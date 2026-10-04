#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
groq_proxy.py
=============
A simple local proxy for the rare case where the chat page cannot
reach Groq directly from the browser (e.g. a CORS error). It is only a fallback
for the AI answers feature. It uses only the Python standard library (nothing
to install) and runs on your machine only.


Usage:
    python groq_proxy.py

It listens on http://localhost:8787. Then open the settings of the
chat page -> "Advanced" and set "Local proxy URL" to:
    http://localhost:8787

Your API key is sent from the browser to this proxy (running on your machine)
and forwarded to Groq as-is: nothing is stored or logged here.
"""

import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8787
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class Handler(BaseHTTPRequestHandler):
    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Groq-Key, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path != "/chat":
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        api_key = self.headers.get("X-Groq-Key") or self.headers.get("Authorization", "").replace("Bearer ", "")

        if not api_key:
            self.send_response(400)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "missing api key"}).encode("utf-8"))
            return

        req = urllib.request.Request(
            GROQ_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            data = e.read()
            status = e.code
        except Exception as e:
            self.send_response(502)
            self._cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("  [proxy] " + (fmt % args))


def main():
    print("=" * 60)
    print(f"Local Groq proxy running at http://localhost:{PORT}")
    print("Keep this window open and put this URL in the Advanced settings of the chat page.")
    print("To stop it: press Ctrl+C")
    print("=" * 60)
    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")


if __name__ == "__main__":
    main()
