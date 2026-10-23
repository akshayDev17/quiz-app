# quiz-app

Invite-only, timed, multiple-choice quizzes at `akshayprabhakant.com/quiz`.
Questions live in **sets** under **topics**; each question has N options and any
number of them may be correct; a set may carry a time limit in minutes (or none).
Nothing is marked until the solver submits — or the clock does it for them.

Same stack as `ai-chat-archive`: Python Cloudflare Worker + D1 for the API,
Next.js static export on a static-assets Worker for the frontend, Cloudflare
Access (email one-time PIN) as the only way in.

- `docs/design.md` — the design: topology, auth, schema, backend, frontend
- `backend/migrations/0001_init.sql` — the D1 schema
- `docs/deploy.md` — the deploy runbook: Access, D1, secrets, CI, first-deploy checks
- `design/sparks.html` — clickable frontend sketch (open it in a browser)

Status: Implemented; deploy per docs/deploy.md. Do not push to main before completing
docs/deploy.md §A–C (Access, D1, ADMIN_EMAILS) — CI deploys on every push to main.
