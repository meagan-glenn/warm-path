"""Relay: my strong contact -> their coworker -> the target company.

The pattern: your friend Eddie is at Clay. Clay people know Wispr Flow people. Eddie
does not, but a coworker of his does. You want to know which coworker, how close they
are to Eddie, and whom they know at the target, so Eddie can walk down the hall.

  python -m warmpath relay --via "Eduardo Rosenfeld" --target "Wispr Flow" [--about "..."] [--function product]

Data: public work histories from the people index for the hub company (where your
contact works) and the target company, cached locally. Overlap between the two rosters
finds the relay person; overlap with your contact (function, tenure, office) says how
easy the hallway ask is. Everything on the far side of your contact is inferred.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from .bridge import _overlap_months
from .discover import FUNCTION_LABEL, _exa, _norm
from .enrich import SCHEMA, Job, Profile, _to_profile, load_all
from .score import score_all
from .targets import FUNCTIONS

# Employers too large to imply acquaintance. Overlap there counts a little, not a lot.
BIG = {"google", "alphabet", "microsoft", "amazon", "aws", "meta", "facebook", "apple", "cisco", "adobe", "ibm", "oracle",
       "salesforce", "deloitte", "accenture", "mckinsey company", "mckinsey", "kpmg", "pwc", "ey", "linkedin", "uber", "airbnb",
       "netflix", "intel", "nvidia", "samsung", "capgemini", "infosys", "tcs", "wipro", "cognizant"}
SKIP = re.compile(r"universit|college|school|institute|self[- ]?employed|freelance|independent|stealth|consult", re.I)


def _function(title: str) -> str | None:
    for fn, rx in FUNCTIONS.items():
        if rx.search(title or ""):
            return fn
    return None


def _collapse(hist: list[Job]) -> dict[str, tuple[str, str | None, str | None]]:
    """Per normalized company: (display name, earliest start, latest end or None if any stint is current)."""
    out: dict[str, tuple[str, str | None, str | None]] = {}
    for j in hist:
        k = _norm(j.company)
        if not k or SKIP.search(j.company):
            continue
        name, s0, e0 = out.get(k, (j.company, None, "x"))
        start = min([x for x in (s0, j.start) if x], default=None)
        end = None if (e0 is None or j.end is None) else max([x for x in (e0, j.end) if x and x != "x"], default=None)
        out[k] = (name, start, end)
    return out


def _roster(conn: sqlite3.Connection, exa, company: str, about: str = "", extra_query: str = "", n: int = 40) -> list[Profile]:
    """People at a company from the index, cached under roster:<company>:<url>."""
    conn.executescript(SCHEMA)
    ck = _norm(company)
    rows = conn.execute("SELECT name, company, url, location, history, confidence FROM enrich WHERE key LIKE ?", (f"roster:{ck}:%",)).fetchall()
    if rows:
        out, seen = [], set()
        for r in rows:
            if _norm(r[0]) in seen:
                continue
            seen.add(_norm(r[0]))
            out.append(Profile(r[0], r[1], r[2], r[3], [Job(j["company"], j["title"], j.get("from"), j.get("to")) for j in json.loads(r[4] or "[]")], r[5]))
        return out
    cq = f"{company} ({about})" if about else company
    queries = [f"people who work at {cq}", f"heads, leads, managers and senior staff at {cq}",
               f"engineers, product managers and designers at {cq}",
               f"sales, customer success, deployment, marketing and go-to-market at {cq}"]
    if extra_query:
        queries.append(f"{extra_query} at {cq}")
    seen, out = set(), []
    def uk(u): return re.sub(r"^https?://(www\.)?", "", (u or "").lower()).rstrip("/")
    for q in queries:
        res = exa.search(q, category="people", type="auto", num_results=n)
        for r in getattr(res, "results", []) or []:
            p = _to_profile(r)
            if not p or uk(p.url) in seen or _norm(p.name) in seen:
                continue
            seen.add(uk(p.url)); seen.add(_norm(p.name))
            if not any(_norm(j.company) == ck or _norm(j.company).startswith(ck + " ") for j in p.history):
                continue
            out.append(p)
    for p in out:
        conn.execute("INSERT OR REPLACE INTO enrich VALUES (?,?,?,?,?,?,?,?)",
                     (f"roster:{ck}:{p.url}", p.name, company, p.url, p.location, json.dumps([j.d() for j in p.history]), "high", date.today().isoformat()))
    conn.commit()
    return out


@dataclass
class Relay:
    hub_person: Profile          # Eddie's coworker
    target_person: Profile       # who they know at the target
    link_score: int              # inferred: hub_person <-> target_person
    link_reason: str
    close_score: int             # inferred: how close hub_person is to my contact
    close_reason: str
    hub_title: str = ""
    target_title: str = ""


@dataclass
class RelayReport:
    via_name: str
    hub_company: str
    target_company: str
    relays: list[Relay] = field(default_factory=list)
    hub_size: int = 0
    target_size: int = 0
    note: str = ""


def _link(a: Profile, b: Profile) -> tuple[int, str]:
    """Best shared-employer overlap between two people, big companies downweighted."""
    ca, cb = _collapse(a.history), _collapse(b.history)
    best, why = 0, ""
    for k, (name, s0, e0) in ca.items():
        if k not in cb:
            continue
        nb, s1, e1 = cb[k]
        m = _overlap_months(Job(name, "", s0, e0), Job(nb, "", s1, e1))
        if e0 is None and e1 is None:
            sc, r = 60, f"colleagues now at {name}"
        elif m is None:
            sc, r = 15, f"both at {name}, dates unknown"
        elif m >= 24:
            sc, r = 55, f"both at {name} for {m // 12}+ yr together"
        elif m >= 6:
            sc, r = 35, f"both at {name}, {m} months together"
        elif m > 0:
            sc, r = 15, f"both at {name}, brief overlap"
        else:
            sc, r = 6, f"both at {name}, different years"
        if k in BIG:
            sc = int(sc * 0.35); r += " (large company, weak signal)"
        if sc > best:
            best, why = sc, r
    return best, why


def _closeness(via: Profile, via_title: str, peer: Profile, hub: str) -> tuple[int, str]:
    """How easy is the hallway ask: same function, tenure overlap at the hub, same office."""
    sc, r = 0, []
    fv, fp = _function(via_title), _function(next((j.title for j in peer.history if _norm(j.company).startswith(_norm(hub))), ""))
    if fv and fv == fp:
        sc += 40; r.append(f"same function ({FUNCTION_LABEL.get(fv, fv).split(',')[0]})")
    hv, hp = _collapse(via.history).get(_norm(hub)), _collapse(peer.history).get(_norm(hub))
    if hv and hp:
        m = _overlap_months(Job(hub, "", hv[1], hv[2]), Job(hub, "", hp[1], hp[2]))
        if m is None or m >= 6:
            sc += 30; r.append(f"overlapping tenure at {hub}" + (f" ({m} mo)" if m else ""))
        elif m > 0:
            sc += 15; r.append(f"short shared tenure at {hub}")
    if via.location and peer.location and _norm(via.location) == _norm(peer.location):
        sc += 15; r.append("same city")
    return min(sc, 100), "; ".join(r) or "same company only"


def relay(conn: sqlite3.Connection, via_name: str, target_company: str, about: str = "", role_function: str | None = None,
          top: int = 8) -> RelayReport:
    exa = _exa()
    rep = RelayReport(via_name, "", target_company)
    if exa is None:
        rep.note = "Relay needs Exa: `pip install exa-py` and EXA_API_KEY in ./.env"; return rep
    q = via_name.lower()
    mine = [p for p in score_all(conn) if q in p.name.lower()]
    if not mine:
        rep.note = f"No connection matching '{via_name}'."; return rep
    me_p = mine[0]
    profiles = load_all(conn)
    via = profiles.get(me_p.key)
    if via is None or not via.history:
        rep.note = f"{me_p.name} is not enriched yet. Run `python -m warmpath enrich` (or --top higher) so their work history is cached."; return rep
    hub = via.company or me_p.company
    rep.hub_company = hub
    hub_people = [p for p in _roster(conn, exa, hub, n=40) if p.url != via.url and not (p.name or "").lower() == me_p.name.lower()]
    tq = FUNCTION_LABEL.get(role_function or "", "")
    tgt_people = _roster(conn, exa, target_company, about=about, extra_query=tq, n=30)
    rep.hub_size, rep.target_size = len(hub_people), len(tgt_people)
    for hp in hub_people:
        for tp in tgt_people:
            sc, why = _link(hp, tp)
            if sc < 12:
                continue
            cs, cwhy = _closeness(via, me_p.position, hp, hub)
            rep.relays.append(Relay(hp, tp, sc, why, cs, cwhy,
                                    next((j.title for j in hp.history if not j.end), hp.history[0].title if hp.history else ""),
                                    next((j.title for j in tp.history if not j.end), tp.history[0].title if tp.history else "")))
    rep.relays.sort(key=lambda x: -(x.link_score * 0.65 + x.close_score * 0.35))
    rep.relays = rep.relays[:top]
    return rep
