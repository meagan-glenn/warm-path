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
