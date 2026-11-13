"""Local development server: the real ``Api`` over SQLite, on 127.0.0.1.

The Worker runs inside Cloudflare's runtime with a D1 binding and Access in front of it.
Plain Python has none of that, so this file swaps in ``SqliteD1`` (the same SQL as D1),
a fixed ``DevIdentity``, and the stdlib HTTP server. Nothing here ships to the Worker.

Run:  python3 local_server.py     (then GET http://127.0.0.1:8787/quiz/api/me)

Environment:
  PORT           listen port (default 8787)
  DB_PATH        SQLite file (default backend/quiz.db, created from the migration if missing)
  DEV_EMAIL      the signed-in user (default dev@example.com)
  ADMIN_EMAILS   comma-separated admins (default: DEV_EMAIL, so you can use /admin)

Written answers are marked by the evaluators the admin lists at /quiz/admin/evaluators.
Locally the ``Fake (local)`` provider is always there (deterministic, free, no network):
add a "Fake (local) · fake-overlap" entry to mark answers offline. A real provider is
listed as usable only when its secrets are in this process's environment (the same names
as the Worker's, e.g. ANTHROPIC_API_KEY), and it is called over urllib. Use a separate dev
key with its own small spend limit, never the production one.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from quiz_app.api import decode_body, response_headers
from quiz_app.auth import DevIdentity, normalize_email, parse_emails
from quiz_app.composition import build_api, quotas_from
from quiz_app.d1.sqlite_binding import SqliteD1
from quiz_app.evaluators import FAKE, FakeEvaluator, urllib_post, usable_evaluators

HERE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH", HERE / "quiz.db"))
DEV_EMAIL = normalize_email(os.environ.get("DEV_EMAIL", "dev@example.com"))
ADMIN_EMAILS = parse_emails(os.environ.get("ADMIN_EMAILS", DEV_EMAIL))

#: The Next dev server. Credentials are sent, so the origin must be echoed, never "*".
ALLOWED_ORIGIN = "http://localhost:3000"
ALLOWED_METHODS = "GET, POST, PUT, PATCH, OPTIONS"
ALLOWED_HEADERS = "content-type"


def open_db(path: Path) -> SqliteD1:
    fresh = not path.exists()
    # One connection shared by the handler threads; requests are serialised by LOCK.
    db = SqliteD1(sqlite3.connect(str(path), check_same_thread=False))
    if fresh:
        for migration in sorted((HERE / "migrations").glob("*.sql")):
            db.executescript(migration.read_text())
    return db


EVALUATORS = {FAKE: FakeEvaluator(), **usable_evaluators(os.environ.get, urllib_post)}
API = build_api(open_db(DB_PATH), ADMIN_EMAILS, evaluators=EVALUATORS, quotas=quotas_from(os.environ.get))
IDENTITY = DevIdentity(DEV_EMAIL)
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def _cors_headers(self) -> None:
        """Echo the origin only when it is the frontend's: a wildcard is illegal with credentials."""
        if self.headers.get("Origin") == ALLOWED_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    def _send(self, status: int, body: dict | None, extra: dict[str, str]) -> None:
        payload = b"" if status == 204 or body is None else json.dumps(body).encode("utf-8")
        self.send_response(status)
        if payload:
            self.send_header("Content-Type", "application/json")
        for name, value in extra.items():
            self.send_header(name, value)
        self._cors_headers()
        if status != 204:
            self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace") if length else None
        body = decode_body(raw) if self.command in ("POST", "PUT", "PATCH") else None
        path = urlsplit(self.path).path
        try:
            with LOCK:
                identity = asyncio.run(IDENTITY.identify(self))
                status, payload = asyncio.run(API.handle(self.command, path, body, identity))
        except Exception:  # noqa: BLE001 - surface any bug as a 500 instead of a dropped connection
            traceback.print_exc()
            status, payload = 500, {"error": "internal error"}
        self._send(status, payload, response_headers(path, status))

    # DELETE is a real route (/admin/sets/{id}); the dev server must speak it too.
    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", ALLOWED_METHODS)
        self.send_header("Access-Control-Allow-Headers", ALLOWED_HEADERS)
        self.end_headers()

    def log_message(self, *_args) -> None:
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8787"))
    print(f"quiz backend listening on http://127.0.0.1:{port}/quiz/api")
    print(f"  db       : {DB_PATH}")
    print(f"  identity : {DEV_EMAIL}" + (" (admin)" if DEV_EMAIL in ADMIN_EMAILS else ""))
    print(f"  providers: {', '.join(sorted(EVALUATORS))}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
