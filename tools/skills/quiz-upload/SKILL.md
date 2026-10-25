---
name: quiz-upload
description: Upload a quiz-set JSON to the live quiz app and optionally publish it. Use when asked to upload, publish, or ship a quiz.
---

# quiz-upload — ship a quiz set to /quiz

Run `<scripts>/upload.py`, which validates, authenticates (Cloudflare Access
one-time PIN), and posts to `POST /quiz/api/admin/sets`. You must be an admin:
your email must be in `ADMIN_EMAILS`.

## Steps

Resolve `<scripts>` as the `scripts/` directory beside this SKILL.md — in Claude Code that is `${CLAUDE_PLUGIN_ROOT}/skills/quiz-upload/scripts`, never a path relative to the project you happen to be in.

1. **Validate** the file first, if you didn't just run `quiz-create`:
   `python3 <scripts>/validate.py <file>` → must print `OK …`. (upload.py re-checks
   with the same validator before posting, so a bad file is refused locally.)
2. **Make sure the code mailbox is reachable** — the login code arrives by email, so
   this must work *before* a code is spent. Call a cheap read: `mcp__gmail__search_emails`
   with `from:noreply@notify.cloudflare.com newer_than:1d`. A real answer, even an empty
   one, means the grant is in place; skip to step 3.
   If that tool is missing or errors about credentials, run
   `python3 <scripts>/gmail_auth.py` — no arguments, no paths to configure.
   **Do not send the user to the Google Cloud console.** The OAuth client belongs to the
   plugin, not to them: the script writes it, opens the consent screen for their own
   mailbox, and waits. Say only this: pick the Google account that owns the quiz mailbox;
   if it says "Google hasn't verified this app", click **Advanced → Go to … (unsafe)**
   (expected — nobody has paid for Google's app review); approve read/manage Gmail; the
   tab should then say "Authentication successful! You can close this window."
   Then tell the user plainly: the Gmail *tool* is served by a process that started
   before the token existed, so it may need a fresh session before the tool appears —
   ask them to restart Claude Code and say "upload it" again, and the flow resumes at
   this step for free.
   If the script exits 2 because port 3000 is busy, stop whatever holds it and retry.
3. **Request a login code** (skip if `~/.quiz/session.json` already has a fresh
   cookie):
   `python3 <scripts>/upload.py --request-otp --email <admin-email>`.
   The first run that needs a browser provisions Playwright into `~/.quiz/venv` by
   itself and then re-execs — expect a one-time, well-over-100 MB Chromium download
   and a minute or two before `Login code sent to …` appears. Do not install
   Playwright by hand; do not interrupt it.
   Completion: it prints `Login code sent to …`.
4. **Read the code email** with the Gmail MCP (`mcp__gmail__search_emails` for
   `from:noreply@notify.cloudflare.com`, then `mcp__gmail__read_email`). Copy the
   **"Finish logging in" URL** from the body.
5. **Complete login**:
   `python3 <scripts>/upload.py --finish-login --url "<that URL>"`.
   Completion: it prints `Logged in. Cookie cached at ~/.quiz/session.json`.
6. **Upload**:
   `python3 <scripts>/upload.py <file> [--publish]`.
   Completion: `Imported "<name>" as draft (id=<id>)` (and, with `--publish`,
   `Published (id=<id>, status=published)`).

## Failures

- `422` — lists every validation problem verbatim; fix and re-run.
- `403` — the signed-in email is not in `ADMIN_EMAILS`.
- `401` — the cookie expired; re-run steps 2–4.
- `Login code sent …` but no email in 10 minutes → request a fresh code; the
  previous one expires on the next request.

## Notes

- The `CF_Authorization` cookie lasts ~24 h; once cached, uploads skip steps 2–4
  until it expires.
- `--cookie "eyJ…"` or `QUIZ_CF_AUTHORIZATION` bypasses the login entirely if you
  already have a cookie.
- The Playwright trigger needs `pip install playwright && playwright install chromium`.
