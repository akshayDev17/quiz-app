# Deploying quiz-app

A checklist, in order. **Access is set up before anything is deployed**, so
`/quiz` is never publicly reachable, not even for a minute. Sections A to G match
the order you do them in; "Verify after first deploy" lists what only the real
platform can prove.

> **Precondition: do not push to `main` before completing §A to §C** (Access, D1
> with its `database_id` committed, and the `ADMIN_EMAILS` secret), plus the
> GitHub `production` environment of §E. CI deploys on every push to `main`. The
> API job refuses to run while `backend/wrangler.jsonc` still holds the
> `REPLACE_AFTER_d1_create` placeholder, and the frontend job waits for the API
> job, but neither check knows whether Access exists.

Topology (details in [design.md](design.md) §2 and §7):

```
akshayprabhakant.com/quiz/api/*   → backend Worker  (Python + D1)   backend/wrangler.jsonc
akshayprabhakant.com/quiz, /quiz/* → frontend Worker (static assets)  frontend/wrangler.jsonc
everything else                    → GitHub Pages (untouched)
```

The routes come from the `wrangler.jsonc` files, so nothing is set in the
dashboard. DNS for `akshayprabhakant.com` is already proxied (orange cloud),
which routes require; the archive relies on it too.

---

## A. Cloudflare Access (first, before any deploy)

Cloudflare One → Access → Applications
(`dash.cloudflare.com/<account>/one/access-controls/apps`). Add a **new**
application. Do not add destinations to the archive's existing app: one app has
one policy, so anyone invited to the quiz would also get through to the archive's
copy desk.

1. **Add an application → Self-hosted.** Name it `Quiz Room`.
2. **Destinations** (public hostname). Add two, both with domain
   `akshayprabhakant.com`:
   - path `quiz`
   - path `quiz/*`

   Both are needed, because a wildcard "does not cover the parent path"
   (`ai-chat-archive/docs/access-limits.md` §2). `quiz/*` already covers
   `/quiz/api/*`, so the API needs no destination of its own.
3. **Session duration:** **24 h or longer.** It must comfortably exceed the
   longest quiz, or a session can expire mid-attempt. The app recovers, but it is
   a jolt. 1 week is fine for an invite-only quiz.
4. **Login methods:** One-time PIN. It is already enabled account-wide for the
   archive; if it is not listed, enable it under Settings → Authentication.
5. **Policy:** name `Invited solvers`, Action **Allow**, Include → **Emails** →
   you plus each invitee.
   - **Never** use Include → "Login Methods: One-time PIN" alone. That lets *any*
     email in (`access-limits.md` §6).
   - Optional: create an Access **group** "Quiz solvers" first and Include that
     group, so inviting someone later means editing one list.
6. Leave the CORS settings, the App Launcher and the cookie settings at their
   defaults. Everything is same-origin.
7. Save. Then check:

   ```sh
   curl -sI https://akshayprabhakant.com/quiz
   ```

   It should give `302` to `<team>.cloudflareaccess.com`. (GitHub Pages is still
   the origin at this point, and that is fine.)

## B. D1 (CLI, not the dashboard)

```sh
cd backend
npx wrangler d1 create quiz-app --location apac
```

Paste the printed `database_id` into `backend/wrangler.jsonc` (replacing
`REPLACE_AFTER_d1_create`) and commit it. Then apply the schema:

```sh
npx wrangler d1 migrations apply quiz-app --remote
```

CI repeats the `migrations apply` before every backend deploy; it is idempotent,
so later migrations ship by adding a file under `backend/migrations/`.

## C. Admin secret

```sh
cd backend
npx wrangler secret put ADMIN_EMAILS
```

Enter your email (comma-separated for several; case-insensitive). Wrangler
creates the Worker if it does not exist yet. It is a secret, not a `vars` entry,
so admin emails never land in the repo.

## D. Deploy

```sh
cd backend  && uv run pywrangler deploy
cd frontend && npm run build && npx wrangler deploy
```

Do this by hand once, or skip it and let CI do it (§E) on the first push to
`main`. Never deploy before §A is done.

