#!/usr/bin/env python3
"""Authorise the Gmail MCP, walking the human through the one screen only they can pass.

The upload flow reads the Cloudflare Access login code out of a mailbox, so the Gmail
MCP needs an OAuth grant. That grant cannot be made headless — a person has to approve
it — but everything around the approval can be: checking whether it is already done,
finding the URL, waiting for the token to land, and telling the user exactly which
buttons to press.

The server's own `auth` command, read from its source, does:

    server.listen(3000)                     # hardcoded, and it is the callback port
    console.log('Please visit this URL to authenticate:', authUrl)
    open(authUrl)                           # pops the browser by itself
    ...writes GMAIL_CREDENTIALS_PATH on success

So this runs that command detached, surfaces the URL the moment it is printed, waits
for the token file to appear, and stops the child. Exit 0 means authorised.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

#: The MCP server hardcodes this port for its OAuth callback; there is no flag to move it.
CALLBACK_PORT = 3000

#: The plugin's own OAuth client. A desktop client is a PUBLIC client — Google:
#: "desktop apps are public clients and cannot keep secrets confidential" — so the
#: app ships one and the person installing it only ever sees a consent screen for
#: their own mailbox. Nobody using this plugin should ever open the Google console.
#:
#: Fill these once, as whoever publishes the plugin, or set QUIZ_GOOGLE_CLIENT_ID /
#: QUIZ_GOOGLE_CLIENT_SECRET, or drop a `client.json` beside this script with
#: {"client_id": "...", "client_secret": "..."}.
DEFAULT_CLIENT_ID = ""
DEFAULT_CLIENT_SECRET = ""

_MCP_KEYS_TEMPLATE = {
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost:3000/oauth2callback"],
}

INSTRUCTIONS = """
In the browser window that just opened (or at the URL above):

  1. Pick the Google account that owns the quiz mailbox.
  2. If it says "Google hasn't verified this app", click Advanced, then
     "Go to <app> (unsafe)". This is expected: the OAuth client belongs to you,
     it is just not published for public verification.
  3. Read the permissions it asks for — read and manage Gmail, plus basic Gmail
     settings — and click Continue / Allow.
  4. The tab should end on "Authentication successful! You can close this window."

