"""Local web UI. Standard library only, binds to 127.0.0.1, same code paths as the CLI.

  python -m warmpath serve                 http://127.0.0.1:8765, data/warmpath.db
  python -m warmpath serve --db data/demo.db --port 8765

Nothing here leaves the machine. The page is one HTML file (warmpath/ui.html) that
calls the JSON endpoints below. Ingest accepts a local path or a dropped ZIP; the ZIP is
written to data/ (gitignored) and parsed there.
"""

from __future__ import annotations

import json
import sqlite3
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .bridge import bridge
from .discover import _exa, discover
from .enrich import coverage, enrich_top
from .drafts import DraftInput, input_for, length_note, prompt_for, render
from .ingest import ingest
from .outcomes import STATUSES, due, log, report
from .score import score_all
from .targets import build_report, classify_role

UI = Path(__file__).with_name("ui.html")
FUNCTIONS = ["product", "cs", "gtm", "eng", "ops", "design"]


def _person(p) -> dict:
    return {"key": p.key, "name": p.name, "url": p.url, "company": p.company, "position": p.position,
            "connected_on": p.connected_on, "strength": round(p.strength), "tier": p.tier, "reasons": p.reasons,
            "sent": p.sent, "received": p.received, "last_msg": p.last_msg}


class App:
    def __init__(self, db: Path):
        self.db = db

    def conn(self) -> sqlite3.Connection | None:
        return sqlite3.connect(self.db) if self.db.exists() else None

    # ---- read endpoints
    def status(self) -> dict:
        c = self.conn()
        out = {"db": str(self.db), "ready": bool(c), "me": "", "tiers": {}, "total": 0, "exa": _exa() is not None, "llm": False}
        try:
            import anthropic  # noqa: F401
            out["llm"] = True
        except ImportError:
            pass
        if c:
            row = c.execute("SELECT value FROM meta WHERE key='me'").fetchone()
            out["me"] = row[0] if row else ""
            for p in score_all(c):
                out["tiers"][p.tier] = out["tiers"].get(p.tier, 0) + 1
                out["total"] += 1
            out["enrich"] = coverage(c)
        return out

    def bridge(self, q: dict) -> dict:
        c = self.conn()
        if not c:
            return {"error": "no database yet"}
        name, company = q.get("person", [""])[0].strip(), q.get("company", [""])[0].strip()
        if not name or not company:
            return {"error": "person and company required"}
        rep = bridge(c, name, company, top=int(q.get("top", ["8"])[0]))
        return {"target": name, "company": company, "note": rep.note, "scanned": rep.scanned, "coverage": coverage(c),
                "history": [j.d() for j in (rep.target.history if rep.target else [])][:8],
                "pairs": [{"person": _person(x.person), "bridge": x.bridge, "reasons": x.reasons, "verdict": x.verdict, "ask": x.ask} for x in rep.pairs]}

    def enrich(self, b: dict) -> dict:
        c = self.conn()
        if not c:
            return {"error": "no database yet"}
        try:
            stats = enrich_top(c, top=int(b.get("top") or 150), refresh=bool(b.get("refresh")), log=lambda *a: None)
        except SystemExit as e:
            return {"error": str(e)}
        return {"ok": True, "stats": stats, "coverage": coverage(c)}

    def people(self, q: dict) -> dict:
        c = self.conn()
        if not c:
            return {"error": "no database yet"}
        top = int(q.get("top", ["50"])[0]); tier = q.get("tier", [""])[0]; company = q.get("company", [""])[0].lower()
        out = []
        for p in score_all(c):
            if tier and p.tier != tier:
                continue
            if company and company not in (p.company or "").lower():
                continue
            out.append(_person(p))
            if len(out) >= top:
                break
        return {"people": out}

    def target(self, q: dict) -> dict:
        c = self.conn()
        if not c:
            return {"error": "no database yet"}
        company = q.get("company", [""])[0].strip()
        if not company:
            return {"error": "company required"}
        aliases = [a for a in q.get("alias", []) if a.strip()]
        orbit = [o for o in q.get("orbit", []) if o.strip()]
        fn = q.get("function", [""])[0] or None
        rep = build_report(c, company, aliases=aliases, role_function=fn, orbit=orbit)
        return {
            "company": rep.company, "aliases": rep.aliases, "function": fn,
            "matches": [{"person": _person(t.person), "role_class": t.role_class, "role_reason": t.role_reason,
                         "function_match": t.function_match, "verdict": t.verdict, "ask": t.ask, "weak_side": t.weak_side}
                        for t in rep.matches],
            "orbit": [{"company": oc, "person": _person(p)} for oc, p in rep.orbit[:12]],
        }

    def discover(self, q: dict) -> dict:
        company = q.get("company", [""])[0].strip()
        if not company:
            return {"error": "company required"}
        rep = discover(company, q.get("function", [""])[0] or None, per_bucket=int(q.get("n", ["8"])[0]),
                       aliases=[a for a in q.get("alias", []) if a.strip()], about=q.get("about", [""])[0])
        return {"company": rep.company, "note": rep.note,
                **{k: [asdict(d) for d in getattr(rep, k)] for k in ("recruiters", "leaders", "peers", "roster")}}

    def outcomes(self) -> dict:
        c = self.conn()
        if not c:
            return {"rows": [], "due": []}
        rows = report(c)
        keys = ["person", "company", "shape", "channel", "sent_on", "status", "updated_on", "note"]
        return {"rows": [dict(zip(keys, r)) for r in rows],
                "due": [{"person": p, "company": co, "days": d, "what": w} for p, co, d, w in due(rows)],
                "statuses": list(STATUSES)}

    # ---- write endpoints
    def ingest(self, body: dict) -> dict:
        path = body.get("path", "").strip()
        if not path:
            return {"error": "path required"}
        p = Path(path).expanduser()
        if not p.exists():
            return {"error": f"not found: {p}"}
        self.db.parent.mkdir(parents=True, exist_ok=True)
        try:
            stats = ingest(p, self.db, me=body.get("me") or None)
        except SystemExit as e:
            return {"error": str(e)}
        return {"ok": True, "stats": stats}

    def ingest_upload(self, data: bytes, me: str) -> dict:
        self.db.parent.mkdir(parents=True, exist_ok=True)
        dest = self.db.parent / "upload.zip"
        dest.write_bytes(data)
        try:
            stats = ingest(dest, self.db, me=me or None)
        except SystemExit as e:
            return {"error": str(e)}
        return {"ok": True, "stats": stats, "saved_to": str(dest)}

    def draft(self, b: dict) -> dict:
        c = self.conn()
        me = ""
        if c:
            row = c.execute("SELECT value FROM meta WHERE key='me'").fetchone()
            me = row[0] if row else ""
        extra = dict(me=me, me_line=b.get("me_line", ""), profile_url=b.get("url", ""),
                     findings=[f for f in b.get("findings", []) if f.strip()], via=b.get("via", ""), via_reason=b.get("via_reason", ""))
        person, target = b.get("person", "").strip(), b.get("target", "").strip()
        role, hook, channel = b.get("role", ""), b.get("hook", ""), b.get("channel", "linkedin")
        d = None; header = ""
        if c and person and target:
            rep = build_report(c, target, aliases=b.get("aliases", []), role_function=b.get("function") or None)
            ql = person.lower()
            m = [t for t in rep.matches if ql in t.person.name.lower()]
            if m:
                d = input_for(m[0], role, hook, channel, **extra)
                header = f"{m[0].verdict.upper()}: {m[0].ask}"
        if d is None and c and person and b.get("via"):
            ql = person.lower()
            mine = [p for p in score_all(c) if ql in p.name.lower()]
            if mine:
                p = mine[0]
                shape = b.get("shape") if b.get("shape") and b["shape"] != "auto" else "ask-for-intro"
                d = DraftInput(p.name, p.position, target, role, f"{p.tier}, score {p.strength:.0f}", shape, "Intro ask to a mutual.", hook, channel, **extra)
                header = f"INTRO via {p.name} to {b['via']}"
        if d is None:
            rc, rr, _ = classify_role(b.get("title", ""), b.get("function") or None)
            d = DraftInput(person or "there", b.get("title", ""), target, role, "not a connection; no history", "cold",
                           f"Cold outreach; seat: {rc} ({rr}).", hook, channel, role_class=rc, **extra)
            header = f"COLD (not in your network) · seat: {rc}"
        if b.get("shape") and b["shape"] != "auto":
            d.verdict = b["shape"]
        if b.get("prompt"):
            return {"header": header, "shape": d.verdict, "text": prompt_for(d), "note": "paste into any chat model"}
        fu = int(b.get("followup") or 0)
        text = render(d, bool(b.get("llm")), fu)
        return {"header": header, "shape": d.verdict, "followup": fu, "text": text, "note": length_note(text, channel)}

    def log(self, b: dict) -> dict:
        c = self.conn()
        if not c:
            return {"error": "no database yet"}
        if not b.get("person") or not b.get("company"):
            return {"error": "person and company required"}
        msg = log(c, b["person"], b["company"], b.get("shape") or None, b.get("channel") or None,
                  b.get("sent") or None, b.get("status") or None, b.get("note") or None)
        return {"ok": True, "message": msg}


