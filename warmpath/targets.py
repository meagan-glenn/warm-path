"""Per-application shortlist: who in my network reaches the target, and how much each path is worth.

A path is a pair (mutual, target). In v0 the mutual and the target are the same
person (1st degree). Each side gets its own read:
  mutual strength   from score.py: will they help me?
  target strength   from their title: can they champion me, or only route me?

The output names the weak side of every pair, because the ask differs:
  strong mutual, weak target   "who actually runs hiring for this?"
  weak mutual, strong target   "would you forward a two-line note?"
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from .score import Person, _company_norm, score_all

RECRUITER = re.compile(r"recruit|talent|sourc|people (ops|partner|team)|\bta\b|hiring", re.I)
SENIOR = re.compile(r"founder|co-founder|\bceo\b|\bcto\b|\bcoo\b|\bcpo\b|chief|\bvp\b|vice president|head of|head,|director|principal|\bstaff\b|\blead\b", re.I)
MID = re.compile(r"senior|\bsr\.?\b|manager|\bii\b|\biii\b", re.I)
JUNIOR = re.compile(r"intern|associate|junior|\bjr\.?\b|coordinator|new grad|apprentice", re.I)

FUNCTIONS = {
    "product": re.compile(r"product|\bpm\b|\bcpo\b", re.I),
    "cs": re.compile(r"customer success|customer experience|\bcs\b|onboarding|adoption|implementation|deployment|solutions|account manag", re.I),
    "gtm": re.compile(r"sales|gtm|go-to-market|revenue|account exec|\bae\b|\bsdr\b|\bbdr\b|partnership|growth|marketing", re.I),
    "eng": re.compile(r"engineer|developer|swe|technical|architect|data|ml\b|research", re.I),
    "ops": re.compile(r"operations|\bops\b|chief of staff|strategy|bizops|program", re.I),
    "design": re.compile(r"design|ux|ui|research", re.I),
}


@dataclass
class TargetPerson:
    person: Person
    role_class: str          # champion / route / peer / other
    role_reason: str
    function_match: bool
    verdict: str             # spend / ask-for-routing / forward-note / cold / skip
    ask: str
    weak_side: str           # mutual / target / neither / both


@dataclass
class TargetReport:
    company: str
    aliases: list[str]
    role_function: str | None
    matches: list[TargetPerson] = field(default_factory=list)
    orbit: list[tuple[str, Person]] = field(default_factory=list)   # (orbit company, person)


def classify_role(position: str, role_function: str | None) -> tuple[str, str, bool]:
    pos = position or ""
    fn_match = bool(role_function and FUNCTIONS.get(role_function) and FUNCTIONS[role_function].search(pos))
    if RECRUITER.search(pos):
        return "route", "recruiter / TA", fn_match
    if SENIOR.search(pos):
        return ("champion", "senior + same function", True) if fn_match else ("champion", "senior, other function", False)
    if JUNIOR.search(pos):
        return "other", "junior", fn_match
    if fn_match:
        return "peer", "in-function peer", True
    return "other", "other function", False


def _verdict(p: Person, role_class: str) -> tuple[str, str, str]:
    strong = p.tier in ("strong", "warm")
    unanswered = p.tier == "cold-unanswered"
    if role_class == "route":
        if unanswered:
            return "skip", "Already tried, no reply. Do not spend more here; find a warmer route.", "mutual"
        if strong:
            return "ask-for-routing", "Ask them directly who owns this req and whether they can flag your application.", "neither"
        return "cold", "Recruiters rarely reply cold. Email is more normal than DM for this. Low priority.", "mutual"
    if role_class == "champion":
        if strong:
            return "spend", "Your best path. Ask for 20 minutes and a read on the team; let them offer to advocate.", "neither"
        if unanswered:
            return "cold", "Strong seat, but they have not replied before. Try once via email with a specific hook, then stop.", "mutual"
        return "forward-note", "Right seat, thin relationship. Ask if they would forward a two-line note, not for a favor.", "mutual"
    if role_class == "peer":
        if strong:
            return "ask-for-routing", "They know the team. Ask who the hiring manager is and what they actually value.", "target"
        return "cold", "Peer with no relationship. Cheap 'how is the team?' ask, low expected yield.", "both"
    if strong:
        return "ask-for-routing", "Real relationship, wrong seat. Ask them who runs hiring for this and for an internal referral link.", "target"
    if unanswered:
        return "skip", "Neither the relationship nor the seat is there, and they already ignored you.", "both"
    return "cold", "No relationship, wrong seat. One cheap 'who owns hiring for X?' message, then move on.", "both"


def match_company(people: list[Person], names: list[str]) -> list[Person]:
    norms = [_company_norm(n) for n in names if n]
    out = []
    for p in people:
        c = _company_norm(p.company)
        if not c:
            continue
        if any(c == n or c.startswith(n + " ") or (len(n) > 4 and n in c) for n in norms):
            out.append(p)
    return out


def build_report(conn: sqlite3.Connection, company: str, aliases: list[str] | None = None,
                 role_function: str | None = None, orbit: list[str] | None = None) -> TargetReport:
    people = score_all(conn)
    aliases = aliases or []
    rep = TargetReport(company=company, aliases=aliases, role_function=role_function)
    for p in match_company(people, [company, *aliases]):
        role_class, reason, fn = classify_role(p.position, role_function)
        verdict, ask, weak = _verdict(p, role_class)
        rep.matches.append(TargetPerson(p, role_class, reason, fn, verdict, ask, weak))
    order = {"spend": 0, "ask-for-routing": 1, "forward-note": 2, "cold": 3, "skip": 4}
    rep.matches.sort(key=lambda t: (order[t.verdict], -t.person.strength))
    for oc in orbit or []:
        for p in match_company(people, [oc]):
            if p.tier in ("strong", "warm"):
                rep.orbit.append((oc, p))
    rep.orbit.sort(key=lambda x: -x[1].strength)
    return rep
