<div align="center">
  <img src="assets/logo.svg" width="112" alt="The Quiz Room">
</div>

# The Quiz Room

[![live](https://img.shields.io/badge/live-akshayprabhakant.com%2Fquiz-3a4bd8)](https://akshayprabhakant.com/quiz)
[![CI](https://github.com/akshayDev17/quiz-app/actions/workflows/ci.yml/badge.svg)](https://github.com/akshayDev17/quiz-app/actions/workflows/ci.yml)

Invite-only, timed, multiple-choice quizzes. Questions live in **sets** under
**topics**; a question has any number of options and any number of them may be
correct; a set can carry a time limit. Nothing is marked — no right, no wrong, no
count — until the solver submits or the clock runs out.

[**Take a quiz**](https://akshayprabhakant.com/quiz) |
[**Authoring plugin**](tools/README.md) |
[**Design**](docs/design.md) |
[**Deploy**](docs/deploy.md) |
[**Stack**](#stack)

## What it is

- **Sets under topics.** "RAG › Embeddings and vector space · Set 1" is derived from
  the set's topic, subtopic, difficulty and sequence — never typed by hand.
- **Multi-correct by design.** Tick any combination; the answer key is the set of
  options marked correct, and scoring is per set (`all_or_nothing` or `partial`).
- **The server owns the clock.** The deadline is fixed at start, the browser's
  countdown only displays it, and closing the tab cannot buy time.
- **Pausing freezes the clock.** A paused attempt keeps its time, its answers, and
  the exact paper it was served.
- **History is the solver's, not the author's.** Editing or deleting a quiz never
  rewrites someone's past attempt: every attempt keeps its own copy of the
  questions, so the per-question breakdown survives even after the quiz is gone.
- **Invite-only.** Cloudflare Access with an email one-time PIN is the only way in.

## The authoring plugin → [`tools/`](tools/README.md)

Quizzes are authored and uploaded by a packaged agent plugin, not by hand-editing
JSON. It lives in this repo at **[`tools/`](tools/README.md)** and gives two skills:

| Skill | What it does |
| --- | --- |
| `quiz-create` | Writes a quiz-set JSON in the house style and validates it against the server's own rules. |
| `quiz-upload` | Logs in, imports the set, publishes it — hands-off. |

```sh
# Claude Code
claude plugin marketplace add akshayDev17/quiz-app
claude plugin install quiz-tools@quiz-app --scope user

# DSH
dsh plugin --profile web add file:"$PWD/tools"
```

**Full instructions — first-run Gmail setup, usage, troubleshooting, what it leaves
on disk — are in [`tools/README.md`](tools/README.md).**

## Repo layout

| Path | What |
| --- | --- |
| [`backend/`](backend) | Python Cloudflare Worker: the API, D1 repositories, migrations, tests. |
| [`frontend/`](frontend) | Next.js static export: the quiz UI, deployed as static assets under `/quiz`. |
| [`tools/`](tools/README.md) | **The authoring plugin** — `quiz-create` and `quiz-upload`, packaged for Claude Code and DSH. |
| [`docs/design.md`](docs/design.md) | The design: topology, auth, schema, request flows. |
| [`docs/deploy.md`](docs/deploy.md) | The deploy runbook: Access, D1, secrets, CI, first-deploy checks. |
| [`design/`](design) | Clickable frontend sketches — open the HTML in a browser. |

## Run it locally

Two processes; the frontend talks to the backend's origin.

```sh
# API + database, on :8787 (creates backend/quiz.db on first run)
cd backend && python3 local_server.py

# UI, on http://localhost:3000/quiz
cd frontend && npm install && NEXT_PUBLIC_API_BASE=http://127.0.0.1:8787 npx next dev
```

The dev server signs you in as `DEV_EMAIL` (default `dev@example.com`) and treats
that address as an admin, so `/admin` works without Cloudflare Access.

## Deploy

Per [`docs/deploy.md`](docs/deploy.md): Cloudflare Access first, then D1, then
`ADMIN_EMAILS`. CI deploys on every push to `main`, so **do not push to `main`
before §A–C are complete**.

## Stack

The same shape as `ai-chat-archive`: a Python Cloudflare Worker + D1 for the API, a
Next.js static export uploaded as static assets for the frontend, and Cloudflare
Access (email one-time PIN) as the only way in. No framework is used in the
backend — the router is a pure function of `(method, path, body, identity)`, and
every repository is the single SQL implementation that both D1 and the tests run
against.