def make_handler(app: App):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _json(self, obj, code=200):
            data = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path); q = parse_qs(u.query)
            try:
                if u.path in ("/", "/index.html"):
                    html = UI.read_bytes()
                    self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html))); self.end_headers(); self.wfile.write(html); return
                if u.path == "/api/status": return self._json(app.status())
                if u.path == "/api/people": return self._json(app.people(q))
                if u.path == "/api/target": return self._json(app.target(q))
                if u.path == "/api/discover": return self._json(app.discover(q))
                if u.path == "/api/outcomes": return self._json(app.outcomes())
                if u.path == "/api/bridge": return self._json(app.bridge(q))
                self._json({"error": "not found"}, 404)
            except Exception as e:  # surface, do not crash the server
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b""
            try:
                if u.path == "/api/ingest-upload":
                    return self._json(app.ingest_upload(raw, self.headers.get("X-Me", "")))
                body = json.loads(raw or b"{}")
                if u.path == "/api/ingest": return self._json(app.ingest(body))
                if u.path == "/api/draft": return self._json(app.draft(body))
                if u.path == "/api/log": return self._json(app.log(body))
                if u.path == "/api/enrich": return self._json(app.enrich(body))
                self._json({"error": "not found"}, 404)
            except Exception as e:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)
    return H


def serve(db: Path, port: int = 8765, open_browser: bool = True) -> None:
    app = App(db)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{port}"
    print(f"Warm Path UI at {url}  (db: {db}; local only; Ctrl-C to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
