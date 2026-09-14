#!/usr/bin/env python3
"""Minimal BUD-01 Blossom server used as the Phase 0 spike's blob source.

Serves blobs content-addressed by sha256 at ``GET /<sha256>`` with the
Content-Type/Content-Length headers the NIP-5A spec says a host server MUST
forward. Blobs are files named ``<sha256>`` under ``--blobs``; an optional
sidecar ``<sha256>.type`` holds the MIME type so Content-Type forwarding is
realistic. A file named ``<sha256>`` under ``--tamper`` makes the server
return that file's (wrong) bytes instead, to exercise the gateway's hash
verification.

Also implements ``PUT /upload`` (BUD-02) so the spike can upload over the wire.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    blobs: Path = Path("/blobs")
    tamper: Path = Path("/tamper")

    def log_message(
        self, format: str, *args
    ):  # noqa: A002 - BaseHTTPRequestHandler API
        print(f"[fake-blossom] {format % args}", flush=True)

    def _serve_sha(self, sha256: str) -> None:
        if len(sha256) != 64:
            self.send_response(404)
            self.end_headers()
            return
        tamper_file = self.tamper / sha256
        if tamper_file.is_file():
            body = tamper_file.read_bytes()
            ctype = "application/octet-stream"
        else:
            blob = self.blobs / sha256
            if not blob.is_file():
                self.send_response(404)
                self.end_headers()
                return
            body = blob.read_bytes()
            side = self.blobs / f"{sha256}.type"
            ctype = (
                side.read_text().strip()
                if side.is_file()
                else "application/octet-stream"
            )
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:
        self._serve_sha(self.path.strip("/"))

    def do_GET(self) -> None:
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "12")
            self.end_headers()
            self.wfile.write(b"fake blossom\n")
            return
        self._serve_sha(self.path.strip("/"))

    def do_PUT(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        sha = self.headers.get("x", "").lower()
        if not sha or hashlib.sha256(body).hexdigest() != sha:
            sha = hashlib.sha256(body).hexdigest()
        (self.blobs / sha).write_bytes(body)
        url = f"{self.headers.get('x-server', 'http://localhost:8787')}/{sha}"
        payload = json.dumps({"url": url, "sha256": sha, "size": len(body)}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--blobs", default="blobs")
    ap.add_argument("--tamper", default="tamper")
    args = ap.parse_args()
    Handler.blobs = Path(args.blobs)
    Handler.tamper = Path(args.tamper)
    Handler.blobs.mkdir(parents=True, exist_ok=True)
    Handler.tamper.mkdir(parents=True, exist_ok=True)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"[fake-blossom] listening on http://{args.host}:{args.port} blobs={Handler.blobs}",
        flush=True,
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
