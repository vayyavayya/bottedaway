#!/usr/bin/env python3
"""Tiny static server so index/template.html can fetch data/dashboard.json.
Not needed if you just open the standalone dashboard.html (data is embedded).

    python serve.py            # http://localhost:8000/template.html
"""
import http.server, socketserver, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PORT = int(os.environ.get("PORT", "8000"))

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

with socketserver.TCPServer(("", PORT), H) as httpd:
    print(f"Serving on http://localhost:{PORT}/template.html  (Ctrl-C to stop)")
    httpd.serve_forever()