A missing `ADMIN_EMAILS` does not fail the deploy: the Worker treats it as an
empty list, so it deploys fine but nobody is an admin and `/quiz/admin` shows
"Not available".

## E. CI (deploy on push)

In github.com/akshayDev17/quiz-app → Settings → Environments, create
`production`, then add two **environment secrets**. GitHub secrets are per-repo
and cannot be copied across or read back, so both must be entered again:

- `CLOUDFLARE_ACCOUNT_ID`: the same value as the archive's (it is your account
  id).
- `CLOUDFLARE_API_TOKEN`: preferably a **new** token just for this repo, so each
  repo can be rotated or revoked on its own. Create it in dash.cloudflare.com →
  My Profile → API Tokens, from the **Edit Cloudflare Workers** template, adding
  **Account · D1 · Edit**, and scope the zone to `akshayprabhakant.com`. Reusing
  the archive's token also works if you still have its value, but Cloudflare shows
  a token only once.

`.github/workflows/ci.yml` runs the tests on every push and pull request. On
`main`, after the tests pass, two jobs run under `environment: production`:
**Deploy API** (secrets check, D1 reachability check, `d1 migrations apply`,
`pywrangler deploy`) and **Deploy Frontend** (`npm run build`, `wrangler deploy`).
The D1 check fails the job early if the token lacks D1 Edit, instead of letting
the migration fail or silently do nothing behind a green tick.

## F. Verify

- `curl -sI https://akshayprabhakant.com/quiz` and `…/quiz/api/me` both give a
  302 to Access.
- `curl -sI https://akshayprabhakant.com/chat-archives` gives a 200 with no
  Access redirect (the archive is untouched).
- `curl -s https://akshayprabhakant.com/api/health` still shows the archive's
  health JSON.
- In a browser, signing in via OTP lands on `/quiz` with the name prompt, and
  `/quiz/api/me` shows `role: admin`.
- An email *not* on the policy gets "A code has been emailed to you", but no code
  ever arrives. That is Access's documented behaviour.

Then work through "Verify after first deploy" below.

## G. Inviting someone later

Add their email to the policy (or the group) from §A.5. No deploy is needed;
inviting is an Access edit only.

---

## Loading quizzes

1. Sign in as an admin (an email in `ADMIN_EMAILS`) and open `/quiz/admin`.
2. Upload a quiz-set JSON file. The shape is in [design.md](design.md) §4,
   "Authoring in v1": `topic`, optional `subtopic`, `difficulty`, `style`,
   `time_limit_minutes`, `scoring_policy`, and `questions` with `options` that
   each carry `body` and `correct`. Topics and subtopics are found by slug or
   created.
3. An import lands as a **draft**. Click Publish in the same page to make it
   visible to solvers. A set that fails validation (fewer than 2 options, no
   correct option, empty prompt) is rejected with the reason.

## Local development

Backend: the real `Api` over SQLite, with a fixed dev identity and no Cloudflare.

```sh
cd backend
python3 local_server.py          # http://127.0.0.1:8787/quiz/api/me
```

Environment: `PORT`, `DB_PATH`, `DEV_EMAIL` (default `dev@example.com`),
`ADMIN_EMAILS` (default `DEV_EMAIL`, so `/admin` works).

Frontend, pointed at that server:

```sh
cd frontend
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8787 npm run dev
```

Tests:

```sh
cd backend  && for t in test/test_*.py; do python3 $t || exit 1; done && uv run pytest -q
cd frontend && npm run test:lib && npm run test:worker && npm run build:check
```

---

## Verify after first deploy

Some behaviour depends on the Python Workers and D1 runtimes and cannot be tested
off-platform: the local server and the test suite use SQLite and a fixed identity.
Each item below is an assumption the code makes. Check them once, after the first
deploy, signed in through Access. Run the snippets in the browser's DevTools
console on any `https://akshayprabhakant.com/quiz/...` page (the Access cookie
makes them same-origin and authenticated). `SET_ID` and `SET_ID_2` are the ids of
two published sets with at least two questions each; take them from
`/quiz/api/topics`. Starting an attempt consumes one of the set's
`max_attempts` (if it has a limit), so use throwaway sets, or ones with no limit.

