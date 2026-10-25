#!/usr/bin/env python3
"""Tests for gmail_auth.py — run them yourself:  python3 test_gmail_auth.py

Every check is offline and deterministic: no Google, no network, no browser. The
one thing they cannot cover is the consent click itself, which needs a real client
and a human; everything around it is asserted here.

They exist because the claims about this script ("a new machine needs no console",
"the user only consents", "the keys file is in the shape the MCP parses") are the
kind of thing that is easy to assert and easy to get wrong.
"""

from __future__ import annotations

import json
import os
import socket
import stat
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gmail_auth  # noqa: E402

CLIENT = {"client_id": "abc.apps.googleusercontent.com", "client_secret": "s3cret"}


class BundledClientTest(unittest.TestCase):
    """Where the app's client comes from, and in what order."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.beside = self.dir / "client.json"
        for key in ("QUIZ_GOOGLE_CLIENT_ID", "QUIZ_GOOGLE_CLIENT_SECRET"):
            os.environ.pop(key, None)
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in
                                 ("QUIZ_GOOGLE_CLIENT_ID", "QUIZ_GOOGLE_CLIENT_SECRET")])

    def test_a_publisher_that_ships_nothing_means_none(self):
        # Not what this plugin does — it ships a client — but the fallback has to stay
        # honest for the case where someone blanks the constants.
        with mock.patch.multiple(
            gmail_auth, DEFAULT_CLIENT_ID="", DEFAULT_CLIENT_SECRET=""
        ):
            self.assertIsNone(gmail_auth.bundled_client(self.beside))

    def test_the_plugin_ships_a_usable_desktop_client(self):
        # The first-run promise in one assertion: a fresh machine gets a consent
        # screen without anyone opening the Google console. Blanking these silently
        # breaks every install but the publisher's own.
        self.assertTrue(gmail_auth.DEFAULT_CLIENT_ID, "the plugin ships no client_id")
        self.assertRegex(
            gmail_auth.DEFAULT_CLIENT_ID, r"\.apps\.googleusercontent\.com$"
        )
        self.assertTrue(
            gmail_auth.DEFAULT_CLIENT_SECRET.startswith("GOCSPX-"),
            "secret is not shaped like a Google client secret",
        )
        client = gmail_auth.bundled_client(self.beside)
        self.assertEqual(client["client_id"], gmail_auth.DEFAULT_CLIENT_ID)

    def test_env_wins(self):
        os.environ["QUIZ_GOOGLE_CLIENT_ID"] = "env-id"
        os.environ["QUIZ_GOOGLE_CLIENT_SECRET"] = "env-secret"
        self.assertEqual(
            gmail_auth.bundled_client(self.beside),
            {"client_id": "env-id", "client_secret": "env-secret"},
        )

    def test_client_json_beside_the_script(self):
        self.beside.write_text(json.dumps(CLIENT))
        self.assertEqual(gmail_auth.bundled_client(self.beside), CLIENT)

    def test_client_json_in_googles_downloaded_shape(self):
        # Google hands you {"installed": {...}}; either shape must work.
        self.beside.write_text(json.dumps({"installed": CLIENT}))
        self.assertEqual(gmail_auth.bundled_client(self.beside), CLIENT)

    def test_constants_are_the_last_resort(self):
        with mock.patch.multiple(
            gmail_auth, DEFAULT_CLIENT_ID="c-id", DEFAULT_CLIENT_SECRET="c-secret"
        ):
            self.assertEqual(
                gmail_auth.bundled_client(self.beside),
                {"client_id": "c-id", "client_secret": "c-secret"},
            )

    def test_a_broken_client_json_is_ignored_rather_than_crashing(self):
        self.beside.write_text("{not json")
        with mock.patch.multiple(
            gmail_auth, DEFAULT_CLIENT_ID="", DEFAULT_CLIENT_SECRET=""
        ):
            self.assertIsNone(gmail_auth.bundled_client(self.beside))

    def test_a_broken_client_json_falls_through_to_the_shipped_one(self):
        # A malformed client.json must not poison the run: the plugin's own client is
        # still there, so first run keeps working.
        self.beside.write_text("{not json")
        self.assertEqual(
            gmail_auth.bundled_client(self.beside),
            {
                "client_id": gmail_auth.DEFAULT_CLIENT_ID,
                "client_secret": gmail_auth.DEFAULT_CLIENT_SECRET,
            },
        )


class KeysFileTest(unittest.TestCase):
    """The file the MCP insists on, generated from the app's client."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.keys = self.dir / "nested" / "gcp-oauth.keys.json"
        self.beside = self.dir / "client.json"
        self.beside.write_text(json.dumps(CLIENT))

    def test_written_in_the_shape_the_mcp_parses(self):
        # The MCP does `keysContent.installed || keysContent.web`, then reads
        # client_id and client_secret — so this is the shape or it does not load.
        with mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()):
            self.assertEqual(gmail_auth.ensure_keys_file(self.keys, self.beside), 0)
        written = json.loads(self.keys.read_text())
        self.assertIn("installed", written)
        self.assertEqual(written["installed"]["client_id"], CLIENT["client_id"])
        self.assertEqual(written["installed"]["client_secret"], CLIENT["client_secret"])

    def test_the_secret_is_not_world_readable(self):
        with mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()):
            gmail_auth.ensure_keys_file(self.keys, self.beside)
        mode = stat.S_IMODE(self.keys.stat().st_mode)
        self.assertEqual(mode, 0o600, oct(mode))

    def test_an_existing_file_is_never_overwritten(self):
        self.keys.parent.mkdir(parents=True)
        self.keys.write_text(json.dumps({"installed": {"client_id": "mine"}}))
        self.assertEqual(gmail_auth.ensure_keys_file(self.keys, self.beside), 0)
        self.assertEqual(json.loads(self.keys.read_text())["installed"]["client_id"], "mine")

    def test_a_fresh_machine_gets_the_shipped_client_written(self):
        # The real first run: no client.json, no env vars, nothing on disk — just the
        # plugin's own client and a directory that does not exist yet.
        self.beside.unlink()
        with mock.patch("sys.stdout", new_callable=lambda: __import__("io").StringIO()) as out:
            self.assertEqual(gmail_auth.ensure_keys_file(self.keys, self.beside), 0)
        written = json.loads(self.keys.read_text())["installed"]
        self.assertEqual(written["client_id"], gmail_auth.DEFAULT_CLIENT_ID)
        self.assertEqual(
            written["redirect_uris"],
            [f"http://localhost:{gmail_auth.CALLBACK_PORT}/oauth2callback"],
        )
        self.assertIn("plugin's own Google client", out.getvalue())

    def test_with_no_client_it_exits_2_and_blames_the_publisher(self):
        self.beside.unlink()
        with mock.patch.multiple(
            gmail_auth, DEFAULT_CLIENT_ID="", DEFAULT_CLIENT_SECRET=""
        ), mock.patch(
            "sys.stderr", new_callable=lambda: __import__("io").StringIO()
        ) as err:
            self.assertEqual(gmail_auth.ensure_keys_file(self.keys, self.beside), 2)
        message = err.getvalue()
        self.assertIn("published this plugin", message.lower())
        self.assertIn("should not have to do anything", message)
        self.assertNotIn("Cloud console", message)  # never send the user there
        self.assertFalse(self.keys.exists())


