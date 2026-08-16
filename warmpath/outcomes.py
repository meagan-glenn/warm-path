"""Outcome log: what was sent, to whom, in what shape, made how, and what happened.

This is the tool's evaluation set. Every draft the tool produces is a prediction
(this verdict, this shape, this seat, this generator will get a reply); the log is
where those predictions meet reality. `outcomes --report` turns it into rates by
shape, seat, verdict, channel and generator (scaffold vs Claude vs pasted prompt vs
hand-written), so the choices in docs/decisions.md can be checked, not just argued.

Stored in the same local SQLite database. Nothing leaves the machine.

  warmpath log "Ryan Boyd" --company Simile --shape cold --channel linkedin --sent 2026-08-15 --generator scaffold
  warmpath log "Ryan Boyd" --company Simile --status replied --note "answered the question, no mention of the role"
  warmpath outcomes
  warmpath outcomes --report
"""

from __future__ import annotations

import sqlite3
from datetime import date
from statistics import median

SCHEMA = """
CREATE TABLE IF NOT EXISTS outcomes (
  id INTEGER PRIMARY KEY,
  person TEXT NOT NULL,
  company TEXT NOT NULL,
  shape TEXT,          -- spend / ask-for-routing / forward-note / cold / feedback / ask-for-intro / relay / other
  channel TEXT,        -- linkedin / email / video / other
  sent_on TEXT,        -- ISO date
  status TEXT DEFAULT 'sent',  -- sent / replied / silent / intro-made / call-booked / rejected / not-close
  updated_on TEXT,
  note TEXT
);
"""

# Columns added after v1. Applied idempotently on every open so old databases upgrade in place.
EXTRA_COLUMNS = {
    "verdict": "TEXT",       # what the tool said about the pair: spend / ask-for-routing / cold / ask-for-intro / ...
    "seat": "TEXT",          # route / champion / peer / other (who you wrote to)
    "generator": "TEXT",     # scaffold / claude-opus-5 / prompt-paste / hand (how the words were made)
    "predicted": "TEXT",     # optional numeric prior the tool attached (strength or bridge score)
    "replied_on": "TEXT",    # first date the status left 'sent' for a positive outcome
}

STATUSES = ("sent", "replied", "silent", "intro-made", "call-booked", "rejected", "not-close")
POSITIVE = {"replied", "intro-made", "call-booked"}      # a human answered
GENERATORS = ("scaffold", "claude-opus-5", "prompt-paste", "hand")


def ensure(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(outcomes)")}
    for col, typ in EXTRA_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE outcomes ADD COLUMN {col} {typ}")
    conn.commit()


def log(conn: sqlite3.Connection, person: str, company: str, shape: str | None, channel: str | None,
        sent_on: str | None, status: str | None, note: str | None,
        verdict: str | None = None, seat: str | None = None, generator: str | None = None, predicted: str | None = None) -> str:
    ensure(conn)
    today = date.today().isoformat()
    row = conn.execute("SELECT id, replied_on FROM outcomes WHERE lower(person)=lower(?) AND lower(company)=lower(?) ORDER BY id DESC LIMIT 1",
                       (person, company)).fetchone()
    if row and (status or note) and not sent_on:  # annotate or advance the existing thread
        replied_on = row[1] or (today if status in POSITIVE else None)
        conn.execute("UPDATE outcomes SET status=COALESCE(?, status), updated_on=?, note=COALESCE(?, note), replied_on=?, "
                     "verdict=COALESCE(?, verdict), seat=COALESCE(?, seat), generator=COALESCE(?, generator) WHERE id=?",
                     (status, today, note, replied_on, verdict, seat, generator, row[0]))
        conn.commit()
        return f"updated {person} @ {company}: {status or 'note added'}"
    conn.execute("INSERT INTO outcomes (person, company, shape, channel, sent_on, status, updated_on, note, verdict, seat, generator, predicted, replied_on) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (person, company, shape or "other", channel or "linkedin", sent_on or today, status or "sent", today, note,
                  verdict, seat, generator or "hand", predicted, today if (status in POSITIVE) else None))
    conn.commit()
    return f"logged {person} @ {company}: {shape or 'other'} via {channel or 'linkedin'}, {status or 'sent'} {sent_on or today}, made by {generator or 'hand'}"


FOLLOWUP_1 = 5    # days after send: one bump (the single biggest lift in every follow-up corpus)
FOLLOWUP_2 = 12   # days: close the loop, then stop; a third follow-up is noise
SETTLE_DAYS = 14  # a thread younger than this with no reply is 'open', not 'silent', in the rates

COLS = ["person", "company", "shape", "channel", "sent_on", "status", "updated_on", "note", "verdict", "seat", "generator", "predicted", "replied_on"]


def rows_full(conn: sqlite3.Connection) -> list[dict]:
    ensure(conn)
    return [dict(zip(COLS, r)) for r in conn.execute(
        "SELECT person, company, shape, channel, sent_on, status, updated_on, COALESCE(note,''), verdict, seat, generator, predicted, replied_on "
        "FROM outcomes ORDER BY sent_on, id")]


def report(conn: sqlite3.Connection) -> list[tuple]:
    """Back-compat: the eight v1 columns as tuples."""
    return [tuple(r[c] for c in COLS[:8]) for r in rows_full(conn)]


