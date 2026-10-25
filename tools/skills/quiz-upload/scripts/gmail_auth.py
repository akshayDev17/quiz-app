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
    if not oauth_keys.exists():
        print(
            f"No OAuth client keys at {oauth_keys}.\n"
            "\n"
            "If any machine is already set up, copy the pair across — no console, no browser,\n"
            "no consent:\n"
            f"  scp <set-up-machine>:~/.gmail-quiz/gcp-oauth.keys.json {oauth_keys}\n"
            f"  scp <set-up-machine>:~/.gmail-quiz/credentials.json {credentials}\n"
            "or let this script do it:\n"
            f"  gmail_auth.py --copy-from <set-up-machine> --oauth {oauth_keys} "
            f"--credentials {credentials}\n"
            "\n"
            "Create one from scratch only when no machine has it: Google Cloud console →\n"
            "new project → enable the Gmail API → OAuth client of type Desktop app → download\n"
            "the JSON. That is once per Google project, not once per machine.",
            file=sys.stderr,
        )
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
    parser.add_argument("--oauth", type=Path, required=True, help="path to gcp-oauth.keys.json")
    parser.add_argument("--credentials", type=Path, required=True, help="where the token is stored")
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
