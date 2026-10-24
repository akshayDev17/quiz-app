#!/usr/bin/env python3
"""Upload a quiz-set JSON to the live quiz app.

Cloudflare Access one-time-PIN auth, three steps (upload.py never talks to mail):

  1. python3 upload.py --request-otp --email you@example.com
       Opens a headless browser, enters the email, clicks "Send login code".
  2. (the agent reads the email with a mail MCP and copies the
       "Finish logging in" URL from it)
  3. python3 upload.py --finish-login --url "https://…/cdn-cgi/access/callback?…"
       Visits that URL and caches the CF_Authorization cookie (~24 h).
  4. python3 upload.py quiz.json [--publish]

The cookie is cached at ~/.quiz/session.json. Alternatively pass --cookie or set
QUIZ_CF_AUTHORIZATION to skip the login entirely.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _plugin_root() -> Path:
    """The quiz-tools plugin root, found by walking up to quiz_validation.py."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "quiz_validation.py").exists():
            return parent
    raise SystemExit("could not locate the quiz-tools plugin root (quiz_validation.py)")


sys.path.insert(0, str(_plugin_root()))

from quiz_validation import Invalid, QuizValidator  # noqa: E402

BASE = os.environ.get("QUIZ_BASE", "https://akshayprabhakant.com")
CACHE = os.path.expanduser("~/.quiz/session.json")

_HINTS = {
    401: "session expired — re-run the login",
    403: "not an admin — check ADMIN_EMAILS",
    422: "invalid quiz",
}


# --- auth -------------------------------------------------------------------

def _with_playwright():
    """The Playwright entry point, installing it on first use rather than up front.

    Playwright is a package plus a downloaded Chromium, so it cannot ship in the
    plugin; bootstrap.py provisions it into ~/.quiz/venv once, then this re-execs
    under that interpreter. The env guard stops a re-exec loop if the install did
    not actually take.
    """
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        pass
    if os.environ.get("QUIZ_PLAYWRIGHT_READY"):
        sys.exit("playwright is installed but will not import — run: pip install --force-reinstall playwright")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import bootstrap  # noqa: PLC0415 — only needed on this path

    interpreter = bootstrap.ensure()
    os.environ["QUIZ_PLAYWRIGHT_READY"] = "1"
    os.execve(interpreter, [interpreter, str(Path(__file__).resolve()), *sys.argv[1:]], os.environ)
    raise AssertionError("unreachable: os.execve replaces this process")


def request_otp(email: str) -> None:
    """Open the Access login in a headless browser and request a code."""
    sync_playwright = _with_playwright()
    udd = os.path.expanduser("~/.quiz/access-browser")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(udd, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(BASE + "/quiz", wait_until="domcontentloaded")
        page.fill('[data-testid="email-input"]', email)
        page.click('[data-testid="email-submit-button"]')
        page.wait_for_selector('[data-testid="otp-code-input"]', timeout=20000)
        print(f"Login code sent to {email} (expires in 10 minutes).")
        ctx.close()


def finish_login(url: str) -> None:
    """Visit the 'Finish logging in' link and cache the CF_Authorization cookie."""
    import http.cookiejar

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler(),
    )
    req = urllib.request.Request(url, headers={"User-Agent": "quiz-upload"})
    try:
        with opener.open(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        e.read()

    cf = None
    for c in cj:
        if c.name == "CF_Authorization" and "akshayprabhakant.com" in c.domain:
            cf = c.value
            break
    if not cf:
        sys.exit("login failed — no CF_Authorization cookie for akshayprabhakant.com")

    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump({"CF_Authorization": cf}, f)
    print(f"Logged in. Cookie cached at {CACHE}")


# --- cookie + post ----------------------------------------------------------

def _cookie(args: argparse.Namespace) -> str | None:
    if args.cookie:
        return args.cookie
    if os.environ.get("QUIZ_CF_AUTHORIZATION"):
        return os.environ["QUIZ_CF_AUTHORIZATION"]
    if os.path.exists(CACHE):
        try:
            return json.load(open(CACHE, encoding="utf-8")).get("CF_Authorization")
        except (OSError, ValueError):
            return None
    return None


def _post(path: str, payload: object, cookie: str) -> tuple[int, object]:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Cookie": f"CF_Authorization={cookie}",
            # Cloudflare 1010-blocks urllib's default "Python-urllib/x.y" signature.
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def _die(verb: str, status: int, data: object) -> None:
    msg = data.get("error") if isinstance(data, dict) else data
    hint = _HINTS.get(status)
    suffix = f" ({hint})" if hint else ""
    sys.exit(f"{verb} failed {status}{suffix}: {msg}")


# --- main -------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("quiz", nargs="?", help="path to a quiz-set JSON file (upload mode)")
    p.add_argument("--cookie", help="CF_Authorization value (or QUIZ_CF_AUTHORIZATION, or ~/.quiz/session.json)")
    p.add_argument("--publish", action="store_true", help="publish immediately after import")
    p.add_argument("--request-otp", action="store_true", help="request a login code (send email)")
    p.add_argument("--email", help="email for --request-otp")
    p.add_argument("--finish-login", action="store_true", help="complete login from a 'Finish logging in' URL")
    p.add_argument("--url", help="'Finish logging in' URL for --finish-login")
    args = p.parse_args()

    if args.request_otp:
        if not args.email:
            sys.exit("--request-otp needs --email")
        request_otp(args.email)
        return
    if args.finish_login:
        if not args.url:
            sys.exit("--finish-login needs --url")
        finish_login(args.url)
        return

    if not args.quiz:
        sys.exit("nothing to do — pass a quiz.json, --request-otp, or --finish-login")

    try:
        with open(args.quiz, encoding="utf-8") as f:
            quiz = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"not valid JSON: {e}")
    except OSError as e:
        sys.exit(f"cannot read {args.quiz}: {e}")

    try:
        QuizValidator.parse(quiz)
    except Invalid as e:
        sys.exit(f"not uploading — invalid quiz: {e.message}")

    cookie = _cookie(args)
    if not cookie:
        sys.exit("no CF_Authorization cookie — run --request-otp / --finish-login first, "
                 "or pass --cookie / QUIZ_CF_AUTHORIZATION")

    status, data = _post("/quiz/api/admin/sets", quiz, cookie)
    if status != 201:
        _die("import", status, data)

    set_id, name = data["id"], data["name"]
    print(f'Imported "{name}" as draft (id={set_id})')

    if args.publish:
        status, data = _post(f"/quiz/api/admin/sets/{set_id}/publish", {}, cookie)
        if status != 200:
            _die("publish", status, data)
        print(f'Published (id={set_id}, status={data["status"]})')


if __name__ == "__main__":
    main()