def due(rows: list[tuple], today: date | None = None) -> list[tuple[str, str, int, str]]:
    """Threads still at 'sent' with a follow-up due: (person, company, days_since, which)."""
    today = today or date.today()
    out = []
    for person, company, shape, channel, sent, status, upd, note in rows:
        if status != "sent" or not sent:
            continue
        try:
            days = (today - date.fromisoformat(sent)).days
        except ValueError:
            continue
        if days >= FOLLOWUP_2:
            out.append((person, company, days, "close the loop (--followup 2), then stop"))
        elif days >= FOLLOWUP_1:
            out.append((person, company, days, "one bump (--followup 1)"))
    return out


# ---- the evaluation report

def _days(a: str | None, b: str | None) -> int | None:
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days if a and b else None
    except ValueError:
        return None


def _rate(rows: list[dict], key: str, today: date) -> list[dict]:
    """Reply rate per value of `key`. Open threads (younger than SETTLE_DAYS, no answer) are excluded from the denominator."""
    groups: dict[str, dict] = {}
    for r in rows:
        k = r.get(key) or "(unset)"
        g = groups.setdefault(k, {"key": k, "sent": 0, "settled": 0, "replied": 0, "open": 0, "days": []})
        g["sent"] += 1
        pos = r["status"] in POSITIVE
        age = _days(r["sent_on"], today.isoformat())
        if pos:
            g["settled"] += 1; g["replied"] += 1
            d = _days(r["sent_on"], r.get("replied_on") or r.get("updated_on"))
            if d is not None:
                g["days"].append(d)
        elif r["status"] in ("silent", "rejected", "not-close") or (age is not None and age >= SETTLE_DAYS):
            g["settled"] += 1
        else:
            g["open"] += 1
    out = []
    for g in groups.values():
        g["rate"] = round(g["replied"] / g["settled"], 2) if g["settled"] else None
        g["median_days"] = median(g["days"]) if g["days"] else None
        del g["days"]
        out.append(g)
    return sorted(out, key=lambda g: (-(g["rate"] or 0), -g["sent"]))


def evaluate(conn: sqlite3.Connection, today: date | None = None) -> dict:
    """The numbers docs/decisions.md promises: rates by shape, seat, verdict, channel, generator; intro-ask precision."""
    today = today or date.today()
    rows = rows_full(conn)
    intro = [r for r in rows if (r["shape"] or "") in ("ask-for-intro", "ask-if-they-know", "relay")]
    intro_settled = [r for r in intro if r["status"] in POSITIVE or r["status"] in ("silent", "not-close", "rejected")]
    intro_true = [r for r in intro_settled if r["status"] in ("intro-made", "replied", "call-booked")]
    intro_false = [r for r in intro_settled if r["status"] == "not-close"]
    for r in rows:
        r["_all"] = "all"
    return {
        "n": len(rows),
        "overall": _rate(rows, "_all", today)[0] if rows else None,
        "by_shape": _rate(rows, "shape", today),
        "by_seat": _rate(rows, "seat", today),
        "by_verdict": _rate(rows, "verdict", today),
        "by_channel": _rate(rows, "channel", today),
        "by_generator": _rate(rows, "generator", today),
        "intro_precision": {
            "asked": len(intro), "settled": len(intro_settled),
            "knew_them": len(intro_true), "did_not_know": len(intro_false),
            "precision": round(len(intro_true) / (len(intro_true) + len(intro_false)), 2) if (intro_true or intro_false) else None,
        },
        "settle_days": SETTLE_DAYS,
    }


def format_evaluation(ev: dict) -> str:
    if not ev["n"]:
        return "No outcomes logged yet, so no rates. Log what you send and what comes back; the report builds itself."
    lines = [f"{ev['n']} threads logged. Rates count only settled threads (answered, or older than {ev['settle_days']} days, or closed); open ones are shown, not counted."]
    o = ev["overall"]
    if o:
        lines.append(f"Overall: {o['replied']}/{o['settled']} replied ({_pct(o['rate'])}), {o['open']} open" + (f", median {o['median_days']:.0f} days to reply" if o["median_days"] is not None else ""))
    for title, key in (("By shape", "by_shape"), ("By seat", "by_seat"), ("By verdict", "by_verdict"), ("By generator", "by_generator"), ("By channel", "by_channel")):
        lines.append(f"\n{title}:")
        for g in ev[key]:
            md = f"  median {g['median_days']:.0f}d" if g["median_days"] is not None else ""
            lines.append(f"  {g['key']:18s} {g['replied']}/{g['settled']} replied  {_pct(g['rate']):>5s}  ({g['open']} open, {g['sent']} sent){md}")
    ip = ev["intro_precision"]
    lines.append(f"\nIntro-ask precision (did the inferred mutual actually know them?): {ip['knew_them']} yes, {ip['did_not_know']} no, {ip['asked'] - ip['settled']} pending"
                 + (f"  ->  {_pct(ip['precision'])}" if ip["precision"] is not None else "  ->  no settled asks yet"))
    lines.append("\nSmall numbers. Read direction, not decimals, until a bucket has 20 or more settled threads.")
    return "\n".join(lines)


def _pct(x) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"
