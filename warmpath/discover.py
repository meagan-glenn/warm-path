"""External target discovery: recruiters, hiring managers, and in-function peers at a company.

Uses Exa's people search (an index Exa maintains; refreshed weekly). This module never
contacts LinkedIn. It returns public profile URLs the user opens themselves.

Optional dependency: `pip install exa-py`, and EXA_API_KEY in the environment or ./.env.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from .targets import classify_role

SUFFIXES = {"inc", "llc", "ltd", "corp", "co", "ai", "labs", "technologies", "technology", "hq", "io", "com"}

FUNCTION_LABEL = {
    "product": "product managers and product leads",
    "cs": "customer success, deployment, onboarding, and solutions leads",
    "gtm": "sales, go-to-market, and revenue leaders",
    "eng": "engineering managers and engineering leads",
    "ops": "operations, strategy, and chief of staff",
    "design": "design leads and design managers",
}


@dataclass
class Discovered:
    name: str
    title: str
    url: str
    role_class: str
    role_reason: str
    function_match: bool
    location: str = ""
    company: str = ""
    at_target: bool = False


@dataclass
class DiscoveryReport:
    company: str
    recruiters: list[Discovered] = field(default_factory=list)
    leaders: list[Discovered] = field(default_factory=list)
    peers: list[Discovered] = field(default_factory=list)
    roster: list[Discovered] = field(default_factory=list)   # fallback: everyone the index has at the company
    note: str = ""


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _exa():
    _load_dotenv()
    key = os.environ.get("EXA_API_KEY")
    if not key:
        return None
    try:
        from exa_py import Exa
    except ImportError:
        return None
    return Exa(api_key=key)


def _g(obj, *names, default=None):
    """Read a field from a dict or a typed SDK object, trying several names (snake and camel case)."""
    if obj is None:
        return default
    for n in names:
        if isinstance(obj, dict):
            if n in obj and obj[n] is not None:
                return obj[n]
        elif getattr(obj, n, None) is not None:
            return getattr(obj, n)
    return default


def _current_title_company(props) -> tuple[str, str, str]:
    """Return (title, company, location) for the most recent open-ended job in work history."""
    wh = _g(props, "work_history", "workHistory", default=[]) or []
    current = [w for w in wh if not _g(_g(w, "dates"), "to_date", "to")] or wh
    loc = _g(props, "location", default="") or ""
    if not current:
        return "", "", loc
    w = current[0]
    return (_g(w, "title", default="") or "", _g(_g(w, "company"), "name", default="") or "", loc)


def _search(exa, query: str, n: int) -> list[Discovered]:
    out: list[Discovered] = []
    res = exa.search(query, category="people", type="auto", num_results=n)
    for r in getattr(res, "results", []) or []:
        name, title, loc, company = "", "", "", ""
        ents = getattr(r, "entities", None) or []
        if ents:
            props = _g(ents[0], "properties")
            name = _g(props, "name", default="") or ""
            title, company, loc = _current_title_company(props)
        if not name:
            # Fall back to "Name - Title" in the result title
            t = getattr(r, "title", "") or ""
            name, _, title = t.partition(" - ")
        role_class, reason, fn = classify_role(title, None)
        out.append(Discovered(name.strip(), title.strip(), getattr(r, "url", "") or "", role_class, reason, fn, loc, company.strip()))
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def discover(company: str, role_function: str | None, per_bucket: int = 8, aliases: list[str] | None = None,
             about: str = "") -> DiscoveryReport:
    rep = DiscoveryReport(company=company)
    names = [_norm(x) for x in [company, *(aliases or [])] if x]
    # A short description disambiguates common words and surnames ("Simile, the synthetic-user AI startup")
    company_q = f"{company} ({about})" if about else company
    exa = _exa()
    if exa is None:
        rep.note = ("Discovery needs Exa: `pip install exa-py` and set EXA_API_KEY (env or ./.env). "
                    "Until then, search LinkedIn yourself for: recruiters at " + company +
                    (f", and {FUNCTION_LABEL.get(role_function, role_function)} at {company}" if role_function else ""))
        return rep
    rep.recruiters = _search(exa, f"recruiters and talent acquisition at {company_q}", per_bucket)
    fn_label = FUNCTION_LABEL.get(role_function or "", None)
    if fn_label:
        rep.leaders = _search(exa, f"head of or director of {fn_label} at {company_q}", per_bucket)
        rep.peers = _search(exa, f"{fn_label} at {company_q}", per_bucket)
    else:
        rep.leaders = _search(exa, f"heads of department and directors at {company_q}", per_bucket)
    def finalize(bucket):
        for d in bucket:
            d.role_class, d.role_reason, d.function_match = classify_role(d.title, role_function)
            c = _norm(d.company)
            # exact, or the alias plus a corporate suffix ("fractional ai inc"); never a bare substring or a longer name
            d.at_target = bool(c) and any(n == c or (c.startswith(n + " ") and c[len(n):].strip() in SUFFIXES) for n in names)

    for bucket in (rep.recruiters, rep.leaders, rep.peers):
        finalize(bucket)
    # Small companies: role queries return near-misses. Fall back to a roster query and keep only confirmed matches.
    seen = {d.url for b in (rep.recruiters, rep.leaders, rep.peers) for d in b if d.at_target}
    if len(seen) < 4:
        roster = _search(exa, f"people who work at {company_q}", max(10, per_bucket * 2))
        finalize(roster)
        rep.roster = [d for d in roster if d.at_target and d.url not in seen]
    return rep
