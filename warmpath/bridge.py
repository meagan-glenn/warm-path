"""Second degree, inferred: which of my people probably know this target?

No feed exists for other people's connections. What we can do is predict the real
mutuals from career overlap: your strong contact who spent three years at the same
company as the target, in the same years, almost certainly knows them. That is the
same guess you make in your head; this makes it for every target and never forgets
someone. The second side of the pair is inferred, not observed, and the output says so.

  python -m warmpath bridge "Elena Verna" --company Lovable [--role "Product Lead"]

Each row is a pair judged on both sides:
  your side      relationship strength from the export (observed)
  their side     bridge score from overlapping employers and years (inferred)
Verdicts: ask-for-intro / ask-if-they-know / forward-note / long-shot.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from .discover import _exa, _norm
from .enrich import Job, Profile, load, load_all, lookup, save
from .score import Person, score_all

# generic employers that prove nothing about knowing someone
GENERIC = {"freelance", "self employed", "self-employed", "consultant", "independent", "various", "stealth", "stealth startup"}


def _d(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _overlap_months(a: Job, b: Job) -> int | None:
    """Months both jobs were concurrent; None if either side lacks dates."""
    a0, a1, b0, b1 = _d(a.start), _d(a.end) or date.today(), _d(b.start), _d(b.end) or date.today()
    if not a0 or not b0:
        return None
    lo, hi = max(a0, b0), min(a1, b1)
    return max(0, (hi.year - lo.year) * 12 + hi.month - lo.month)


@dataclass
class BridgePair:
    person: Person
    bridge: int                 # 0-100 inferred likelihood they know the target
    reasons: list[str] = field(default_factory=list)
    verdict: str = ""
    ask: str = ""


@dataclass
class BridgeReport:
    target_name: str
    target_company: str
    target: Profile | None
    pairs: list[BridgePair] = field(default_factory=list)
    scanned: int = 0
    note: str = ""
    hubs: list[Person] = field(default_factory=list)   # people you marked 'hub': ask regardless of overlap


def _score_pair(mine: Profile, target: Profile) -> tuple[int, list[str]]:
    score, reasons = 0, []
    seen = set()
    for tj in target.history:
        tc = _norm(tj.company)
        if not tc or tc in GENERIC or tc in seen:
            continue
        for mj in mine.history:
            mc = _norm(mj.company)
            if mc != tc and not (mc.startswith(tc + " ") or tc.startswith(mc + " ")):
                continue
            m = _overlap_months(mj, tj)
            if not mj.end and not tj.end:
                score += 45; reasons.append(f"colleagues now at {tj.company}")
            elif m is None:
                score += 15; reasons.append(f"both at {tj.company}, dates unknown")
            elif m >= 24:
                score += 45; reasons.append(f"both at {tj.company} for {m // 12}+ yr together")
            elif m >= 6:
                score += 30; reasons.append(f"both at {tj.company}, {m} months together")
            elif m > 0:
                score += 12; reasons.append(f"both at {tj.company}, brief overlap")
            else:
                score += 8; reasons.append(f"both at {tj.company}, different years")
            seen.add(tc)
            break
    if target.location and mine.location and _norm(target.location) == _norm(mine.location) and score:
        score += 5; reasons.append("same city")
    return min(score, 100), reasons


def _verdict(strength: float, tier: str, bridge: int) -> tuple[str, str]:
    if tier == "cold-unanswered":
        return "skip", "They already ignored you. Do not route through them."
    strong_me = strength >= 55
    strong_bridge = bridge >= 30
    if strong_me and strong_bridge:
        return "ask-for-intro", "Real relationship, real overlap. Ask if they would make a two-line intro; blurb attached."
    if strong_me:
        return "ask-if-they-know", "Real relationship, thin overlap. Ask first whether they actually know them; do not assume."
    if strong_bridge:
        return "forward-note", "They likely know the target better than they know you. Ask if a two-line note would be easy to forward."
    return "long-shot", "Weak on both sides. Only if nothing else exists."


def bridge(conn: sqlite3.Connection, target_name: str, target_company: str, top: int = 8) -> BridgeReport:
    rep = BridgeReport(target_name, target_company, None)
    tkey = "target:" + _norm(target_name).replace(" ", "-") + "@" + _norm(target_company).replace(" ", "-")
    target = load(conn, tkey)
    if target is None:
        exa = _exa()
        if exa is None:
            # demo / offline: accept a target seeded under their own name
            row = conn.execute("SELECT key FROM enrich WHERE lower(name)=lower(?) AND key LIKE 'target:%'", (target_name,)).fetchone()
            if row:
                target = load(conn, row[0])
            else:
                rep.note = "Bridge needs Exa for the target's work history: `pip install exa-py` and EXA_API_KEY in ./.env"
                return rep
        else:
            target = lookup(exa, target_name, target_company)
            save(conn, tkey, target, target_name, target_company)
    rep.target = target
    if target is None or not target.history:
        rep.note = f"Could not find a public work history for {target_name} at {target_company}. Try the exact name as it appears on their profile."
        return rep
    profiles = load_all(conn)
    if not profiles:
        rep.note = "No contacts enriched yet. Run `python -m warmpath enrich` once (top 150 strong/warm contacts, cached)."
        return rep
    people = {p.key: p for p in score_all(conn)}
    rep.hubs = [p for p in people.values() if "hub" in p.flags]
    rep.scanned = len(profiles)
    for key, prof in profiles.items():
        p = people.get(key)
        if not p or prof.confidence == "none":
            continue
        b, reasons = _score_pair(prof, target)
        if b <= 0:
            continue
        if prof.confidence == "medium":
            reasons.append("(profile match by name only; verify it is them)")
        v, ask = _verdict(p.strength, p.tier, b)
        rep.pairs.append(BridgePair(p, b, reasons, v, ask))
    order = {"ask-for-intro": 0, "forward-note": 1, "ask-if-they-know": 2, "long-shot": 3, "skip": 4}
    rep.pairs.sort(key=lambda x: (order[x.verdict], -(x.bridge * 0.6 + x.person.strength * 0.4)))
    rep.pairs = rep.pairs[:top]
    return rep
