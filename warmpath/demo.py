"""Synthetic LinkedIn export for demos, tests, and screencasts.

Every name, company, and message here is invented. The generator is deterministic
(seeded), so the same files come out every time and the README numbers stay true.

The persona is Sam Rivera, a customer-success-turned-product lead who has applied to
three fictional companies that mirror the three real cases the tool was built on:

  Corvid AI    warm case: a strong ex-colleague in the right seat, plus recruiters who
               never answered, plus a thin peer connection
  Halberd      cold case: two connections, both cold, neither useful
  Tessellate   zero case: nobody there under that name; one warm person under the old
               name "Fractal Ops" (rename), and a couple of strong people in the orbit

  python -m warmpath demo            writes demo/export/*.csv and ingests into data/demo.db
"""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

ME = ("Sam", "Rivera")
ME_URL = "https://www.linkedin.com/in/sam-rivera-demo"
TODAY = datetime(2026, 8, 15, 12, 0, 0)  # fixed so recency scores are stable

FIRST = ["Priya", "Jordan", "Marcus", "Elena", "Tobias", "Aisha", "Noah", "Ingrid", "Diego", "Hana", "Wesley", "Farah",
         "Leo", "Maren", "Kofi", "Sofia", "Rafael", "Nadia", "Owen", "Yuki", "Callum", "Amara", "Theo", "Lucia", "Emeka",
         "Greta", "Idris", "Bea", "Mateo", "Zara", "Felix", "Anika", "Rowan", "Sanaa", "Jonas", "Talia", "Arjun", "Mila",
         "Cyrus", "Petra", "Dev", "Wren", "Ezra", "Leila", "Otto", "Nia", "Ravi", "Iris", "Bram", "Sloane"]
LAST = ["Okafor", "Lindqvist", "Nakamura", "Castellano", "Whitfield", "Haddad", "Brennan", "Sorensen", "Adeyemi", "Kowalski",
        "Marchetti", "Osei", "Vance", "Petrov", "Delgado", "Ferreira", "Iyer", "Halvorsen", "Quintero", "Abernathy",
        "Moreau", "Tanaka", "Sallow", "Eriksen", "Bakshi", "Novak", "Grimaldi", "Achebe", "Lockhart", "Duarte"]

# (company, list of positions). Companies are fictional. Titles are chosen to exercise the classifier.
COMPANIES = {
    "Corvid AI": ["Head of Customer Success", "Technical Recruiter", "Senior Talent Partner", "Customer Success Manager",
                  "Software Engineer", "Account Executive", "Product Manager", "Onboarding Specialist"],
    "Halberd": ["Staff Engineer", "Marketing Manager"],
    "Fractal Ops": ["Head of Deployments"],
    "Northwind Ventures": ["Partner", "Platform Lead", "Principal"],
    "Meridian": ["VP Customer Experience", "Solutions Engineer", "Director of Product", "Customer Success Lead"],
    "Brightwater": ["Product Manager", "Senior Customer Success Manager", "Engineering Manager", "VP Sales", "Designer",
                    "Head of Support", "Data Analyst", "Account Manager"],
    "Nimbus Labs": ["Co-founder & CEO", "Product Lead", "Growth Manager", "Senior Engineer", "Chief of Staff", "Recruiter"],
    "Larkspur Health": ["Product Manager", "Customer Success Manager", "Sales Director"],
    "Ferrous": ["Founder", "Head of Product", "Engineer"],
    "Quillon": ["Senior Product Manager", "UX Researcher", "Solutions Architect"],
    "Bluecap Software": ["Customer Success Director", "SDR", "Implementation Manager", "Product Marketing Manager"],
    "Orenda": ["Director of Operations", "Program Manager"],
    "Sable & Finch": ["Consultant", "Partner"],
    "Ridgeline Robotics": ["Mechanical Engineer", "Product Manager", "Recruiter"],
    "Vantage Point Media": ["Editor", "Growth Lead"],
    "Kestrel Analytics": ["Data Scientist", "Head of Data", "Analyst"],
    "Tidewell": ["Nurse Manager", "Operations Coordinator"],
    "Pinecone Coffee Co": ["Owner"],
    "Freelance": ["Product Consultant", "Fractional CMO", "Designer"],
}

MY_POSITIONS = [
    ("Sam Rivera Consulting", "Fractional Head of Product", "Mar 2024", ""),
    ("Nimbus Labs", "Product Lead", "Jun 2022", "Feb 2024"),
    ("Brightwater", "Senior Customer Success Manager", "Jan 2019", "May 2022"),
    ("Bluecap Software", "Customer Success Manager", "Aug 2016", "Dec 2018"),
]
MY_EDUCATION = [("Coastal State University", "Sep 2010", "May 2014", "", "BA, Communication", "")]

