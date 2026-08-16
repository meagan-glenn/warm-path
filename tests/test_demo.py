"""Smoke test over the synthetic export. Run: python -m unittest discover tests"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from warmpath.demo import build
from warmpath.ingest import ingest
from warmpath.score import score_all
from warmpath.targets import build_report


class DemoSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        build(root / "export")
        ingest(root / "export", root / "demo.db")
        cls.conn = sqlite3.connect(root / "demo.db")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        cls.tmp.cleanup()

    def test_ingest_counts(self):
        n = self.conn.execute("SELECT count(*) FROM people").fetchone()[0]
        self.assertEqual(n, 122)
        self.assertEqual(self.conn.execute("SELECT value FROM meta WHERE key='me'").fetchone()[0], "Sam Rivera")

    def test_tiers(self):
        by = {}
        for p in score_all(self.conn):
            by[p.name] = p
        self.assertEqual(by["Priya Okafor"].tier, "strong")
        self.assertEqual(by["Jordan Lindqvist"].tier, "cold-unanswered")
        self.assertEqual(by["Tobias Whitfield"].tier, "cold-untested")
        self.assertIn(by["Elena Castellano"].tier, ("weak", "warm"))

    def test_warm_case(self):
        rep = build_report(self.conn, "Corvid AI", role_function="cs")
        v = {m.person.name: m.verdict for m in rep.matches}
        self.assertEqual(v["Priya Okafor"], "spend")
        self.assertEqual(v["Aisha Haddad"], "ask-for-routing")
        self.assertEqual(v["Jordan Lindqvist"], "skip")
        self.assertEqual(v["Marcus Nakamura"], "skip")

    def test_cold_case(self):
        rep = build_report(self.conn, "Halberd", role_function="cs")
        self.assertEqual(len(rep.matches), 2)
        self.assertNotIn("spend", {m.verdict for m in rep.matches})

    def test_zero_case_and_alias(self):
        self.assertEqual(build_report(self.conn, "Tessellate", role_function="cs").matches, [])
        rep = build_report(self.conn, "Tessellate", aliases=["Fractal Ops"], role_function="cs", orbit=["Meridian"])
        self.assertEqual([m.person.name for m in rep.matches], ["Diego Adeyemi"])
        self.assertTrue(any(p.name == "Wesley Marchetti" for _, p in rep.orbit))


if __name__ == "__main__":
    unittest.main()


class Drafts(unittest.TestCase):
    def _d(self, verdict, **kw):
        from warmpath.drafts import DraftInput
        return DraftInput("Elena Castellano", "CSM", "Corvid AI", "CS Lead", "weak", verdict, "x", "your post stuck with me",
                          me="Sam Rivera", me_line="a CS-turned-product lead", profile_url="https://x", **kw)

    def test_shapes_under_soft_limit(self):
        from warmpath.drafts import HARD_LIMIT, SOFT_LIMIT, scaffold
        for v in ("spend", "cold", "forward-note", "feedback"):
            body = scaffold(self._d(v, findings=["a", "b", "c"])).split("\n---")[0]
            self.assertLessEqual(len(body), SOFT_LIMIT + 60, v)   # scaffold plus a short hook stays in the band
            self.assertLessEqual(len(body), HARD_LIMIT, v)

    def test_no_em_dashes(self):
        from warmpath.drafts import STYLE, followup, scaffold
        for v in ("spend", "ask-for-routing", "forward-note", "cold", "feedback", "blurb"):
            self.assertNotIn("—", scaffold(self._d(v)))
        self.assertNotIn("—", followup(self._d("cold"), 1) + followup(self._d("cold"), 2) + STYLE)

    def test_blurb_is_third_person_with_link(self):
        from warmpath.drafts import blurb
        b = blurb(self._d("ask-for-routing"))
        self.assertTrue(b.startswith("Sam Rivera is "))
        self.assertIn("https://x", b)

    def test_followup_due(self):
        from datetime import date
        from warmpath.outcomes import due
        rows = [("A", "X", "cold", "linkedin", "2026-08-01", "sent", "", ""),
                ("B", "X", "cold", "linkedin", "2026-08-09", "sent", "", ""),
                ("C", "X", "cold", "linkedin", "2026-08-01", "replied", "", "")]
        d = due(rows, today=date(2026, 8, 15))
        self.assertEqual([(p, w.split(" (")[0]) for p, _, _, w in d], [("A", "close the loop"), ("B", "one bump")])


class SeatAwareCold(unittest.TestCase):
    def test_cold_varies_by_seat(self):
        from warmpath.drafts import DraftInput, scaffold
        outs = {}
        for rc in ("route", "champion", "peer", "other"):
            d = DraftInput("Angela L.", "Recruiting", "Wispr Flow", "Product Lead", "none", "cold", "x", "on Tuesday", role_class=rc, me_line="a PM", profile_url="https://x")
            outs[rc] = scaffold(d)
        self.assertEqual(len(set(outs.values())), 4)
        self.assertNotIn("15 minutes", outs["route"])
        self.assertIn("still open", outs["route"])
        self.assertIn("15 minutes", outs["peer"])
        self.assertIn("who owns", outs["other"])


class Bridge(unittest.TestCase):
    def test_demo_bridge_offline(self):
        import os
        from warmpath.bridge import bridge
        from warmpath.demo import seed_enrichment
        # force offline: no EXA key
        saved = os.environ.pop("EXA_API_KEY", None)
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            build(root / "export"); ingest(root / "export", root / "demo.db")
            seed_enrichment(root / "demo.db")
            rep = bridge(sqlite3.connect(root / "demo.db"), "Nora Fitzgerald", "Corvid AI")
            names = [x.person.name for x in rep.pairs]
            self.assertIn("Hana Kowalski", names)
            self.assertIn("Wesley Marchetti", names)
            self.assertNotIn("Diego Adeyemi", names)   # no overlap
            self.assertEqual({x.verdict for x in rep.pairs if x.person.name == "Hana Kowalski"}, {"ask-for-intro"})
        finally:
            tmp.cleanup()
            if saved: os.environ["EXA_API_KEY"] = saved

    def test_overlap_scoring(self):
        from warmpath.bridge import _score_pair
        from warmpath.enrich import Job, Profile
        me = Profile("A", "X", "", "", [Job("Amplitude", "PM", "2018-01-01", "2021-01-01")])
        t = Profile("B", "Y", "", "", [Job("Amplitude", "Growth", "2019-01-01", "2022-01-01")])
        b, r = _score_pair(me, t)
        self.assertGreaterEqual(b, 30)
        self.assertTrue(any("Amplitude" in x for x in r))
        none = Profile("C", "Z", "", "", [Job("Other", "x", "2010-01-01", "2012-01-01")])
        self.assertEqual(_score_pair(none, t)[0], 0)
