# tools/ — a plugin for the quiz app

Two skills that author and ship quiz sets to `/quiz`, packaged once and installable
on both harnesses this project is used with. Both read the same `skills/`, so there
is one copy of the skills, not two.

- **DSH** — the agent-plugins manifest (`plugin.json`) plus a skill provider
  (`lib/index.js` + `cordis.patch.yml`).
- **Claude Code** — the `.claude-plugin/plugin.json` manifest, which also carries
  the Gmail MCP server and the two values it needs.

## What's in here

| Path | Read by | What it is |
| --- | --- | --- |
| `skills/` | both | The two skills. The only place their content lives. |
| `quiz_validation.py` | both | The server's validator, copied so a file that passes here passes on upload. |
| `.claude-plugin/plugin.json` | Claude Code | Manifest: metadata, `userConfig`, skill discovery. |
| `.mcp.json` | Claude Code | The Gmail MCP server the upload flow reads its login code with. |
| `plugin.json` | DSH | The agent-plugins manifest. |
| `lib/index.js`, `cordis.patch.yml` | DSH only | Registers a skill provider pointing at `skills/`. |

`.claude-plugin/marketplace.json` at the repo root is what makes the plugin
installable at all — Claude Code installs plugins from a marketplace, never from a
bare directory.

## Install — Claude Code

```sh
claude plugin marketplace add akshayDev17/quiz-app
claude plugin install quiz-tools@quiz-app --scope user
```

That one install brings the skills (`/quiz-tools:quiz-create`,
`/quiz-tools:quiz-upload`) **and** the Gmail MCP server. You are prompted for two
paths; see below for what to enter.

After a change: `claude plugin update quiz-tools@quiz-app`, then `/reload-plugins`
in a session. To try it without installing:

```sh
claude --plugin-dir ./quiz-app/tools
```

## Install — DSH

```sh
dsh plugin --profile web add file:"$PWD/tools"
```

`file:` copies the plugin into the profile's `node_modules`, which is **required** —
at boot DSH resolves `@deepseek-ai/dsh-skill-filesystem` (a DSH-internal package)
relative to that location. Don't use `link:`: the symlink resolves back to this
repo and breaks that resolution. To ship edits, remove + re-add (or bump the
version). Restart `dsh web` to load the skills.

The Gmail MCP is **not** shipped by the DSH side of this package; it is declared in
the DSH profile (`~/.dsh/profiles/web/cordis.patch.yml`). Claude Code gets the same
server from `.mcp.json` here.

## What the plugin gives you, and what is still yours

| | Provisioned by the plugin |
| --- | --- |
| The two skills | yes |
| Gmail MCP server definition | yes — `npx -y @jessicaoy89/gmail-mcp` |
| `GMAIL_OAUTH_PATH` / `GMAIL_CREDENTIALS_PATH` / `GMAIL_ACCOUNT_NAME` | **no** — prompted at install |
| The Gmail OAuth grant itself | **no** — one-time, in a browser |
| Playwright (package + Chromium) | yes — provisioned on first use into `~/.quiz/venv` |
| `python3` | **no** — see prerequisites |

The two paths are `userConfig` values, so you never run `claude mcp add`: the install
asks for them, and a shell install prints the options it still needs. Set them later
with `/plugin configure quiz-tools@quiz-app`, or up front with
`--config gmail_oauth_path=/abs/path/gcp-oauth.keys.json --config
gmail_credentials_path=/abs/path/credentials.json`. They must be absolute paths. The
credentials file is created on first authorisation, so it need not exist yet.

`GMAIL_ACCOUNT_NAME` defaults to `quiz`.

## Prerequisites

- **`python3`** — the two skills run their `scripts/` with it.
- **`node`/`npx`** — to start the Gmail MCP server.

**Playwright is not a prerequisite.** The Cloudflare Access login step needs it, so
`upload.py` provisions it on first use: if the running interpreter cannot import
Playwright, `scripts/bootstrap.py` builds a virtualenv at `~/.quiz/venv` (override
with `QUIZ_VENV`), installs Playwright into it, downloads Chromium, and re-execs.
That is a one-time, well-over-100 MB download, after which the check costs
milliseconds. `python3 <scripts>/bootstrap.py --dry-run` prints what it would do
without doing it.

The virtualenv is deliberately outside the plugin: it survives plugin updates and is
the same on DSH and Claude Code. It also survives an uninstall — delete
`~/.quiz/venv` by hand if you want the space back.

## The two skills

- **`quiz-create`** — write a quiz-set JSON, then `scripts/validate.py` checks it
  against the *same* validator the server uses (`backend/quiz_app/validation.py`).
- **`quiz-upload`** — `scripts/upload.py` posts it to `/quiz/api/admin/sets` and can
  publish. It drives the Cloudflare Access one-time-PIN flow (`--request-otp` /
  `--finish-login`), and the agent reads the code email through the Gmail MCP.

Both resolve `<scripts>` as the `scripts/` directory beside the `SKILL.md`, so they
work regardless of the directory you start the agent in.
