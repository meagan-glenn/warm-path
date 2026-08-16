"""Outcome log: what was sent, to whom, in what shape, and what happened.

This is the data the scorer will eventually learn from, and the honest record for
the README. Stored in the same local SQLite database. Nothing leaves the machine.

  warmpath log "Ryan Boyd" --company Simile --shape cold --channel linkedin --sent 2026-08-15
  warmpath log "Ryan Boyd" --company Simile --status replied --note "answered the question, no mention of the role"
  warmpath outcomes
"""

from __future__ import annotations

import sqlite3
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS outcomes (
  id INTEGER PRIMARY KEY,
  person TEXT NOT NULL,
  company TEXT NOT NULL,
  shape TEXT,          -- spend / ask-for-routing / forward-note / cold / feedback / other
  channel TEXT,        -- linkedin / email / video / other
  sent_on TEXT,        -- ISO date
  status TEXT DEFAULT 'sent',  -- sent / replied / silent / intro-made / call-booked / rejected
  updated_on TEXT,
  note TEXT
);
"""

STATUSES = ("sent", "replied", "silent", "intro-made", "call-booked", "rejected")


def log(conn: sqlite3.Connection, person: str, company: str, shape: str | None, channel: str | None,
        sent_on: str | None, status: str | None, note: str | None) -> str:
    conn.executescript(SCHEMA)
    today = date.today().isoformat()
    row = conn.execute("SELECT id FROM outcomes WHERE lower(person)=lower(?) AND lower(company)=lower(?) ORDER BY id DESC LIMIT 1",
                       (person, company)).fetchone()
    if row and (status or note) and not sent_on:  # annotate or advance the existing thread
        conn.execute("UPDATE outcomes SET status=COALESCE(?, status), updated_on=?, note=COALESCE(?, note) WHERE id=?",
                     (status, today, note, row[0]))
        conn.commit()
        return f"updated {person} @ {company}: {status or 'note added'}"
    conn.execute("INSERT INTO outcomes (person, company, shape, channel, sent_on, status, updated_on, note) VALUES (?,?,?,?,?,?,?,?)",
                 (person, company, shape or "other", channel or "linkedin", sent_on or today, status or "sent", today, note))
    conn.commit()
    return f"logged {person} @ {company}: {shape or 'other'} via {channel or 'linkedin'}, {status or 'sent'} {sent_on or today}"


FOLLOWUP_1 = 5    # days after send: one bump (the single biggest lift in every follow-up corpus)
FOLLOWUP_2 = 12   # days: close the loop, then stop; a third follow-up is noise


def report(conn: sqlite3.Connection) -> list[tuple]:
    conn.executescript(SCHEMA)
    return conn.execute("SELECT person, company, shape, channel, sent_on, status, updated_on, COALESCE(note,'') FROM outcomes ORDER BY sent_on, id").fetchall()


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
