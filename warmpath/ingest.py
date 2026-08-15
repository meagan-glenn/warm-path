"""Parse a LinkedIn data export (ZIP or unzipped folder) into a local SQLite database.

Files used, all optional except Connections.csv:
  Connections.csv              1st-degree connections (the spine)
  messages.csv                 full DM history, used for relationship strength
  Positions.csv                the user's own work history, used for overlap
  Invitations.csv              who invited whom
  Recommendations_*.csv        written recommendations, strongest reciprocity signal
  Endorsement_*_Info.csv       skill endorsements, weak reciprocity signal
  Education.csv                the user's schools, reserved for the alumni layer

Everything stays local. Message content is stored only as per-person aggregates.
"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

csv.field_size_limit(sys.maxsize)

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS people (
  key TEXT PRIMARY KEY,          -- normalized profile slug, or name if no URL
  first TEXT, last TEXT, name TEXT, url TEXT, email TEXT,
  company TEXT, position TEXT, connected_on TEXT
);
CREATE TABLE IF NOT EXISTS msg_agg (
  key TEXT PRIMARY KEY,
  sent INTEGER, received INTEGER,
  first_msg TEXT, last_msg TEXT,
  active_days INTEGER,           -- distinct days with any message
  capped_msgs INTEGER            -- messages counted with a per-day cap, dampens support bursts
);
CREATE TABLE IF NOT EXISTS invitations (key TEXT, direction TEXT, sent_at TEXT, has_note INTEGER);
CREATE TABLE IF NOT EXISTS recommendations (key TEXT, direction TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS endorsements (key TEXT, direction TEXT, count INTEGER);
CREATE TABLE IF NOT EXISTS my_positions (company TEXT, title TEXT, started TEXT, finished TEXT);
CREATE TABLE IF NOT EXISTS my_education (school TEXT, started TEXT, finished TEXT);
"""

PER_DAY_CAP = 8  # messages per person per day that count toward strength


def norm_key(url: str, name: str) -> str:
    """Stable key for a person: the profile slug when we have it, else the lowercased name."""
    if url:
        m = re.search(r"linkedin\.com/in/([^/?#]+)", url)
        if m:
            return m.group(1).lower().rstrip("/")
    return "name:" + re.sub(r"\s+", " ", name.strip().lower())


