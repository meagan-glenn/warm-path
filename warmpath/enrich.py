"""Work-history enrichment for your strongest contacts, cached locally.

The second-degree problem has no data feed: LinkedIn exports your connections, not
theirs. What we can get, compliantly, is public work history from a people index
(Exa) for the people who matter: your strong and warm contacts. Once that is cached,
`bridge` can infer who probably knows a target from overlapping employers and years.

  python -m warmpath enrich            top 150 strong/warm contacts, skips already cached
  python -m warmpath enrich --top 300

One Exa query per person, run once, refreshed only when you ask. Nothing touches LinkedIn.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from .discover import _exa, _g, _norm
from .score import Person, score_all

SCHEMA = """
CREATE TABLE IF NOT EXISTS enrich (
  key TEXT PRIMARY KEY,        -- people.key, or 'target:<slug>' for looked-up targets
  name TEXT, company TEXT, url TEXT, location TEXT,
  history TEXT,                -- JSON list of {company, title, from, to}
  confidence TEXT,             -- high (name+company matched) / medium (name only) / none
  fetched_on TEXT
);
"""


@dataclass
class Job:
    company: str
    title: str
    start: str | None   # YYYY-MM-DD or None
    end: str | None     # None = current

    def d(self) -> dict:
        return {"company": self.company, "title": self.title, "from": self.start, "to": self.end}


@dataclass
class Profile:
    name: str
    company: str
    url: str
    location: str
    history: list[Job] = field(default_factory=list)
    confidence: str = "none"


def _name_key(s: str) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def _first_last(s: str) -> tuple[str, str]:
    parts = (s or "").split()
    return (parts[0].lower() if parts else "", parts[-1].lower().rstrip(".") if parts else "")


def _names_match(a: str, b: str) -> bool:
    """Loose: same first token and same last token (or last is an initial: 'Angela L.')."""
    fa, la = _first_last(a); fb, lb = _first_last(b)
    if not fa or not fb or fa != fb:
        return False
    if la == lb:
        return True
    return len(la) == 1 and lb.startswith(la) or len(lb) == 1 and la.startswith(lb)


def _to_profile(r) -> Profile | None:
    ents = getattr(r, "entities", None) or []
    if not ents:
        return None
    p = _g(ents[0], "properties")
    name = _g(p, "name", default="") or ""
    hist = []
    for w in _g(p, "work_history", "workHistory", default=[]) or []:
        d = _g(w, "dates")
        hist.append(Job((_g(_g(w, "company"), "name", default="") or "").strip(), (_g(w, "title", default="") or "").strip(),
                        _g(d, "from_date", "from"), _g(d, "to_date", "to")))
    current = next((j.company for j in hist if not j.end), hist[0].company if hist else "")
    return Profile(name, current, getattr(r, "url", "") or "", _g(p, "location", default="") or "", hist)


def lookup(exa, name: str, company: str = "", n: int = 4) -> Profile | None:
    """Best public profile for name (+ company). Confidence high if current company matches, medium if only the name."""
    q = f"{name} {company}".strip()
    res = exa.search(q, category="people", type="auto", num_results=n)
    cands = [p for p in (_to_profile(r) for r in getattr(res, "results", []) or []) if p and _names_match(p.name, name)]
    if not cands:
        return None
    cn = _norm(company)
    if cn:
        for p in cands:
            if any(_norm(j.company) == cn or _norm(j.company).startswith(cn + " ") for j in p.history) or _norm(p.company) == cn:
                p.confidence = "high"
                return p
    cands[0].confidence = "medium" if cn else "high"
    return cands[0]


def save(conn: sqlite3.Connection, key: str, p: Profile | None, name: str, company: str) -> None:
    conn.executescript(SCHEMA)
    if p is None:
        conn.execute("INSERT OR REPLACE INTO enrich VALUES (?,?,?,?,?,?,?,?)",
                     (key, name, company, "", "", "[]", "none", date.today().isoformat()))
    else:
        conn.execute("INSERT OR REPLACE INTO enrich VALUES (?,?,?,?,?,?,?,?)",
                     (key, p.name or name, p.company or company, p.url, p.location, json.dumps([j.d() for j in p.history]),
                      p.confidence, date.today().isoformat()))
    conn.commit()


def load(conn: sqlite3.Connection, key: str) -> Profile | None:
    conn.executescript(SCHEMA)
    r = conn.execute("SELECT name, company, url, location, history, confidence FROM enrich WHERE key=?", (key,)).fetchone()
    if not r:
        return None
    hist = [Job(j["company"], j["title"], j.get("from"), j.get("to")) for j in json.loads(r[4] or "[]")]
    return Profile(r[0], r[1], r[2], r[3], hist, r[5])


def load_all(conn: sqlite3.Connection) -> dict[str, Profile]:
    conn.executescript(SCHEMA)
    out = {}
    for key, name, company, url, loc, hist, conf in conn.execute("SELECT key, name, company, url, location, history, confidence FROM enrich"):
        if key.startswith("target:"):
            continue
        out[key] = Profile(name, company, url, loc, [Job(j["company"], j["title"], j.get("from"), j.get("to")) for j in json.loads(hist or "[]")], conf)
    return out


def enrich_top(conn: sqlite3.Connection, top: int = 150, tiers=("strong", "warm"), refresh: bool = False, log=print) -> dict:
    """Look up work history for the top N contacts by strength in the given tiers. Cached; skips done rows unless refresh."""
    exa = _exa()
    if exa is None:
        raise SystemExit("Enrichment needs Exa: `pip install exa-py` and EXA_API_KEY in ./.env")
    conn.executescript(SCHEMA)
    done = {r[0] for r in conn.execute("SELECT key FROM enrich")}
    people = [p for p in score_all(conn) if p.tier in tiers][:top]
    todo = [p for p in people if refresh or p.key not in done]
    log(f"{len(people)} contacts in scope ({', '.join(tiers)}), {len(people) - len(todo)} cached, {len(todo)} to look up.")
    stats = {"looked_up": 0, "high": 0, "medium": 0, "none": 0}
    for i, p in enumerate(todo, 1):
        try:
            prof = lookup(exa, p.name, p.company)
        except Exception as e:  # keep going; one bad query should not stop the batch
            log(f"  ! {p.name}: {type(e).__name__}: {e}")
            prof = None
        save(conn, p.key, prof, p.name, p.company)
        stats["looked_up"] += 1
        stats[prof.confidence if prof else "none"] += 1
        if i % 10 == 0 or i == len(todo):
            log(f"  {i}/{len(todo)}  high={stats['high']} medium={stats['medium']} none={stats['none']}")
    return stats


def coverage(conn: sqlite3.Connection, tiers=("strong", "warm"), top: int = 150) -> dict:
    conn.executescript(SCHEMA)
    done = {r[0]: r[1] for r in conn.execute("SELECT key, confidence FROM enrich")}
    people = [p for p in score_all(conn) if p.tier in tiers][:top]
    have = [p for p in people if p.key in done]
    return {"in_scope": len(people), "enriched": len(have),
            "high": sum(1 for p in have if done[p.key] == "high"), "medium": sum(1 for p in have if done[p.key] == "medium"),
            "none": sum(1 for p in have if done[p.key] == "none")}