If one fails, the "if not" note says where to look.

**(a) `self.ctx.access` identity works.** After OTP sign-in, open
`https://akshayprabhakant.com/quiz/api/me`. Expect JSON with your email and
`role: admin`. *If not:* there is no fallback. `CloudflareAccessIdentity`
(`backend/quiz_app/auth.py`) fails closed, so without `ctx.access` every
`/quiz/api` route answers 401. (`ctx.access` in Python Workers is undocumented;
the archive's `access-limits.md` §8 records that question.) The fix would be a new
`IdentityProvider` that verifies the `Cf-Access-Jwt-Assertion` JWT against the
team's JWKS. That is not implemented.

**(b) A PUT answer returns 204.** The empty-body `Response("", status=204)` must
be accepted by the runtime.

```js
const a = await (await fetch('/quiz/api/sets/SET_ID/attempts', {method: 'POST'})).json();
const q = a.questions[0];
const r = await fetch(`/quiz/api/attempts/${a.attempt.id}/answers/${q.id}`, {
  method: 'PUT', headers: {'content-type': 'application/json'},
  body: JSON.stringify({option_ids: [q.options[0].id]}),
});
console.log(r.status, JSON.stringify(await r.text()));   // 204 ""
```

*If not:* a 500 or a hung request points at `_response` in
`backend/quiz_app/entry.py`.

**(c) `await request.text()` body parsing works.** Rename yourself and read it
back:

```js
await fetch('/quiz/api/me', {method: 'PATCH', headers: {'content-type': 'application/json'},
  body: JSON.stringify({display_name: 'Deploy Check'})});
console.log(await (await fetch('/quiz/api/me')).json());  // display_name: "Deploy Check"
```

*If not:* a 422 "malformed" means the body arrived empty or undecoded; check
`decode_body` and the `request.text()` call in `entry.py`. Rename yourself back
afterwards.

**(d) Starting the same set twice concurrently returns one attempt.** D1's UNIQUE
error text must contain `UNIQUE constraint failed` (the code matches on it). Use
`SET_ID_2`, a set you have no open attempt on, or the second request would just
resume the open one and prove nothing. If `max_attempts` is set, this and (e)
use up one attempt of it.

```js
const r = await Promise.all([1, 2].map(() =>
  fetch('/quiz/api/sets/SET_ID_2/attempts', {method: 'POST'}).then(x => x.json())));
console.log(r[0].attempt.id === r[1].attempt.id);         // true
```

*If not:* two ids, or a 500, means D1 words the error differently; check the
`except` in `D1AttemptRepository.create` (`backend/quiz_app/d1/attempts.py`) and
widen the match.

**(e) `UPDATE … RETURNING` with `.first()` works.** Submit the attempt from (d)
twice and compare:

```js
const id = r[0].attempt.id;
const s = [await fetch(`/quiz/api/attempts/${id}/submit`, {method: 'POST'}).then(x => x.json()),
           await fetch(`/quiz/api/attempts/${id}/submit`, {method: 'POST'}).then(x => x.json())];
const res = await fetch(`/quiz/api/attempts/${id}/results`).then(x => x.json());
console.log(s, res.attempt);                               // same status both times, one score, no 500
```

Expect two identical `{attempt_id, status}` answers and one score. Results are
written only by the call that flips the row out of `in_progress`; a second write
would collide on the `attempt_results` primary key and surface as a 500.
*If not:* `finish` in `backend/quiz_app/d1/attempts.py` is the place; `.first()`
must return nothing for an `UPDATE … RETURNING` that matched no row.

**(f) `/quiz/play/` with a trailing slash stays inside `/quiz`.** Visit
`https://akshayprabhakant.com/quiz/play/` by hand. It must redirect to
`/quiz/play` (or serve it), never to `akshayprabhakant.com/play` on GitHub Pages.
Behind Access, `curl` only sees the login redirect, so watch the Network tab in
the browser.

*If not:* `reprefixRedirect` in `frontend/worker.js` (covered by
`frontend/worker.test.mjs`) is the place; compare the real `Location` header with
what the stub assumes.