class AuthorisedTest(unittest.TestCase):
    def setUp(self):
        self.credentials = Path(tempfile.mkdtemp()) / "credentials.json"

    def test_a_refresh_token_counts_as_authorised(self):
        self.credentials.write_text(json.dumps({"refresh_token": "rt", "access_token": "at"}))
        self.assertTrue(gmail_auth._already_authorised(self.credentials))

    def test_an_access_token_alone_counts(self):
        self.credentials.write_text(json.dumps({"access_token": "at"}))
        self.assertTrue(gmail_auth._already_authorised(self.credentials))

    def test_missing_or_empty_is_not_authorised(self):
        self.assertFalse(gmail_auth._already_authorised(self.credentials))
        self.credentials.write_text("{}")
        self.assertFalse(gmail_auth._already_authorised(self.credentials))
        self.credentials.write_text("not json")
        self.assertFalse(gmail_auth._already_authorised(self.credentials))


class PortTest(unittest.TestCase):
    def test_a_busy_callback_port_is_reported_not_attempted(self):
        # The MCP hardcodes 3000 for its callback; a dev server there breaks auth.
        hold = socket.socket()
        hold.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.addCleanup(hold.close)
        try:
            hold.bind(("127.0.0.1", gmail_auth.CALLBACK_PORT))
            hold.listen(1)
        except OSError:
            self.skipTest("port 3000 already busy on this machine")
        keys = Path(tempfile.mkdtemp()) / "keys.json"
        keys.write_text(json.dumps({"installed": CLIENT}))
        credentials = keys.parent / "credentials.json"
        with mock.patch("sys.stderr", new_callable=lambda: __import__("io").StringIO()) as err:
            self.assertEqual(gmail_auth.authorise(keys, credentials, "quiz", 5), 2)
        self.assertIn("3000", err.getvalue())
        self.assertFalse(credentials.exists())


class CopyFromTest(unittest.TestCase):
    """--copy-from is what a second machine actually uses."""

    def setUp(self):
        self.src = Path(tempfile.mkdtemp())
        (self.src / "gcp-oauth.keys.json").write_text(json.dumps({"installed": CLIENT}))
        (self.src / "credentials.json").write_text(json.dumps({"refresh_token": "rt"}))
        self.bin = Path(tempfile.mkdtemp())
        self.dest = Path(tempfile.mkdtemp()) / "out"

    def stub_scp(self, body: str) -> None:
        scp = self.bin / "scp"
        scp.write_text(body)
        scp.chmod(0o755)
        patched = mock.patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}"})
        patched.start()
        self.addCleanup(patched.stop)

    def test_it_copies_both_files_and_the_token_is_used(self):
        # Stand-in for the transport only; the file handling is the code under test.
        self.stub_scp(f'#!/bin/bash\ncp "{self.src}/$(basename "$2")" "$3"\n')
        keys = self.dest / "keys.json"
        credentials = self.dest / "credentials.json"
        self.assertEqual(gmail_auth.copy_from("someone@host", keys, credentials), 0)
        self.assertEqual(json.loads(keys.read_text())["installed"]["client_id"], CLIENT["client_id"])
        self.assertTrue(gmail_auth._already_authorised(credentials))

    def test_a_failed_transport_exits_2_with_the_manual_command(self):
        self.stub_scp('#!/bin/bash\necho "scp: Connection closed" >&2\nexit 1\n')
        keys = self.dest / "keys.json"
        with mock.patch("sys.stderr", new_callable=lambda: __import__("io").StringIO()) as err:
            self.assertEqual(gmail_auth.copy_from("someone@host", keys, self.dest / "c.json"), 2)
        self.assertIn("Copy it by hand", err.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
