#!/usr/bin/env python3
"""Make Playwright available on first use, instead of asking the user to install it.

The upload flow drives a headless browser for the Cloudflare Access login. Playwright
is a Python package *plus* a downloaded Chromium, so it cannot ship inside the plugin
— but it does not have to be a setup step either. This provisions it lazily:

  * the running interpreter already imports Playwright -> use it, change nothing;
  * otherwise build a virtualenv and install into it (once).

The virtualenv lives at ``~/.quiz/venv`` (override with ``QUIZ_VENV``), next to the
cached Access cookie, so it is stable across plugin updates and identical on DSH and
Claude Code. It survives an uninstall: remove it by hand if that matters.

Idempotent: once provisioned, a run is a single import check.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

VENV = Path(os.environ.get("QUIZ_VENV") or Path.home() / ".quiz" / "venv")
VENV_PYTHON = VENV / "bin" / "python"


def _imports_playwright(python: str) -> bool:
    """True when `python` can import Playwright. Never raises."""
    try:
        done = subprocess.run(
            [python, "-c", "import playwright.sync_api"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def _browsers_installed(python: str) -> bool:
    """True when at least one Chromium build is already downloaded."""
    done = subprocess.run(
        [python, "-m", "playwright", "install", "--dry-run", "chromium"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    # `--dry-run` prints an install location and exits 0 whether or not it exists,
    # so the check is on the directory it names.
    for line in done.stdout.splitlines():
        if "Install location:" in line:
            path = Path(line.split("Install location:", 1)[1].strip())
            return path.exists() and any(path.iterdir())
    return False


def _provision(dry_run: bool) -> str:
    """Build the virtualenv and install into it. Returns the interpreter to use."""
    steps = [
        (sys.executable, "-m", "venv", str(VENV)),
        (str(VENV_PYTHON), "-m", "pip", "install", "--quiet", "--upgrade", "pip"),
        (str(VENV_PYTHON), "-m", "pip", "install", "--quiet", "playwright"),
        (str(VENV_PYTHON), "-m", "playwright", "install", "chromium"),
    ]
    if dry_run:
        print(f"would create {VENV} and run:", file=sys.stderr)
        for command in steps:
            print("  " + " ".join(command), file=sys.stderr)
        return str(VENV_PYTHON)

    print(
        f"Installing Playwright into {VENV} — this happens once and downloads a "
        "Chromium build (well over 100 MB).",
        file=sys.stderr,
    )
    for command in steps:
        done = subprocess.run(command)
        if done.returncode != 0:
            raise SystemExit(
                f"could not provision Playwright: {' '.join(command)} exited "
                f"{done.returncode}. Install it by hand with\n"
                "  pip install playwright && playwright install chromium"
            )
    return str(VENV_PYTHON)


def ensure(dry_run: bool = False) -> str:
    """An interpreter that can import Playwright, provisioning one if needed."""
    if _imports_playwright(sys.executable):
        return sys.executable
    if VENV_PYTHON.exists() and _imports_playwright(str(VENV_PYTHON)):
        if not _browsers_installed(str(VENV_PYTHON)) and not dry_run:
            print("Downloading the Chromium build Playwright needs…", file=sys.stderr)
            subprocess.run(
                [str(VENV_PYTHON), "-m", "playwright", "install", "chromium"], check=False
            )
        return str(VENV_PYTHON)
    return _provision(dry_run)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="say what would be installed, without installing it",
    )
    args = parser.parse_args()
    interpreter = ensure(dry_run=args.dry_run)
    if not args.dry_run:
        # Callers re-exec this: `"$(bootstrap.py)" upload.py …`
        print(interpreter)


if __name__ == "__main__":
    main()
