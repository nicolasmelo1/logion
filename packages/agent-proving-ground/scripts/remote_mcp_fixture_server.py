#!/usr/bin/env python3
"""Tiny OAuth-gated HTTP fixture standing in for a closed remote MCP."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/mcp" or self.headers.get("Authorization") != (
            "Bearer fixture-access"
        ):
            self.send_response(401)
            self.end_headers()
            return
        length = min(int(self.headers.get("Content-Length", "0")), 4096)
        self.rfile.read(length)
        body = json.dumps({
            "result": "MCP_PRIVATE_CANARY_DO_NOT_RECORD",
            "task": "completed",
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 18765), Handler).serve_forever()
