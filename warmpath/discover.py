"""External target discovery: recruiters, hiring managers, and in-function peers at a company.

Uses Exa's people search (an index Exa maintains; refreshed weekly). This module never
contacts LinkedIn. It returns public profile URLs the user opens themselves.

Optional dependency: `pip install exa-py`, and EXA_API_KEY in the environment or ./.env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .targets import classify_role

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


@dataclass
class DiscoveryReport:
    company: str
    recruiters: list[Discovered] = field(default_factory=list)
    leaders: list[Discovered] = field(default_factory=list)
    peers: list[Discovered] = field(default_factory=list)
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


def _current_title_company(entity_props: dict) -> tuple[str, str, str]:
    """Return (title, company, location) for the most recent open-ended job in workHistory."""
    wh = entity_props.get("workHistory") or []
    current = [w for w in wh if not (w.get("dates") or {}).get("to")] or wh
    if not current:
        return "", "", entity_props.get("location", "")
    w = current[0]
    return w.get("title", ""), (w.get("company") or {}).get("name", ""), entity_props.get("location", "")


def _search(exa, query: str, n: int) -> list[Discovered]:
    out: list[Discovered] = []
    res = exa.search(query, category="people", type="auto", num_results=n)
    for r in getattr(res, "results", []) or []:
        name, title, loc = "", "", ""
        ents = getattr(r, "entities", None) or []
        if ents:
            props = (ents[0].get("properties") if isinstance(ents[0], dict) else getattr(ents[0], "properties", None)) or {}
            name = props.get("name", "")
            title, _company, loc = _current_title_company(props)
        if not name:
            # Fall back to "Name - Title" in the result title
            t = getattr(r, "title", "") or ""
            name, _, title = t.partition(" - ")
        role_class, reason, fn = classify_role(title, None)
        out.append(Discovered(name.strip(), title.strip(), getattr(r, "url", "") or "", role_class, reason, fn, loc))
    return out


def discover(company: str, role_function: str | None, per_bucket: int = 8) -> DiscoveryReport:
    rep = DiscoveryReport(company=company)
    exa = _exa()
    if exa is None:
        rep.note = ("Discovery needs Exa: `pip install exa-py` and set EXA_API_KEY (env or ./.env). "
                    "Until then, search LinkedIn yourself for: recruiters at " + company +
                    (f", and {FUNCTION_LABEL.get(role_function, role_function)} at {company}" if role_function else ""))
        return rep
    rep.recruiters = _search(exa, f"recruiters and talent acquisition at {company}", per_bucket)
    fn_label = FUNCTION_LABEL.get(role_function or "", None)
    if fn_label:
        rep.leaders = [d for d in _search(exa, f"head of or director of {fn_label} at {company}", per_bucket)]
        rep.peers = [d for d in _search(exa, f"{fn_label} at {company}", per_bucket)]
    else:
        rep.leaders = _search(exa, f"heads of department and directors at {company}", per_bucket)
    # Re-classify with the function so peers vs leaders reads correctly
    for bucket in (rep.leaders, rep.peers):
        for d in bucket:
            d.role_class, d.role_reason, d.function_match = classify_role(d.title, role_function)
    return rep
