<div align="center">
  <img src="assets/logo.svg" width="120" alt="quiz-tools">
</div>

# quiz-tools

![version](https://img.shields.io/badge/version-0.3.2-3a4bd8)
![license](https://img.shields.io/badge/license-MIT-0f1220)

Two skills that author quiz sets for `/quiz` and ship them hands-off — write and
self-check the set, then upload and publish it without touching a form.

Part of the [`quiz-app`](../README.md) repository — the app these quizzes are
published to.

[**Install (Claude Code)**](#install-claude-code) |
[**Install (DSH)**](#install-dsh) |
[**First run**](#first-run-per-machine) |
[**Usage**](#usage) |
[**Troubleshooting**](#troubleshooting) |
[**What it leaves on disk**](#what-it-leaves-on-disk)

## What it does

- **`quiz-create`** — writes a quiz-set JSON in the house style (varied difficulty,
  plausible distractors, hidden multi-correct counts) and self-validates it against
  the *same* validator the server runs, so a set that passes locally cannot be
  rejected on upload.
- **`quiz-upload`** — posts it to `/quiz/api/admin/sets` and optionally publishes.
  Handles the Cloudflare Access one-time-PIN login by itself: drives the browser,
  reads the code out of the mailbox, caches the session cookie for ~24 h.

Ask in plain language — "make me a quiz on Raft consensus", then "upload it" — or
run them directly as `/quiz-tools:quiz-create` and `/quiz-tools:quiz-upload`.

## Install (Claude Code)

```sh
claude plugin marketplace add akshayDev17/quiz-app
claude plugin install quiz-tools@quiz-app --scope user
```

Brings both skills **and** the Gmail MCP server the upload flow reads its login code
with. Try it without installing: `claude --plugin-dir ./quiz-app/tools`.

## Install (DSH)

```sh
dsh plugin --profile web add file:"$PWD/tools"
```

Restart `dsh web` to load the skills. On this harness the Gmail MCP is declared in
the DSH profile rather than by the plugin.

## First run

One screen, once per Google account: the skill opens Google's consent page for the
mailbox it needs to read, you approve it, done. If it says the app is unverified,
that is expected — **Advanced → Go to … (unsafe)**.

Nothing is configured at install: the plugin asks for no paths, and both files live
where the Gmail MCP looks by default (`~/.gmail-mcp/`). The Gmail *tool* is served by a
process that starts with the session, so if you authorised mid-session, restart Claude
Code once — the tool appears and the upload continues.

There is nothing to configure and no Google Cloud project to create: the OAuth client
belongs to this plugin, not to whoever installs it. Playwright is provisioned the same
way, silently, on first use (~100 MB, once).

<details>
<summary>Publishing the plugin — one-time setup for the publisher, not for users</summary>

A desktop OAuth client is a **public client** — Google's own documentation says such
apps "cannot keep secrets confidential" — so the plugin ships one and every installer
just sees a consent screen. It is already filled in at
`skills/quiz-upload/scripts/gmail_auth.py`. To point the plugin at a different Google
project, replace those two constants, or set `QUIZ_GOOGLE_CLIENT_ID` /
`QUIZ_GOOGLE_CLIENT_SECRET`, or drop a `client.json` beside that script (gitignored, if
you would rather keep a client out of the repo).

Both constants must stay filled. With them blank the plugin has no client, so no
consent URL can even be built and every fresh install stalls at "ships no client" —
working only on a machine that already has the files. The offline tests fail loudly if
they are emptied.

The client itself comes from a one-time trip to the Google Cloud console (new project,
enable the Gmail API, OAuth client of type **Desktop app**). Gmail's scopes are
*restricted*, so an unverified app shows the warning screen and is capped at 100
consenting users; removing both requires Google's app review.

`--copy-from` remains for machines that are already authorised: copying
`~/.gmail-mcp/{gcp-oauth.keys.json,credentials.json}` across skips even the consent screen.

</details>

## Checking it yourself

The Gmail plumbing is tested offline — no Google, no network, no browser:

```sh
python3 skills/quiz-upload/scripts/test_gmail_auth.py
```

19 assertions covering that the plugin ships a usable desktop client, that a virgin
machine's first run writes the keys file from it (directory created, mode 0600, the
shape the MCP actually parses), that an existing file is never overwritten, that env
vars and `client.json` still win over the shipped client, that a busy callback port
and a failed copy exit 2 with the exact command to run, and that an unauthorised
mailbox is detected before a login code is spent. The one thing they cannot cover is
the consent click, which needs a real client and a human.

## Usage

```
you:  make me a quiz on Raft consensus, hard, 20 minutes
      → quiz-create writes rafts-consensus-quiz.json and validates it

you:  upload it and publish
      → quiz-upload logs in if needed, imports it, publishes it
```

## What the plugin sets up, and what is still yours

| | Provisioned |
| --- | --- |
| Both skills | yes |
| Gmail MCP server definition | yes |
| Playwright and its Chromium | yes, on first use |
| The Gmail OAuth grant | guided — a human still clicks Allow |
| `~/.gmail-mcp/gcp-oauth.keys.json` | yes — written on first run from the client the plugin ships |
| `python3`, `node`/`npx` | **no** — the only real prerequisites |

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `port 3000 is in use` | The Gmail MCP hardcodes 3000 for its OAuth callback. Stop whatever holds it (`lsof -nP -iTCP:3000 -sTCP:LISTEN`) and retry. |
| Gmail tools error about credentials | Not authorised on this machine. Delete `~/.gmail-mcp/credentials.json` and let the skill re-run the auth. |
| "Google hasn't verified this app" | Expected for an unpublished client: **Advanced → Go to … (unsafe)**, then Allow. |
| `playwright not installed` and it will not install | No network, or no `python3` to build the venv. Install by hand: `pip install playwright && playwright install chromium`. |
| `session expired — re-run the login` | The cached Cloudflare cookie lapsed (24 h). Delete `~/.quiz/session.json` and upload again. |
| "How do I reset / reinstall from scratch?" | See the quiz-upload SKILL.md, "Resetting from scratch". |

## What it leaves on disk

| Path | What | Removed by uninstalling? |
| --- | --- | --- |
| `~/.quiz/venv/` | Playwright virtualenv | no — delete to reclaim ~100 MB |
| `~/.quiz/session.json` | cached Cloudflare Access cookie (~24 h) | no |
| `~/.quiz/access-browser/` | the browser profile the login step drives | no |
| `~/.gmail-mcp/` | OAuth client keys and token (the MCP's own default location) | no |

## Why two manifests

`skills/` is the only copy of the skills. DSH reads `plugin.json` plus a skill
provider (`lib/index.js`, `cordis.patch.yml`); Claude Code reads
`.claude-plugin/plugin.json` plus `.mcp.json`. Same skills, two thin shells.

## Licence

MIT — see the `license` field in [`package.json`](package.json).
