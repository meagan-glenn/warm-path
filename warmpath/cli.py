"""warmpath CLI.

  python -m warmpath ingest <export.zip|folder> [--db data/warmpath.db] [--me "First Last"]
  python -m warmpath people [--top 30] [--tier strong] [--company X]
  python -m warmpath target "Lovable" [--alias "Fractional AI"] [--function product] [--orbit Anthropic --orbit Cursor]
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .ingest import ingest
from .score import score_all
from .targets import build_report

DEFAULT_DB = Path("data/warmpath.db")


def _conn(db: Path) -> sqlite3.Connection:
    if not db.exists():
        raise SystemExit(f"No database at {db}. Run: python -m warmpath ingest <export.zip>")
    return sqlite3.connect(db)


def cmd_ingest(a):
    a.db.parent.mkdir(parents=True, exist_ok=True)
    stats = ingest(Path(a.export), a.db, me=a.me)
    print("Ingested:", ", ".join(f"{k}={v}" for k, v in stats.items()))
    print(f"Database: {a.db}  (local only; nothing was sent anywhere)")


def cmd_people(a):
    people = score_all(_conn(a.db))
    tiers = {}
    for p in people:
        tiers[p.tier] = tiers.get(p.tier, 0) + 1
    print(f"{len(people)} connections. Tiers: " + ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))
    print()
    shown = 0
    for p in people:
        if a.tier and p.tier != a.tier:
            continue
        if a.company and a.company.lower() not in (p.company or "").lower():
            continue
        print(f"{p.strength:5.1f} {p.tier:15s} {p.name:28s} {p.company[:24]:24s} {p.position[:34]:34s} {'; '.join(p.reasons)}")
        shown += 1
        if shown >= a.top:
            break


def cmd_target(a):
    rep = build_report(_conn(a.db), a.company, aliases=a.alias, role_function=a.function, orbit=a.orbit)
    names = " / ".join([rep.company, *rep.aliases])
    print(f"=== {names}" + (f"  (role function: {rep.role_function})" if rep.role_function else ""))
    if not rep.matches:
        print("\nNo 1st-degree connections at this company.")
        print("This is the empty state. Next moves:")
        print("  1. Check the company's aliases: recent rename, acquired startup, parent entity. Re-run with --alias.")
        print("  2. Find recruiters and the hiring manager from outside LinkedIn (v1: Exa / Apollo). Email beats DM.")
        print("  3. Second degree: which of your strong relationships know someone there? (v2)")
    else:
        print(f"\n{len(rep.matches)} connection(s) at target:\n")
        for t in rep.matches:
            p = t.person
            print(f"[{t.verdict.upper()}] {p.name}  |  {p.position}")
            print(f"    mutual: {p.strength:.0f} ({p.tier}; {'; '.join(p.reasons) or 'no history'})")
            print(f"    target: {t.role_class} ({t.role_reason}); weak side: {t.weak_side}")
            print(f"    -> {t.ask}")
            print(f"    {p.url}")
            print()
    if rep.orbit:
        print("Adjacent orbit (strong/warm relationships at related companies, for 2nd-degree asks):")
        for oc, p in rep.orbit[:10]:
            print(f"  {p.strength:4.0f} {p.name:26s} {oc:16s} {p.position[:40]}")
    elif a.orbit:
        print("No strong relationships in the listed orbit companies.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="warmpath")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest"); s.add_argument("export"); s.add_argument("--me"); s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("people"); s.add_argument("--top", type=int, default=30); s.add_argument("--tier"); s.add_argument("--company"); s.set_defaults(fn=cmd_people)
    s = sub.add_parser("target"); s.add_argument("company"); s.add_argument("--alias", action="append", default=[])
    s.add_argument("--function", choices=["product", "cs", "gtm", "eng", "ops", "design"]); s.add_argument("--orbit", action="append", default=[])
    s.set_defaults(fn=cmd_target)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