Nothing is needed from a terminal after that; this script notices the token and
carries on.
""".rstrip()


def bundled_client() -> dict | None:
    """The app's OAuth client, wherever the publisher put it: env, client.json, constants."""
    client_id = os.environ.get("QUIZ_GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("QUIZ_GOOGLE_CLIENT_SECRET")
    if client_id and client_secret:
        return {"client_id": client_id, "client_secret": client_secret}

    beside = Path(__file__).resolve().parent / "client.json"
    if beside.exists():
        try:
            stored = json.loads(beside.read_text())
        except ValueError:
            stored = {}
        # Accept either the flat form or Google's downloaded {"installed": {...}}.
        stored = stored.get("installed") or stored.get("web") or stored
        if stored.get("client_id") and stored.get("client_secret"):
            return {"client_id": stored["client_id"], "client_secret": stored["client_secret"]}

    if DEFAULT_CLIENT_ID and DEFAULT_CLIENT_SECRET:
        return {"client_id": DEFAULT_CLIENT_ID, "client_secret": DEFAULT_CLIENT_SECRET}
    return None


def ensure_keys_file(oauth_keys: Path) -> int:
    """Write the MCP's keys file from the app's client when the user has none.

    The MCP insists on a `gcp-oauth.keys.json` holding `{"installed": {...}}`. A user
    never has one and never should: the client is the app's, not theirs, so it is
    materialised here from the bundled values. After this the only thing left is the
    consent screen for their own Gmail account.
    """
    if oauth_keys.exists():
        return 0
    client = bundled_client()
    if client is None:
        print(
            f"No OAuth client at {oauth_keys}, and this copy of the plugin ships none.\n"
            "\n"
            "You should not have to do anything here — the client belongs to the app, not\n"
            "to you. Ask whoever published this plugin to set one, or, if you have a machine\n"
            "that is already authorised, copy its files across:\n"
            f"  gmail_auth.py --copy-from <set-up-machine> --oauth {oauth_keys} "
            "--credentials <token-path>",
            file=sys.stderr,
        )
        return 2
    oauth_keys.parent.mkdir(parents=True, exist_ok=True)
    oauth_keys.write_text(
        json.dumps({"installed": {**client, **_MCP_KEYS_TEMPLATE}}, indent=2) + "\n"
    )
    oauth_keys.chmod(0o600)
    print(f"Using the plugin's own Google client (written to {oauth_keys}).")
    return 0


def _already_authorised(credentials: Path) -> bool:
    """True when the token file exists and holds something usable."""
    try:
        stored = json.loads(credentials.read_text())
    except (OSError, ValueError):
        return False
    return bool(stored.get("refresh_token") or stored.get("access_token"))


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _explain_port_conflict(port: int) -> None:
    print(
        f"The Gmail MCP's OAuth callback needs port {port}, and something else is using\n"
        f"it. The server hardcodes that port, so free it and re-run — for example stop a\n"
        f"dev server on {port} (next dev / vite default to it), then try again.\n"
        f"To see what holds it:  lsof -nP -iTCP:{port} -sTCP:LISTEN",
        file=sys.stderr,
    )


SET_UP_PATHS = ("gcp-oauth.keys.json", "credentials.json")


def copy_from(host: str, oauth_keys: Path, credentials: Path) -> int:
    """Fetch the OAuth client and the token from a machine that is already authorised.

    A new machine needs no Google console trip and no consent screen: the client is
    per Google project and the token is per account, so both are already on the
    machine that works. Copying them is the whole setup.
    """
    if not shutil.which("scp"):
        print("scp is not on PATH; copy the two files by hand instead.", file=sys.stderr)
        return 2
    for name, target in zip(SET_UP_PATHS, (oauth_keys, credentials)):
        target.parent.mkdir(parents=True, exist_ok=True)
        done = subprocess.run(
            ["scp", "-q", f"{host}:~/.gmail-quiz/{name}", str(target)],
            capture_output=True, text=True,
        )
        if done.returncode != 0:
            print(
                f"Could not copy {name} from {host}: {done.stderr.strip()}\n"
                f"Copy it by hand:  scp {host}:~/.gmail-quiz/{name} {target}",
                file=sys.stderr,
            )
            return 2
    if not _already_authorised(credentials):
        print(
            f"Copied {credentials} but it holds no token — is {host} really authorised?",
            file=sys.stderr,
        )
        return 2
    print(f"Copied the OAuth client and token from {host}.")
    return 0


def authorise(oauth_keys: Path, credentials: Path, account: str | None, timeout: int) -> int:
    if _already_authorised(credentials):
        print(f"Gmail is already authorised ({credentials}). Nothing to do.")
        return 0
    if ensure_keys_file(oauth_keys):
        return 2
    if not shutil.which("npx"):
        print("npx is not on PATH; it is needed to run the Gmail MCP.", file=sys.stderr)
        return 2
    if not _port_free(CALLBACK_PORT):
        _explain_port_conflict(CALLBACK_PORT)
        return 2

    env = dict(os.environ)
    env["GMAIL_OAUTH_PATH"] = str(oauth_keys)
    env["GMAIL_CREDENTIALS_PATH"] = str(credentials)
    if account:
        env["GMAIL_ACCOUNT_NAME"] = account

    credentials.parent.mkdir(parents=True, exist_ok=True)
    log = Path(tempfile.mkstemp(prefix="gmail-auth-", suffix=".log")[1])
    print("Starting the Gmail authorisation… the browser should open by itself.", flush=True)
    with log.open("w") as sink:
        child = subprocess.Popen(
            ["npx", "-y", "@jessicaoy89/gmail-mcp", "auth"],
            env=env, stdout=sink, stderr=subprocess.STDOUT, text=True,
        )
        seen = 0
        announced = False
        deadline = time.time() + timeout
        try:
            while time.time() < deadline:
                text = log.read_text(errors="replace")
                if not announced and "https://" in text[seen:]:
                    for line in text[seen:].splitlines():
                        if "https://" in line:
                            url = "https://" + line.split("https://", 1)[1].strip()
                            print("\nAuthorise Gmail at:\n  " + url, flush=True)
                            announced = True
                            break
                    print(INSTRUCTIONS, flush=True)
                seen = len(text)
                if _already_authorised(credentials):
                    print(f"\nAuthorised. Token written to {credentials}.")
                    return 0
                if child.poll() is not None:
                    tail = log.read_text(errors="replace").strip()
                    print(f"The authorisation process exited early:\n{tail}", file=sys.stderr)
                    return 1
                time.sleep(0.5)
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
            log.unlink(missing_ok=True)
    print(
        f"Timed out after {timeout}s without a token. Re-run when you can complete the\n"
        "browser step; nothing was authorised.",
        file=sys.stderr,
    )
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--oauth",
        type=Path,
        default=Path.home() / ".gmail-quiz" / "gcp-oauth.keys.json",
        help="the MCP's keys file; created from the plugin's own client if absent",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path.home() / ".gmail-quiz" / "credentials.json",
        help="where the token is stored",
    )
    parser.add_argument("--account", help="label for the mailbox, e.g. quiz")
    parser.add_argument(
        "--copy-from",
        metavar="USER@HOST",
        help="copy the OAuth client and token from a machine that is already set up "
        "(no Google console, no consent screen)",
    )
    parser.add_argument(
        "--timeout", type=int, default=300, help="seconds to wait for the browser step (default 300)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="only report whether authorisation is needed, changing nothing",
    )
    args = parser.parse_args()
    if args.copy_from:
        code = copy_from(args.copy_from, args.oauth, args.credentials)
        if code:
            sys.exit(code)
    if args.check:
        if _already_authorised(args.credentials):
            print(f"authorised: {args.credentials}")
            return
        print(f"not authorised: {args.credentials} is missing or holds no token")
        sys.exit(1)
    sys.exit(authorise(args.oauth, args.credentials, args.account, args.timeout))


if __name__ == "__main__":
    main()