FILLER = ["Thanks for the intro last week, that was really helpful.", "Congrats on the launch!", "Are you around for a call Thursday?",
          "Sending over the doc now.", "Ha, exactly.", "Let me check with the team and get back to you.", "That makes sense, thank you.",
          "Would love to catch up when you are in town.", "Sure, works for me.", "Saw your post, great points on activation.",
          "Do you have a template for that?", "Yes, sent it over.", "Appreciate it!", "Following up on this.", "Quick question about the onboarding flow."]


def _slug(first: str, last: str) -> str:
    return f"https://www.linkedin.com/in/{first.lower()}-{last.lower()}-demo"


def _dt(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S UTC")


def build(out: Path, seed: int = 7) -> dict:
    """Write the synthetic export into `out` (a folder). Returns some counts for the CLI to print."""
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Connections. Named people first (the cases), then random filler.
    people: list[dict] = []
    used = set()

    def person(first, last, company, position, connected_on, profile="untested", **kw):
        used.add((first, last))
        p = dict(first=first, last=last, url=_slug(first, last), company=company, position=position,
                 connected_on=connected_on, profile=profile, **kw)
        people.append(p)
        return p

    # Corvid AI: the warm case
    person("Priya", "Okafor", "Corvid AI", "Head of Customer Success", "2019-04-02", profile="strong", colleague=True, recommended=True)
    person("Jordan", "Lindqvist", "Corvid AI", "Technical Recruiter", "2026-07-30", profile="unanswered")
    person("Marcus", "Nakamura", "Corvid AI", "Senior Talent Partner", "2026-08-01", profile="unanswered")
    person("Elena", "Castellano", "Corvid AI", "Customer Success Manager", "2025-11-12", profile="weak")
    person("Tobias", "Whitfield", "Corvid AI", "Software Engineer", "2023-02-18", profile="untested")
    person("Aisha", "Haddad", "Corvid AI", "Account Executive", "2024-06-05", profile="warm")
    # Halberd: the cold case
    person("Noah", "Brennan", "Halberd", "Staff Engineer", "2022-09-14", profile="untested")
    person("Ingrid", "Sorensen", "Halberd", "Marketing Manager", "2026-08-03", profile="unanswered")
    # Tessellate: zero under the new name; one warm under the old name, orbit at Northwind and Meridian
    person("Diego", "Adeyemi", "Fractal Ops", "Head of Deployments", "2021-05-20", profile="warm", colleague=True)
    person("Hana", "Kowalski", "Northwind Ventures", "Platform Lead", "2020-10-01", profile="strong", recommended=True)
    person("Wesley", "Marchetti", "Meridian", "VP Customer Experience", "2019-08-11", profile="strong", colleague=True)
    person("Farah", "Osei", "Meridian", "Solutions Engineer", "2024-01-09", profile="weak")

    # Filler: 110 more people across the other companies
    pool = [(c, t) for c, ts in COMPANIES.items() for t in ts if c not in ("Corvid AI", "Halberd", "Fractal Ops")]
    profiles = ["strong"] * 6 + ["warm"] * 18 + ["weak"] * 24 + ["unanswered"] * 10 + ["untested"] * 52
    rng.shuffle(profiles)
    for prof in profiles:
        while True:
            f, l = rng.choice(FIRST), rng.choice(LAST)
            if (f, l) not in used:
                break
        c, t = rng.choice(pool)
        d = TODAY - timedelta(days=rng.randint(30, 3000))
        person(f, l, c, t, d.strftime("%Y-%m-%d"), profile=prof, colleague=(c in ("Brightwater", "Nimbus Labs", "Bluecap Software") and rng.random() < 0.6))

    with open(out / "Connections.csv", "w", newline="", encoding="utf-8") as fh:
        fh.write("Notes:\n\"When exporting your connection data, you may notice that some of the email addresses are missing. (Synthetic demo file.)\"\n\n")
        w = csv.writer(fh)
        w.writerow(["First Name", "Last Name", "URL", "Email Address", "Company", "Position", "Connected On"])
        for p in people:
            # LinkedIn writes dates as "02 Apr 2019"
            d = datetime.strptime(p["connected_on"], "%Y-%m-%d").strftime("%d %b %Y")
            w.writerow([p["first"], p["last"], p["url"], "", p["company"], p["position"], d])

    # 2. Messages. Shape per profile:
    #   strong      two-way, 40-120 msgs, span 2-5 years, last within 60 days
    #   warm        two-way, 8-25 msgs, span 6-24 months, last within a year
    #   weak        two-way, 2-4 msgs, one short window, 1-3 years ago
    #   unanswered  1-2 sent by me, nothing back, recent
    #   untested    no messages
    me_name = f"{ME[0]} {ME[1]}"
    rows = []
    n_msgs = 0
    for i, p in enumerate(people):
        prof = p["profile"]
        name = f"{p['first']} {p['last']}"
        conv = f"demo-conv-{i:04d}"
        if prof == "untested":
            continue
        if prof == "strong":
            n, span, last_ago = rng.randint(40, 120), rng.randint(700, 1800), rng.randint(3, 60)
        elif prof == "warm":
            n, span, last_ago = rng.randint(8, 25), rng.randint(180, 720), rng.randint(20, 365)
        elif prof == "weak":
            n, span, last_ago = rng.randint(2, 4), rng.randint(0, 5), rng.randint(365, 1100)
        else:  # unanswered
            n, span, last_ago = rng.randint(1, 2), rng.randint(0, 3), rng.randint(2, 30)
        end = TODAY - timedelta(days=last_ago)
        start = end - timedelta(days=span)
        for j in range(n):
            t = start + (end - start) * (j / max(n - 1, 1)) + timedelta(minutes=rng.randint(0, 600))
            mine = True if prof == "unanswered" else (j % 2 == 0 if rng.random() < 0.8 else rng.random() < 0.5)
            frm, frm_url, to, to_url = (me_name, ME_URL, name, p["url"]) if mine else (name, p["url"], me_name, ME_URL)
            rows.append([conv, "", frm, frm_url, to, to_url, _dt(t), "", rng.choice(FILLER), "INBOX", "", "false", "false"])
            n_msgs += 1
    # One group thread, which the ingester should ignore for pair scoring
    g = people[0]; h = people[9]
    rows.append(["demo-conv-group", "Offsite planning", me_name, ME_URL, f"{g['first']} {g['last']},{h['first']} {h['last']}",
                 f"{g['url']},{h['url']}", _dt(TODAY - timedelta(days=200)), "", "Who is bringing the projector?", "INBOX", "", "false", "false"])
    rows.sort(key=lambda r: r[6], reverse=True)
    with open(out / "messages.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(["CONVERSATION ID", "CONVERSATION TITLE", "FROM", "SENDER PROFILE URL", "TO", "RECIPIENT PROFILE URLS", "DATE",
                    "SUBJECT", "CONTENT", "FOLDER", "ATTACHMENTS", "IS MESSAGE DRAFT", "IS CONVERSATION DRAFT"])
        w.writerows(rows)

    # 3. Invitations: unanswered people got a note from me; a third of the rest invited me.
    with open(out / "Invitations.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["From", "To", "Sent At", "Message", "Direction", "inviterProfileUrl", "inviteeProfileUrl"])
        for p in people:
            name = f"{p['first']} {p['last']}"
            d = datetime.strptime(p["connected_on"], "%Y-%m-%d") - timedelta(days=rng.randint(0, 5))
            sent = d.strftime("%-m/%-d/%y, %-I:%M %p")
            if p["profile"] == "unanswered":
                w.writerow([me_name, name, sent, "Hi, I just applied for the CS Lead role and wanted to put a face to the name.", "OUTGOING", ME_URL, p["url"]])
            elif rng.random() < 0.35:
                w.writerow([name, me_name, sent, rng.choice(["", "", "Enjoyed your talk, would love to connect."]), "INCOMING", p["url"], ME_URL])
            elif rng.random() < 0.5:
                w.writerow([me_name, name, sent, "", "OUTGOING", ME_URL, p["url"]])

    # 4. Recommendations, both directions, for the flagged people.
    for fname in ("Recommendations_Given.csv", "Recommendations_Received.csv"):
        with open(out / fname, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["First Name", "Last Name", "Company", "Job Title", "Text", "Creation Date", "Status"])
            for p in people:
                if p.get("recommended"):
                    w.writerow([p["first"], p["last"], p["company"], p["position"], "Worked together for years. (Synthetic text.)",
                                "2023-06-01 10:00:00 UTC", "VISIBLE"])

    # 5. Endorsements: strong and warm people trade a few skills.
    for fname, cols in (("Endorsement_Given_Info.csv", ["Endorsee First Name", "Endorsee Last Name", "Endorsee Public Url"]),
                        ("Endorsement_Received_Info.csv", ["Endorser First Name", "Endorser Last Name", "Endorser Public Url"])):
        with open(out / fname, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["Endorsement Date", "Skill Name", *cols, "Endorsement Status"])
            for p in people:
                if p["profile"] in ("strong", "warm") and rng.random() < 0.6:
                    for skill in rng.sample(["Customer Success", "Product Management", "Onboarding", "SaaS", "Leadership"], rng.randint(1, 3)):
                        w.writerow(["2024/05/24 18:04:01 UTC", skill, p["first"], p["last"], p["url"].replace("https://", ""), "ACCEPTED"])

    # 6. Me
    with open(out / "Positions.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["Company Name", "Title", "Description", "Location", "Started On", "Finished On"])
        for c, t, s, e in MY_POSITIONS:
            w.writerow([c, t, "(Synthetic.)", "Remote", s, e])
    with open(out / "Education.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["School Name", "Start Date", "End Date", "Notes", "Degree Name", "Activities"])
        w.writerows(MY_EDUCATION)
    with open(out / "Profile.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["First Name", "Last Name", "Maiden Name", "Address", "Birth Date", "Headline", "Summary", "Industry", "Zip Code",
                    "Geo Location", "Twitter Handles", "Websites", "Instant Messengers"])
        w.writerow([ME[0], ME[1], "", "", "", "Fractional Head of Product (synthetic demo persona)", "", "Software", "", "San Francisco Bay Area", "", "", ""])

    return {"connections": len(people), "messages": n_msgs, "companies": len({p["company"] for p in people})}


# Work histories for the bridge demo. Seeded straight into the enrich table after ingest, so
# `bridge "Nora Fitzgerald" --company "Corvid AI"` works with no Exa key. All invented.
DEMO_HISTORIES = {
    "priya-okafor-demo":     [("Corvid AI", "Head of Customer Success", "2022-06-01", None), ("Brightwater", "Customer Success Manager", "2018-03-01", "2022-05-01")],
    "hana-kowalski-demo":    [("Northwind Ventures", "Platform Lead", "2020-10-01", None), ("Meridian", "Head of Customer Success", "2017-02-01", "2020-09-01")],
    "wesley-marchetti-demo": [("Meridian", "VP Customer Experience", "2019-08-01", None), ("Brightwater", "Director of Support", "2016-01-01", "2019-07-01")],
    "diego-adeyemi-demo":    [("Fractal Ops", "Head of Deployments", "2021-05-01", None), ("Quillon", "Solutions Architect", "2018-01-01", "2021-04-01")],
    "aisha-haddad-demo":     [("Corvid AI", "Account Executive", "2024-06-01", None), ("Bluecap Software", "SDR", "2021-01-01", "2024-05-01")],
}
DEMO_TARGETS = {
    # a VP Product at Corvid AI who is not in Sam's network: bridge should find Hana (Meridian 2018-2020) and Wesley (Meridian 2019-2020)
    "Nora Fitzgerald @ Corvid AI": [("Corvid AI", "VP Product", "2021-03-01", None), ("Meridian", "Director of Product", "2018-01-01", "2021-02-01"), ("Kestrel Analytics", "Product Manager", "2014-06-01", "2017-12-01")],
}


def seed_enrichment(db_path: Path) -> None:
    import json
    import sqlite3
    from .enrich import SCHEMA
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    for key, jobs in DEMO_HISTORIES.items():
        row = conn.execute("SELECT name, company, url FROM people WHERE key=?", (key,)).fetchone()
        if not row:
            continue
        hist = [{"company": c, "title": t, "from": f, "to": e} for c, t, f, e in jobs]
        conn.execute("INSERT OR REPLACE INTO enrich VALUES (?,?,?,?,?,?,?,?)", (key, row[0], row[1], row[2], "San Francisco Bay Area", json.dumps(hist), "high", "2026-08-15"))
    for label, jobs in DEMO_TARGETS.items():
        name, company = [x.strip() for x in label.split("@")]
        hist = [{"company": c, "title": t, "from": f, "to": e} for c, t, f, e in jobs]
        conn.execute("INSERT OR REPLACE INTO enrich VALUES (?,?,?,?,?,?,?,?)",
                     ("target:" + name.lower().replace(" ", "-") + "@" + company.lower().replace(" ", "-"), name, company, "", "San Francisco Bay Area", json.dumps(hist), "high", "2026-08-15"))
    conn.commit(); conn.close()
