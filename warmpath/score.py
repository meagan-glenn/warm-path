"""Relationship strength: will this person actually help me?

Scored 0 to 100 from the export alone. Every signal is explainable, and the
reasons are returned alongside the score so the user can see why.

Signals, roughly in order of weight:
  reciprocity        a two-way thread exists at all (the single strongest cut)
  volume             messages, counted with a per-day cap so support bursts do not dominate
  span               days between first and last message; long-running beats one-day burst
  recency            last exchange, decayed
  recommendation     written recommendation either direction
  work overlap       their current company is one of my former employers
  invitation         they reached out to me, or I wrote a note when I did
  endorsements       weak, small bump
  unanswered         I sent, they never replied: explicit penalty and a 'cold' flag
"""

from __future__ import annotations

import math
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Person:
    key: str
    name: str
    url: str
    company: str
    position: str
    connected_on: str | None
    sent: int = 0
    received: int = 0
    first_msg: str | None = None
    last_msg: str | None = None
    active_days: int = 0
    capped_msgs: int = 0
    strength: float = 0.0
    tier: str = "unknown"
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)   # user overrides: close / vouch / barely / hub


def _days_ago(iso: str | None, today: date) -> int | None:
    if not iso:
        return None
    try:
        return (today - datetime.strptime(iso, "%Y-%m-%d").date()).days
    except ValueError:
        return None


def _company_norm(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", (s or "").lower())
    s = re.sub(r"\b(inc|llc|ltd|the|co|corp|corporation|company)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


OVERRIDE_SCHEMA = "CREATE TABLE IF NOT EXISTS overrides (key TEXT, flag TEXT, PRIMARY KEY (key, flag));"
FLAGS = ("close", "vouch", "barely", "hub")


def mark(conn: sqlite3.Connection, name: str, flag: str, remove: bool = False) -> str:
    """Persist a one-click override on a person: close / vouch / barely / hub."""
    conn.executescript(OVERRIDE_SCHEMA)
    q = name.lower()
    rows = [(k, n) for k, n in conn.execute("SELECT key, name FROM people") if q in (n or "").lower()]
    if not rows:
        return f"no connection matching '{name}'"
    if len(rows) > 1 and not any(n.lower() == q for _, n in rows):
        return "ambiguous: " + ", ".join(n for _, n in rows[:6])
    key = next((k for k, n in rows if n.lower() == q), rows[0][0])
    if remove:
        conn.execute("DELETE FROM overrides WHERE key=? AND flag=?", (key, flag))
    else:
        conn.execute("INSERT OR IGNORE INTO overrides VALUES (?,?)", (key, flag))
    conn.commit()
    return f"{'unmarked' if remove else 'marked'} {rows[0][1] if len(rows)==1 else name}: {flag}"


def load_people(conn: sqlite3.Connection) -> list[Person]:
    rows = conn.execute(
        """SELECT p.key, p.name, p.url, p.company, p.position, p.connected_on,
                  COALESCE(m.sent,0), COALESCE(m.received,0), m.first_msg, m.last_msg,
                  COALESCE(m.active_days,0), COALESCE(m.capped_msgs,0)
           FROM people p LEFT JOIN msg_agg m ON m.key = p.key"""
    ).fetchall()
    return [Person(*r) for r in rows]


def score_all(conn: sqlite3.Connection, today: date | None = None) -> list[Person]:
    today = today or date.today()
    people = load_people(conn)

    my_companies = {_company_norm(c) for (c,) in conn.execute("SELECT company FROM my_positions") if c}
    recs = {k: d for k, d in conn.execute("SELECT key, direction FROM recommendations")}
    endorse: dict[str, int] = {}
    for k, n in conn.execute("SELECT key, SUM(count) FROM endorsements GROUP BY key"):
        endorse[k] = n
    inv_in = {k for (k,) in conn.execute("SELECT key FROM invitations WHERE direction='INCOMING'")}
    inv_out_note = {k for (k,) in conn.execute("SELECT key FROM invitations WHERE direction='OUTGOING' AND has_note=1")}
    conn.executescript(OVERRIDE_SCHEMA)
    overrides: dict[str, list[str]] = {}
    for k, flag in conn.execute("SELECT key, flag FROM overrides"):
        overrides.setdefault(k, []).append(flag)

    for p in people:
        s = 0.0
        r: list[str] = []
        two_way = p.sent > 0 and p.received > 0

        if two_way:
            s += 30
            r.append("two-way thread")
            s += min(25, 6 * math.log1p(p.capped_msgs))
            if p.capped_msgs >= 20:
                r.append(f"{p.capped_msgs} msgs")
            span = _days_ago(p.first_msg, today)
            last = _days_ago(p.last_msg, today)
            if span is not None and last is not None:
                span_days = span - last
                if span_days > 365:
                    s += 12; r.append(f"{span_days // 365}+ yr thread")
                elif span_days > 90:
                    s += 6; r.append("multi-month thread")
                elif p.active_days <= 1:
                    s -= 8; r.append("one-day burst")
            if last is not None:
                if last <= 90:
                    s += 12; r.append("active in last 90d")
                elif last <= 365:
                    s += 6
                elif last > 3 * 365:
                    s -= 6; r.append("silent 3+ yrs")
        elif p.sent > 0 and p.received == 0:
            s -= 5
            r.append(f"unanswered ({p.sent} sent, 0 back)")
        elif p.received > 0 and p.sent == 0:
            s += 8
            r.append("they messaged, I never replied")

        if p.key in recs:
            s += 25
            r.append(f"recommendation {recs[p.key]}")
        if _company_norm(p.company) in my_companies and p.company:
            s += 15
            r.append(f"colleague at {p.company}")
        if p.key in inv_in:
            s += 4
            r.append("they invited me")
        elif p.key in inv_out_note:
            s += 2
        if endorse.get(p.key):
            s += min(4, endorse[p.key])

        # user overrides: one click beats every heuristic
        p.flags = overrides.get(p.key, [])
        if "vouch" in p.flags:
            s = max(s, 85); r.append("you: would vouch")
        elif "close" in p.flags:
            s = max(s, 70); r.append("you: close")
        if "barely" in p.flags:
            s = min(s, 25); r.append("you: barely know")
        if "hub" in p.flags:
            r.append("hub: knows everyone")

        p.strength = max(0.0, min(100.0, s))
        p.reasons = r
        if p.strength >= 60:
            p.tier = "strong"
        elif p.strength >= 35:
            p.tier = "warm"
        elif p.sent > 0 and p.received == 0:
            p.tier = "cold-unanswered"
        elif p.sent == 0 and p.received == 0:
            p.tier = "cold-untested"
        else:
            p.tier = "weak"
    people.sort(key=lambda p: -p.strength)
    return people