def _read_csv_text(text: str) -> list[dict]:
    """Read a LinkedIn CSV, tolerating the 'Notes:' preamble above the header."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].startswith("Notes:"):
        # Connections.csv carries a preamble about withheld emails; the real header follows a blank line.
        start = next((i for i, l in enumerate(lines[:30]) if l.startswith("First Name,")), 0)
    return list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))


class Export:
    """Uniform access to the files inside a ZIP or a folder."""

    def __init__(self, path: Path):
        self.path = path
        self.zip = zipfile.ZipFile(path) if path.is_file() else None

    def read(self, name: str) -> list[dict] | None:
        try:
            if self.zip:
                match = next((n for n in self.zip.namelist() if n.split("/")[-1] == name), None)
                if not match:
                    return None
                text = self.zip.read(match).decode("utf-8-sig")
            else:
                p = self.path / name
                if not p.exists():
                    return None
                text = p.read_text(encoding="utf-8-sig")
        except (KeyError, OSError):
            return None
        return _read_csv_text(text)


def _parse_date(s: str) -> str | None:
    """Return ISO date (YYYY-MM-DD) or None. LinkedIn uses several formats across files."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S", "%d %b %Y", "%m/%d/%y, %I:%M %p", "%Y/%m/%d %H:%M:%S %Z", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def ingest(export_path: Path, db_path: Path, me: str | None = None) -> dict:
    ex = Export(export_path)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    for t in ("people", "msg_agg", "invitations", "recommendations", "endorsements", "my_positions", "my_education"):
        conn.execute(f"DELETE FROM {t}")
    stats: dict = {}

    # Who am I? Needed to split sent vs received in messages.
    if not me:
        prof = ex.read("Profile.csv")
        if prof:
            me = f"{prof[0].get('First Name','')} {prof[0].get('Last Name','')}".strip()
    if not me:
        raise SystemExit("Could not determine your name from Profile.csv; pass --me 'First Last'.")
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('me', ?)", (me,))

    # Connections
    rows = ex.read("Connections.csv")
    if not rows:
        raise SystemExit("Connections.csv not found in export.")
    name_to_key: dict[str, str] = {}
    for r in rows:
        name = f"{r.get('First Name','')} {r.get('Last Name','')}".strip()
        key = norm_key(r.get("URL", ""), name)
        name_to_key.setdefault(name.lower(), key)
        conn.execute(
            "INSERT OR REPLACE INTO people VALUES (?,?,?,?,?,?,?,?,?)",
            (key, r.get("First Name", ""), r.get("Last Name", ""), name, r.get("URL", ""),
             r.get("Email Address", ""), (r.get("Company") or "").strip(), (r.get("Position") or "").strip(),
             _parse_date(r.get("Connected On", ""))),
        )
    stats["connections"] = len(rows)

    def key_for(name: str, url: str = "") -> str:
        k = norm_key(url, name)
        if url and k in name_to_key.values():
            return k
        return name_to_key.get(name.strip().lower(), k)

    # Messages -> per-person aggregates. Content is read, never stored.
    msgs = ex.read("messages.csv")
    if msgs:
        agg = defaultdict(lambda: {"sent": 0, "received": 0, "days": defaultdict(int), "first": None, "last": None})
        for m in msgs:
            if m.get("IS MESSAGE DRAFT", "").lower() == "true":
                continue
            d = _parse_date(m.get("DATE", ""))
            frm = (m.get("FROM") or "").strip()
            if frm == me:
                tos = [t.strip() for t in (m.get("TO") or "").split(",") if t.strip()]
                urls = [u.strip() for u in (m.get("RECIPIENT PROFILE URLS") or "").split(",")]
                if len(tos) != 1:
                    continue  # group threads say little about a pair
                k = key_for(tos[0], urls[0] if urls else "")
                a = agg[k]; a["sent"] += 1
            else:
                k = key_for(frm, m.get("SENDER PROFILE URL", ""))
                a = agg[k]; a["received"] += 1
            if d:
                a["days"][d] += 1
                a["first"] = min(a["first"] or d, d)
                a["last"] = max(a["last"] or d, d)
        for k, a in agg.items():
            capped = sum(min(n, PER_DAY_CAP) for n in a["days"].values())
            conn.execute("INSERT OR REPLACE INTO msg_agg VALUES (?,?,?,?,?,?,?)",
                         (k, a["sent"], a["received"], a["first"], a["last"], len(a["days"]), capped))
        stats["messages"] = len(msgs)
        stats["people_messaged"] = len(agg)

    inv = ex.read("Invitations.csv")
    if inv:
        for r in inv:
            if r.get("Direction") == "OUTGOING":
                k = key_for(r.get("To", ""), r.get("inviteeProfileUrl", ""))
            else:
                k = key_for(r.get("From", ""), r.get("inviterProfileUrl", ""))
            conn.execute("INSERT INTO invitations VALUES (?,?,?,?)",
                         (k, r.get("Direction"), _parse_date(r.get("Sent At", "")), 1 if (r.get("Message") or "").strip() else 0))
        stats["invitations"] = len(inv)

    for fname, direction in (("Recommendations_Given.csv", "given"), ("Recommendations_Received.csv", "received")):
        recs = ex.read(fname)
        for r in recs or []:
            name = f"{r.get('First Name','')} {r.get('Last Name','')}".strip()
            conn.execute("INSERT INTO recommendations VALUES (?,?,?)", (key_for(name), direction, _parse_date(r.get("Creation Date", ""))))

    for fname, direction, fn, ln, url in (
        ("Endorsement_Given_Info.csv", "given", "Endorsee First Name", "Endorsee Last Name", "Endorsee Public Url"),
        ("Endorsement_Received_Info.csv", "received", "Endorser First Name", "Endorser Last Name", "Endorser Public Url"),
    ):
        ends = ex.read(fname)
        if ends:
            counts: dict[str, int] = defaultdict(int)
            for r in ends:
                counts[key_for(f"{r.get(fn,'')} {r.get(ln,'')}".strip(), r.get(url, ""))] += 1
            for k, n in counts.items():
                conn.execute("INSERT INTO endorsements VALUES (?,?,?)", (k, direction, n))

    pos = ex.read("Positions.csv")
    for r in pos or []:
        conn.execute("INSERT INTO my_positions VALUES (?,?,?,?)",
                     (r.get("Company Name", ""), r.get("Title", ""), r.get("Started On", ""), r.get("Finished On", "")))
    edu = ex.read("Education.csv")
    for r in edu or []:
        conn.execute("INSERT INTO my_education VALUES (?,?,?)", (r.get("School Name", ""), r.get("Start Date", ""), r.get("End Date", "")))

    conn.commit()
    conn.close()
    return stats
