"""Phase 6/7 — the local dashboard + Correct/Predict/Ask (stdlib HTTP server, 127.0.0.1 only).

Run: python -m radbrain.web [--port 8650]
Security: binds to 127.0.0.1; rejects any Host header that is not localhost/127.0.0.1 (DNS rebinding); every POST
needs the header X-RadBrain: 1 (a cross-site page cannot send it without CORS, which this server never grants).
No external assets: charts are inline SVG drawn by the page's own script.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import config, diff, engine, evaluate, library, llm, miner, pipeline, signers_auto, taxonomy

STATIC = Path(__file__).with_name("static")
_lock = threading.Lock()


def overview(con) -> dict:
    counts = library.counts(con)
    ev = evaluate.latest(con)
    runs = [dict(r) for r in con.execute("SELECT at, pairs, rules, new_rules, synthetic FROM mine_runs ORDER BY id "
                                         "DESC LIMIT 30")]
    synth = con.execute("SELECT COUNT(*) FROM captures WHERE synthetic=1").fetchone()[0]
    real = con.execute("SELECT COUNT(*) FROM captures WHERE synthetic=0").fetchone()[0]
    brains = {}
    for c in config.CODES:
        real_pairs = con.execute("SELECT COUNT(*) FROM captures WHERE signer=? AND kind='pair' AND synthetic=0",
                                 (c,)).fetchone()[0]
        brains[c] = {"role": config.ROLES[c], **counts.get(c, {}), "real_pairs": real_pairs,
                     "live": real_pairs >= config.LIVE_AT_PAIRS,
                     "rules": con.execute("SELECT COUNT(*) FROM rules WHERE signer=?", (c,)).fetchone()[0]}
    return {"brains": brains, "unassigned": counts.get("unassigned"), "targets": {"pairs": config.TARGET_PAIRS,
            "finals": config.TARGET_FINALS, "live_at": config.LIVE_AT_PAIRS}, "eval": ev,
            "eval_history": evaluate.history(con)[-20:], "mine_runs": runs[::-1], "synthetic": synth, "real": real,
            "quarantine": len(pipeline.quarantine_list()), "signers_configured": config.signers().configured,
            "models": llm.available(), "settings": vars(config.models())}


def entities(con) -> dict:
    caps = library.rows(con, "signer IS NOT NULL")
    cnt = defaultdict(lambda: {"pairs": 0, "finals": 0})
    for c in caps:
        for p in c["pathologies"]:
            cnt[(c["signer"], p)]["pairs" if c["kind"] == "pair" else "finals"] += 1
    sat = miner.saturation(con)
    rows = []
    for e in taxonomy.ENTITIES:
        row = {"key": e.key, "label": e.label, "region": e.region, "modalities": list(e.modalities), "by": {}}
        for s in config.CODES:
            st = sat.get(s, {}).get(e.key, {})
            row["by"][s] = {**cnt[(s, e.key)], "saturated": bool(st.get("saturated")), "since_new": st.get("since_new", 0)}
        rows.append(row)
    return {"entities": rows, "open_next": miner.open_next(con), "window": config.SATURATION_WINDOW}


def change_rate(con) -> dict:
    caps = library.rows(con, "kind='pair' AND author_is_me=1")
    series = [{"id": c["id"], "at": c["captured_at"], "rate": round(c["change_rate"] or 0, 3), "signer": c["signer"],
               "pathologies": c["pathologies"]} for c in caps]
    per = defaultdict(list)
    for c in caps:
        for p in c["pathologies"]:
            per[p].append(c["change_rate"] or 0)
    others = [c["change_rate"] or 0 for c in library.rows(con, "kind='pair' AND author_is_me=0")]
    return {"series": series, "per_entity": sorted(
        [{"entity": k, "label": taxonomy.label(k), "n": len(v), "mean": round(sum(v) / len(v), 3)} for k, v in per.items()],
        key=lambda x: -x["mean"]), "others_mean": round(sum(others) / len(others), 3) if others else None}


def captures(con, q: dict) -> list:
    where, args = ["1"], []
    if q.get("signer"):
        where.append("signer=?")
        args.append(q["signer"])
    if q.get("kind"):
        where.append("kind=?")
        args.append(q["kind"])
    out = []
    for c in library.rows(con, " AND ".join(where), args):
        if q.get("entity") and q["entity"] not in c["pathologies"]:
            continue
        out.append({k: c[k] for k in ("id", "kind", "signer", "modality", "region", "pathologies", "change_rate",
                                      "author_is_me", "synthetic", "exam")})
    return out[-300:]


def capture(con, cid: int) -> dict | None:
    rs = library.rows(con, "id=?", (cid,))
    if not rs:
        return None
    c = rs[0]
    c["html"] = {k: diff.highlight_html(c.get(f"draft_{k}") or "", c.get(f"final_{k}") or "")
                 for k in ("befund", "beurteilung")} if c["kind"] == "pair" else None
    c.pop("content_hash", None)
    return c


class Handler(BaseHTTPRequestHandler):
    server_version = "RadBrain"

    def log_message(self, fmt, *args):  # no request logging (paths could carry ids only, but keep it quiet)
        pass

    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost", "[::1]")

    def _send(self, code: int, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False, default=str).encode()
                                                     if ctype == "application/json" else str(body).encode())
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "text" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                    "script-src 'self'; img-src 'self' data:")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if not self._host_ok():
            return self._send(403, {"error": "host"})
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        path = u.path
        if path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html")
        if path == "/app.js":
            return self._send(200, (STATIC / "app.js").read_bytes(), "application/javascript")
        if path == "/app.css":
            return self._send(200, (STATIC / "app.css").read_bytes(), "text/css")
        con = library.connect()
        try:
            if path == "/api/overview":
                return self._send(200, overview(con))
            if path == "/api/entities":
                return self._send(200, entities(con))
            if path == "/api/changerate":
                return self._send(200, change_rate(con))
            if path == "/api/rules":
                return self._send(200, miner.rules_for(con, q.get("signer", "B1")))
            if path == "/api/captures":
                return self._send(200, captures(con, q))
            m = re.fullmatch(r"/api/capture/(\d+)", path)
            if m:
                c = capture(con, int(m.group(1)))
                return self._send(200 if c else 404, c or {"error": "not found"})
            if path == "/api/signers":
                return self._send(200, signers_auto.listing())
            if path == "/api/quarantine":
                return self._send(200, pipeline.quarantine_list())
            m = re.fullmatch(r"/api/quarantine/([\w-]+)", path)
            if m:
                return self._send(200, pipeline.quarantine_preview(m.group(1)))
            if path == "/health":
                return self._send(200, {"ok": True, "captures": sum(v["pairs"] + v["finals"]
                                                                    for v in library.counts(con).values())})
            return self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": type(e).__name__})
        finally:
            con.close()

    def do_POST(self):  # noqa: N802
        if not self._host_ok() or self.headers.get("X-RadBrain") != "1":
            return self._send(403, {"error": "forbidden"})
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            return self._send(413, {"error": "too large"})
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return self._send(400, {"error": "json"})
        path = urlparse(self.path).path
        con = library.connect()
        try:
            if path == "/api/correct":
                return self._send(200, engine.correct(body.get("draft", ""), body.get("signer", "B1"),
                                                      use_llm=bool(body.get("llm", True)), con=con))
            if path == "/api/predict":
                return self._send(200, engine.predict(body.get("draft", ""), body.get("signer", "B1"), con=con))
            if path == "/api/ask":
                return self._send(200, engine.ask(body.get("question", ""), con=con, use_llm=bool(body.get("llm"))))
            if path == "/api/eval":
                with _lock:
                    return self._send(200, evaluate.run(con, llm=bool(body.get("llm"))))
            if path == "/api/mine":
                with _lock:
                    return self._send(200, miner.mine(con))
            if path == "/api/signers/assign":
                r = signers_auto.assign(str(body.get("key", "")), str(body.get("code", "")), con)
                with _lock:
                    miner.mine(con)
                return self._send(200, r)
            if path == "/api/assign":
                s = body.get("signer")
                if s not in config.CODES:
                    return self._send(400, {"error": "signer"})
                con.execute("UPDATE captures SET signer=? WHERE id=? AND signer IS NULL", (s, int(body["id"])))
                con.commit()
                return self._send(200, {"ok": True})
            m = re.fullmatch(r"/api/quarantine/([\w-]+)/(release|discard)", path)
            if m:
                if m.group(2) == "release":
                    return self._send(200, pipeline.quarantine_release(m.group(1), body.get("cleared_words") or []))
                pipeline.quarantine_discard(m.group(1))
                return self._send(200, {"ok": True})
            return self._send(404, {"error": "not found"})
        except ValueError as e:
            return self._send(400, {"error": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": type(e).__name__})
        finally:
            con.close()


def serve(host: str = "127.0.0.1", port: int = 8650) -> ThreadingHTTPServer:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("RadBrain's dashboard binds to localhost only")
    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8650)
    ap.add_argument("--demo", action="store_true", help="serve the synthetic demo data dir (python -m radbrain.demo)")
    a = ap.parse_args(argv)
    if a.demo:
        import os
        from .demo import demo_dir
        os.environ["RADBRAIN_DATA"] = str(demo_dir())
    config.write_signers_template()
    srv = serve(a.host, a.port)
    print(f"RadBrain dashboard on http://{a.host}:{a.port}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
