"""warmpath CLI.

  python -m warmpath ingest <export.zip|folder> [--db data/warmpath.db] [--me "First Last"]
  python -m warmpath people [--top 30] [--tier strong] [--company X]
  python -m warmpath target "Lovable" [--alias "Fractional AI"] [--function product] [--orbit Anthropic --orbit Cursor]
  python -m warmpath draft "Ryan Boyd" --target Simile --role "Deployment Strategist" [--hook "..."] [--llm]
  python -m warmpath discover "Ode with Anthropic" --function cs
  python -m warmpath demo            synthetic export + data/demo.db, no real data needed
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from .demo import build as build_demo
from .discover import _load_dotenv, discover
from .drafts import draft_for
from .ingest import ingest
from .outcomes import STATUSES, log, report
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


def cmd_demo(a):
    out = Path(a.out)
    stats = build_demo(out)
    db = Path("data/demo.db") if a.db == DEFAULT_DB else a.db
    db.parent.mkdir(parents=True, exist_ok=True)
    ingest(out, db)
    print(f"Synthetic export written to {out}/ ({stats['connections']} connections, {stats['messages']} messages, {stats['companies']} companies).")
    print(f"Ingested into {db}. Every name and company is invented. Try:\n")
    for c in (f'python -m warmpath --db {db} people --top 15',
              f'python -m warmpath --db {db} target "Corvid AI" --function cs',
              f'python -m warmpath --db {db} target Halberd --function cs',
              f'python -m warmpath --db {db} target Tessellate --function cs',
              f'python -m warmpath --db {db} target Tessellate --alias "Fractal Ops" --function cs --orbit "Northwind Ventures" --orbit Meridian',
              f'python -m warmpath --db {db} draft "Elena Castellano" --target "Corvid AI" --function cs --role "CS Lead" --hook "your post on onboarding handoffs stuck with me"'):
        print("  " + c)


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


def cmd_draft(a):
    rep = build_report(_conn(a.db), a.target, aliases=a.alias, role_function=a.function)
    q = a.person.lower()
    matches = [t for t in rep.matches if q in t.person.name.lower() or q in (t.person.url or "").lower()]
    if not matches:
        raise SystemExit(f"No connection matching '{a.person}' at {a.target}. Run `target` first to see who is there.")
    t = matches[0]
    print(f"To: {t.person.name}  |  {t.person.position} at {t.person.company}")
    print(f"Verdict: {t.verdict.upper()}  ({t.ask})")
    print(f"Channel: {a.channel}" + ("  |  LLM polish on" if a.llm else "  |  scaffold only, add --llm to finish it"))
    print("-" * 60)
    print(draft_for(t, a.role or "", a.hook or "", a.channel, a.llm))


def cmd_discover(a):
    rep = discover(a.company, a.function, per_bucket=a.n, aliases=a.alias, about=a.about or "")
    print(f"=== Discovery: {rep.company}" + (f"  (role function: {a.function})" if a.function else ""))
    if rep.note:
        print("\n" + rep.note)
        return
    for label, bucket in (("Recruiters / TA (route to process)", rep.recruiters),
                          ("Leaders (likely hiring manager or skip)", rep.leaders),
                          ("In-function peers", rep.peers)):
        print(f"\n{label}: {len(bucket)}")
        for d in bucket:
            flag = "  " if d.at_target else "? "
            print(f"  {flag}{d.name:24s} {d.title[:40]:40s} {('@ ' + d.company)[:24]:24s} {d.url}")
    if rep.roster:
        print(f"\nRoster fallback (small company; everyone the index confirms at {rep.company}): {len(rep.roster)}")
        for d in rep.roster:
            print(f"    {d.name:24s} {d.title[:40]:40s} [{d.role_class}] {d.url}")
    print("\n'?' = current company in the index does not match the target or its aliases; verify before reaching out.")
    print("\nThese are public profile URLs from a third-party index. Open them yourself; nothing here touched LinkedIn.")


def cmd_log(a):
    print(log(_conn(a.db), a.person, a.company, a.shape, a.channel, a.sent, a.status, a.note))


def cmd_outcomes(a):
    rows = report(_conn(a.db))
    if not rows:
        print("No outcomes logged yet. Use: python -m warmpath log \"Name\" --company X --shape cold --sent YYYY-MM-DD")
        return
    by = {}
    for r in rows:
        by[r[5]] = by.get(r[5], 0) + 1
    print(f"{len(rows)} threads. " + ", ".join(f"{k}={v}" for k, v in sorted(by.items())) + "\n")
    for person, company, shape, channel, sent, status, upd, note in rows:
        print(f"{sent}  {status:12s} {person:22s} @ {company:16s} {shape:16s} {channel:9s} {note}")


def main(argv=None):
    _load_dotenv()
    ap = argparse.ArgumentParser(prog="warmpath")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest"); s.add_argument("export"); s.add_argument("--me"); s.set_defaults(fn=cmd_ingest)
    s = sub.add_parser("demo"); s.add_argument("--out", default="demo/export"); s.set_defaults(fn=cmd_demo)
    s = sub.add_parser("people"); s.add_argument("--top", type=int, default=30); s.add_argument("--tier"); s.add_argument("--company"); s.set_defaults(fn=cmd_people)
    s = sub.add_parser("target"); s.add_argument("company"); s.add_argument("--alias", action="append", default=[])
    s.add_argument("--function", choices=["product", "cs", "gtm", "eng", "ops", "design"]); s.add_argument("--orbit", action="append", default=[])
    s.set_defaults(fn=cmd_target)
    s = sub.add_parser("draft"); s.add_argument("person"); s.add_argument("--target", required=True)
    s.add_argument("--alias", action="append", default=[]); s.add_argument("--function", choices=["product", "cs", "gtm", "eng", "ops", "design"])
    s.add_argument("--role"); s.add_argument("--hook"); s.add_argument("--channel", choices=["linkedin", "email"], default="linkedin")
    s.add_argument("--llm", action="store_true"); s.set_defaults(fn=cmd_draft)
    s = sub.add_parser("discover"); s.add_argument("company"); s.add_argument("--alias", action="append", default=[])
    s.add_argument("--function", choices=["product", "cs", "gtm", "eng", "ops", "design"])
    s.add_argument("--about", help="short description to disambiguate the company, e.g. 'synthetic-user AI startup, San Francisco'")
    s.add_argument("-n", type=int, default=8); s.set_defaults(fn=cmd_discover)

    s = sub.add_parser("log"); s.add_argument("person"); s.add_argument("--company", required=True)
    s.add_argument("--shape", choices=["spend", "ask-for-routing", "forward-note", "cold", "feedback", "other"])
    s.add_argument("--channel", choices=["linkedin", "email", "video", "other"]); s.add_argument("--sent", help="YYYY-MM-DD")
    s.add_argument("--status", choices=list(STATUSES)); s.add_argument("--note"); s.set_defaults(fn=cmd_log)
    s = sub.add_parser("outcomes"); s.set_defaults(fn=cmd_outcomes)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
