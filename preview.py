"""Local, demo-only preview. Serves ONLY the generated HTML, never repo files.

No dependencies, credentials, database, or cloud account are needed.
Usage: python preview.py [--port 8000] [--host 127.0.0.1]
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from build_preview import build


class Handler(BaseHTTPRequestHandler):
    html: bytes = b""

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] not in ("/", "/index.html", "/noair-forhandsvisning.html"):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.html)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(self.html)

    def log_message(self, fmt: str, *args: object) -> None:
        # Do not log request paths, query parameters or client addresses.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Noair: local demo preview, no data collection")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    Handler.html = build().read_bytes()
    with ThreadingHTTPServer((args.host, args.port), Handler) as server:
        print(f"Noair DEMO: http://{args.host}:{args.port} (no server-side storage)", flush=True)
        print("Restart this process after editing source files. Ctrl+C stops it.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
