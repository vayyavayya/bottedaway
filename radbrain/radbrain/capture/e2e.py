"""End-to-end test on the PC: the REAL hotkey path against the dummy PACS window and the DEMO data dir.

    python -m radbrain.capture.e2e          (run inside the logged-on desktop, e.g. as an interactive task)

dummy window (fictional pair) → calibration from its panel rectangles → hotkey_app started → Ctrl+Shift+B sent
via keybd_event → grab (mss, memory) → Tesseract → anonymise → library → dashboard API shows the capture.
Only the demo data dir is touched (refuses one that holds real captures). Result: <demo dir>/logs/e2e.json.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request


def _press_ctrl_shift(vk: int) -> None:
    u = ctypes.WinDLL("user32")
    for k in (0x11, 0x10):                    # VK_CONTROL, VK_SHIFT down
        u.keybd_event(k, 0, 0, 0)
    u.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    u.keybd_event(vk, 0, 2, 0)
    for k in (0x10, 0x11):
        u.keybd_event(k, 0, 2, 0)


def main() -> int:
    from radbrain.demo import demo_dir
    d = demo_dir()
    os.environ["RADBRAIN_DATA"] = str(d)
    from radbrain import config, library
    config.data_dir()
    con = library.connect()
    if con.execute("SELECT COUNT(*) FROM captures WHERE synthetic=0 AND source NOT LIKE 'hotkey%'").fetchone()[0]:
        print("refusing: demo dir holds non-test captures")
        return 2
    (d / "signers.json").write_text(json.dumps({"signers": {"B1": ["Probe"], "B2": ["Beispiel"], "B3": ["Test-B3"]},
                                                "me": ["Muster"], "staff": []}), encoding="utf-8")
    geo = d / "logs" / "dummy_geometry.json"
    geo.unlink(missing_ok=True)
    py = sys.executable
    env = dict(os.environ)
    result: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {}}
    dummy = subprocess.Popen([py, "-m", "radbrain.capture.dummy_window", "--geometry-out", str(geo), "--topmost",
                              "--exit-after", "150", "--font-size", "15"], env=env)
    app = None
    try:
        for _ in range(100):
            if geo.exists():
                break
            time.sleep(0.2)
        g = json.loads(geo.read_text(encoding="utf-8"))
        rects = {k: g["rects"][k] for k in ("draft", "final")}
        result["steps"]["dummy_window"] = {"rects": rects}
        from radbrain.capture import calibrate
        calibrate.calibration_path().unlink(missing_ok=True)      # no calibration: the tool must find the panels
        time.sleep(1.5)
        n0 = con.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
        app = subprocess.Popen([py, "-m", "radbrain.capture.hotkey_app"], env=env)
        time.sleep(6)
        _press_ctrl_shift(0x42)                      # Ctrl+Shift+B = pair
        result["steps"]["hotkey_sent"] = time.strftime("%H:%M:%S")
        row = None
        for _ in range(120):
            time.sleep(0.5)
            con2 = library.connect()
            n = con2.execute("SELECT COUNT(*) FROM captures").fetchone()[0]
            if n > n0:
                row = library.rows(con2, "id=(SELECT MAX(id) FROM captures)")[0]
                con2.close()
                break
            con2.close()
        q = list((d / "quarantine").glob("*.json"))
        if row is None:
            result["steps"]["library"] = {"saved": False, "quarantine_files": len(q)}
        else:
            result["steps"]["library"] = {k: row[k] for k in ("id", "kind", "signer", "author_is_me", "modality",
                                                              "region", "pathologies", "change_rate")}
            result["steps"]["library"]["final_befund"] = row["final_befund"]
            result["steps"]["library"]["final_beurteilung"] = row["final_beurteilung"]
            from radbrain import web
            srv = web.serve("127.0.0.1", 0)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            port = srv.server_address[1]
            caps = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/captures").read())
            result["steps"]["dashboard"] = {"capture_listed": any(c["id"] == row["id"] for c in caps)}
            srv.shutdown()
        cal = calibrate.load_calibration().get("pair") or {}
        result["steps"]["autodetected"] = {k: cal.get(k) for k in ("draft", "final")}
        log = d / "logs" / "capture.log"
        if log.exists():
            result["capture_log_tail"] = log.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
        imgs = [p.name for p in d.rglob("*") if p.suffix.lower() in (".png", ".jpg", ".bmp")]
        result["image_files_on_disk"] = imgs
        result["ok"] = bool(row) and result["steps"].get("dashboard", {}).get("capture_listed") and not imgs
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
        result["ok"] = False
    finally:
        for p in (app, dummy):
            if p and p.poll() is None:
                p.terminate()
    (d / "logs" / "e2e.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
