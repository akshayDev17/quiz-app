# tools/ — a DSH plugin for the quiz app

Two skills that author and ship quiz sets to `/quiz`, packaged as a **DSH plugin**
(`plugin.json` + `lib/` skill-provider + `cordis.patch.yml` + `skills/`), so it
installs on any machine with one command — no hand-made symlinks.

## Install (any machine)

From the quiz-app repo:

```sh
dsh plugin --profile web add file:"$PWD/tools"
```

`file:` copies the plugin into the profile's `node_modules`, which is **required** —
at boot DSH resolves `@deepseek-ai/dsh-skill-filesystem` (a DSH-internal package)
relative to that location. Don't use `link:`: the symlink resolves back to this
repo and breaks that resolution. To ship edits, remove + re-add (or bump the
version). `dsh plugin add` writes into both `dependencies` and
`dsh.profile.bundles`, so this one command is the whole install. Restart `dsh web`
to load the skills. On another laptop: clone the repo and run the same one command.

Publish to npm and install by name instead (self-contained, but you re-install to
ship changes):

```sh
cd tools && npm publish
dsh plugin --profile web add quiz-tools
```

## The two skills

- **`quiz-create`** — write a quiz-set JSON, then `scripts/validate.py` checks it
  against the *same* validator the server uses (`backend/quiz_app/validation.py`).
- **`quiz-upload`** — `scripts/upload.py` posts it to `/quiz/api/admin/sets` and can
  publish. It drives the Cloudflare Access one-time-PIN flow (`--request-otp` /
  `--finish-login`), and the agent reads the code email via the Gmail MCP.
