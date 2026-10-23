# quiz-app — design

Invite-only, timed, multiple-choice quizzes at `akshayprabhakant.com/quiz`.
Built on the same stack and conventions as `ai-chat-archive`, so the two
projects share their deploy approach, their auth model and the habits they're
built with.

Calls marked **(my call)** were not specified and are open to change.

---

## 1. What it must do

- Questions belong to a **set**. A set belongs to a **topic** (a course, such as
  RAG or Harness Engineering), and optionally to a **subtopic** inside it (a
  module or a concept). A set may also carry a difficulty and/or be
  scenario-based. "Set N" is a number within that group, not typed by hand:
  `RAG › Embeddings and vector space · Set 1`,
  `Harness Engineering › Prefix caching · Scenario · Set 1`,
  `RAG › Easy · Set 2` (whole-course).
- Each question has **N options** (any N ≥ 2). The frontend renders them
  dynamically, with no fixed A–D layout.
- **Any number of options may be correct**, for example A, B and D out of A–E.
- A set has an optional **time limit in whole minutes**. `NULL` means untimed.
- When time runs out the quiz **halts and redirects to the scores page**.
- **No feedback during the quiz.** Grading happens only on (a) the deadline
  passing, or (b) Submit followed by confirming the dialog.
- **Invite-only.** Cloudflare Access with email OTP, exactly as in the
  archive: email → OTP from Cloudflare → in.

**Non-goals for v1:** other question types (free text, ordering), leaderboards,
anti-cheat (tab-switch detection, proctoring), public sharing of results.

---

## 2. Topology

```
akshayprabhakant.com/quiz/api/*   → quiz-app-backend   (Python Worker, D1)
akshayprabhakant.com/quiz         → quiz-app-frontend  (static-assets Worker)
akshayprabhakant.com/quiz/*       → quiz-app-frontend
akshayprabhakant.com/api/*        → ai-chat-archive backend   (untouched)
akshayprabhakant.com/chat-archives/*, /_next/* → archive frontend (untouched)
everything else                   → GitHub Pages portfolio     (untouched)
```

- **Most-specific route wins**, so `/quiz/api/*` beats `/quiz/*`. This is the
  same mechanism the archive relies on for `/api/*` vs GitHub Pages.
- **The API lives under `/quiz/api/*`, not `/api/quiz/*`**, so the archive's
  Worker route stays exactly as it is, and one Access application covers the
  whole quiz app.
- **The Next.js `basePath` must be `/quiz`.** The archive frontend already
  claims `akshayprabhakant.com/_next/*`. Without a basePath the quiz's chunks
  would be served by the archive's Worker and 404.
- Same hostname, so the `CF_Authorization` cookie covers both the pages and
  the API: one sign-in.
- New D1 database `quiz-app`, created with `--location apac` like the archive.
- `workers_dev: false` on both Workers, reached via Routes and never a Custom
  Domain (a Custom Domain would swallow every path).

### Auth

Simpler than the archive. Nothing in the quiz app is public, so **one Access
application on `akshayprabhakant.com/quiz` and `/quiz/*`** with an email OTP
policy listing invited addresses.

- **The invite list is the Access policy.** Adding a friend means adding their
  email in Zero Trust → Access → the app's policy. No app code is involved.
- Since Access sits in front of every quiz path, `ctx.access` is present on
  every API request. The backend reuses the archive's `IdentityProvider` port
  as is (`CloudflareAccessIdentity` in prod, `DevIdentity` locally) and still
  **fails closed**: no identity means 401.
- On first authenticated request, upsert a `users` row with role `solver`.
  Access gives only an email, so `display_name` starts empty, and the first
  visit shows a one-time **"What should we call you?"** prompt
  (`PATCH /me {display_name}`). The masthead shows the name, falling back to
  the email until it is set.
  Admins are bootstrapped from a Worker secret `ADMIN_EMAILS`, which keeps your email out of the repo. **(my call)**
- Query strings are fine here (e.g. `/quiz/play?attempt=…`). The archive
  avoided them only because Access can't scope a policy by query string. With
  one policy covering everything, that doesn't matter, and it lets a static
  export serve dynamic pages without a path-rewriting Worker.

---

## 3. DB schema (D1)

Source of truth: [`backend/migrations/0001_init.sql`](../backend/migrations/0001_init.sql).
It has been checked against SQLite: these all reject bad rows — the
one-open-attempt index; the no-duplicate-"Set N" index; the rule that a
subtopic must belong to its set's own topic; the difficulty, display-name and
`time_limit_minutes > 0` checks; and the rule that an expired attempt must
have been timed.

```
users(email PK, display_name, role[solver|admin], created_at)

topics(id, slug UNIQUE, name, description, position, created_at)       RAG, Harness Engineering
  ├─< subtopics(id, topic_id, slug, name, position)                      Embeddings…, Prefix caching
  │     └─< quiz_sets.subtopic_id  (NULL = whole-topic set)
  └─< quiz_sets(id, topic_id, subtopic_id NULL,
  │             difficulty NULL[easy|medium|hard], style[standard|scenario],
  │             seq ("Set N"), title NULL (override), description,
  │             time_limit_minutes NULL=untimed,
  │             scoring_policy[all_or_nothing|partial],
  │             shuffle_questions, shuffle_options, reveal_answers,
  │             max_attempts NULL=unlimited,
  │             status[draft|published|archived], created_by, …)
  │     └─< questions(id, set_id, position, prompt(md), explanation(md), points)
  │           └─< options(id, question_id, position, body(md), is_correct)
  │
  └─ quiz_sets ─< attempts(id uuid, set_id, user_email, started_at,
                           deadline_at NULL=untimed, finished_at,
                           status[in_progress|submitted|expired],
                           score, max_score)
                    ├─< attempt_selections(attempt_id, question_id, option_id)   PK = all 3
                    └─< attempt_results(attempt_id, question_id, awarded_points, is_correct)
```

Design notes:

| Decision | Why |
|---|---|
| `is_correct` lives on each **option row** | This is what allows "A, B, D are correct". A question's answer key is `{option ids where is_correct = 1}`. |
| ≥ 1 correct option per question is checked in **code** (`QuizValidator`, on publish) | A SQLite CHECK can't look at sibling rows. A trigger could, but it would also fire mid-edit while an author is adding options. |
| Letters A/B/C are **not stored** | They come from display order, which can be shuffled per attempt. Storing them would make the shuffle contradict them. |
| `deadline_at` is **computed once at start** and stored | The server's clock decides. Refreshing, closing or reopening the tab can't reset the timer. |
| Partial unique index: one `in_progress` attempt per (set, user) | Pressing "Start" twice, or in two tabs, resumes the same attempt instead of creating a second one. |
| `attempt_selections` is one row per ticked option | Multi-select needs no JSON column. Saving an answer is a delete-then-insert of that question's rows in one D1 `batch()`. |
| `attempt_results` is written **once**, at grading | Scores never move afterwards, even if an author later edits the question. |
| Topic → optional **subtopic** → set (not a strict 3 levels) | Some quizzes cover a whole course ("RAG, Easy, Set 1"), others one module or concept ("Prefix caching, Set 1"). A nullable `subtopic_id` covers both without inventing a "General" subtopic. |
| Subtopics are **authored freely**, not seeded from the coursework folders | "Prefix caching" is a concept inside a module, not a module itself. Coursework modules are a good starting list, not a constraint. |
| **Difficulty and style are separate columns**, both optional | "Easy" and "scenario-based" are independent: a set can be both. As columns rather than free-text tags they can be filtered and grouped. |
| **Set names are derived**, not stored: `[subtopic] · [difficulty] · [Scenario] · Set {seq}` | `seq` is assigned as max+1 within its (topic, subtopic, difficulty, style) group, so "Set 2" can't be mistyped. An optional `title` overrides the name for one-offs. |
| Composite FK `(subtopic_id, topic_id) → subtopics(id, topic_id)` | A set can't point at another course's subtopic. D1 enforces foreign keys by default. |
| Epoch-ms integers for all times | Deadline checks become integer comparisons, with no ISO parsing in Python or JS. |

**Editing a set after people have attempted it (my call):** a published set
that has any attempts is **locked**. To change it, *Clone as new draft*. The
clone takes the next `seq` in its group (`Set 1` → `Set 3`), and the original
can be archived. Old attempts keep pointing at the old questions, so
their review pages stay truthful. This is cheaper than full row versioning and
covers the realistic case.

---

## 4. Backend

Python Worker, same layout and conventions as `ai-chat-archive/backend`:
ports as ABCs, frozen dataclasses for the domain, a composition root in
`entry.py`, three repository implementations (D1, SQLite, in-memory) checked by
one contract test, and a stdlib `local_server.py`.

```
backend/
├── quiz_app/
│   ├── entry.py              # WorkerEntrypoint: composition root + routing
│   ├── auth.py               # IdentityProvider port (copied from the archive)
│   ├── models.py             # Topic, QuizSet, Question, Option, Attempt, …
│   ├── ports.py              # QuizCatalog, QuizAuthoring, AttemptRepository, Clock
│   ├── timing.py             # TimeLimit: NoTimeLimit | FixedTimeLimit
│   ├── scoring.py            # ScoringPolicy + ScoringPolicyFactory
│   ├── shuffle.py            # deterministic, attempt-seeded ordering
│   ├── services/
│   │   ├── attempts.py       # AttemptService: start/resume, save, submit, expire
│   │   ├── grading.py        # Grader: answers × answer key × policy → results
│   │   └── authoring.py      # AuthoringService + QuizValidator + JSON import
│   ├── serializers.py        # SolverView vs ReviewView (see "leak-proofing")
│   ├── repository_d1.py
│   ├── repository_sqlite.py  # local dev
│   └── repository_memory.py  # tests
├── local_server.py
├── test/
│   ├── test_repository_contract.py   # same assertions × 3 repositories
│   ├── test_scoring.py
│   ├── test_attempt_lifecycle.py     # uses FakeClock: expiry without sleeping
│   └── test_no_answer_leak.py        # no solver payload ever contains is_correct
├── migrations/0001_init.sql
└── wrangler.jsonc
```

### API

All paths are under `/quiz/api`. All require an identity. `attempt` endpoints
also require `attempt.user_email == caller` and return **404, not 403**,
otherwise, so an attempt's existence isn't revealed.

| Method & path | Does |
|---|---|
| `GET  /me` · `PATCH /me` | email, display name, role · set your display name (the first-visit prompt) |
| `GET  /topics` | topics → subtopic groups → published sets: derived name, chips (difficulty, scenario, time limit, question count), your last score |
| `GET  /sets/{id}` | set intro: rules, time limit, attempts used / allowed. No questions. |
| `POST /sets/{id}/attempts` | **start or resume**: returns attempt, `deadline_at`, `server_now`, questions in solver view, saved selections |
| `GET  /attempts/{id}` | resume (same payload). **Lazily expires** if past deadline (see below). |
| `PUT  /attempts/{id}/answers/{questionId}` | body `{"option_ids":[…]}`, autosave. 409 if finished, 422 if an option isn't in that question. |
| `POST /attempts/{id}/submit` | grade now (idempotent: a second call returns the same result) |
| `GET  /attempts/{id}/results` | 409 while in progress. Review view after. |
| `GET  /attempts` | your history |
| `POST /admin/sets` | import a set from JSON (admin) |
| `POST /admin/sets/{id}/publish` · `/archive` · `/clone` | lifecycle (admin) |
| `GET  /admin/sets/{id}/attempts` | who took it, scores (admin) |

### How time is enforced

The server's clock is the only one that counts. The browser just shows it.

1. **Start**: `deadline_at = now + minutes × 60 000`, or `NULL` if untimed.
2. **Display**: the response carries `server_now`. The browser stores
   `offset = server_now − Date.now()` and counts down to `deadline_at` against
   its corrected clock, so a wrong laptop clock doesn't matter.
3. **At zero**: the browser flushes any unsaved answer, calls `submit`, and
   redirects to `/quiz/results?attempt=…`.
4. **If the tab was closed**, nobody calls `submit`. Any read of that attempt
   (resume, results, history, `/topics`) first runs
   `AttemptService.expire_if_due()`, which grades whatever was saved and sets
   `status = 'expired'`. No cron is needed; a Cron Trigger sweep can be added
   later if admin views need finished rows without anyone opening them.
   **(my call)**
5. **Writes after the deadline** are rejected beyond a **10 s grace**, which
   absorbs the in-flight autosave at the buzzer. **(my call)**

### No feedback during the quiz

This is enforced by types, not just by convention:

- `QuizCatalog` (the port solver code depends on) returns
  `QuestionForSolver` / `OptionForSolver`. **These dataclasses have no
  `is_correct` field**, so solver code can't leak it by accident.
- The answer key is reachable only through `AnswerKeyReader`, which only the
  `Grader` holds.
- `test_no_answer_leak.py` walks every solver endpoint's JSON and fails if
  `is_correct`, `explanation` or `score` appears before the attempt is
  finished.
- Saving an answer returns `204` with no body, so nothing hints at
  correctness.

### Scoring

Per question, `C` = correct option set and `S` = selected set.

- **`all_or_nothing`** (default): full points iff `S == C`, else 0.
- **`partial`**: `points × max(0, (|S∩C| − |S∖C|) / |C|)`. Each wrong tick
  cancels a right one, so ticking everything scores 0.

A blank answer always scores 0. `attempt_results.is_correct` always records
exact match, so the review page can mark ✓/✗ under either policy.

### Applying SOLID, OOP and patterns, where they're worth it

| Principle / pattern | Where | What it buys |
|---|---|---|
| **Strategy + Factory** | `ScoringPolicy` ABC → `AllOrNothing`, `PartialCredit`. `ScoringPolicyFactory.for_set(set)` maps `quiz_sets.scoring_policy` → instance via a registry dict. | This is the factory that pulls its weight: the policy is data in a row, and code needs an object. A new policy (e.g. negative marking) is one class plus one registry line. The `Grader` never changes (Open/Closed). |
| **Null Object** | `TimeLimit` ABC → `FixedTimeLimit(minutes)`, `NoTimeLimit`. Methods: `deadline(started_at)`, `is_expired(attempt, now)`. Built by `TimeLimit.of(set)`. | Untimed quizzes stop being `if deadline is not None` scattered through services and serializers. `NoTimeLimit.is_expired` just returns `False`. Both can stand in for each other (Liskov). |
| **Interface Segregation** | `QuizCatalog` (solver reads, no answers) vs `AnswerKeyReader` (grader only) vs `QuizAuthoring` (admin writes). One D1 class may implement all three. | Each consumer sees only what it needs, and the leak-proofing above falls out of this. |
| **Dependency Inversion** | Services take ports and a `Clock` in their constructor. `entry.py` wires D1 + `SystemClock` + `CloudflareAccessIdentity`, tests wire memory + `FakeClock` + `DevIdentity`. | Timeout tests advance a fake clock instead of sleeping, and the same services run in the Worker, locally and in tests. |
| **Single Responsibility** | `AttemptService` (lifecycle), `Grader` (marking), `QuizValidator` (publish rules), serializers (wire shape) | Each one has one reason to change. |
| **Guarded state transitions** | `Attempt` has `record_selection`, `submit(now)` and `expire(now)`, which raise `AttemptClosed` from any non-open state. | A full State-pattern class hierarchy would be overkill for 3 states and 2 transitions. An enum plus guarded methods on one class is enough. |
| **Repository + contract test** | three implementations, one test suite | Same as the archive: an implementation that drifts fails on its own. |
| **Not used (on purpose)** | a `QuestionTypeFactory` | Only one question type exists. Add it the day a second type shows up, not before. |

### Authoring in v1 (my call)

Sets are written as JSON, posted to `POST /admin/sets` (or loaded with a
`scripts/import_set.py` that calls it), then published. A browser editor is
phase 2. JSON shape:

```json
{
  "topic": {"slug": "rag", "name": "RAG"},
  "subtopic": {"slug": "embeddings", "name": "Embeddings and vector space"},
  "difficulty": "medium", "style": "standard",
  "time_limit_minutes": 15, "scoring_policy": "all_or_nothing",
  "questions": [
    {"prompt": "Which of these change when you swap the embedding model?",
     "explanation": "…",
     "options": [
       {"body": "Every stored vector must be re-embedded", "correct": true},
       {"body": "The vector dimension may change", "correct": true},
       {"body": "The chunking boundaries", "correct": false},
       {"body": "Similarity thresholds need re-tuning", "correct": true}]}
  ]
}
```

`topic` and `subtopic` are found by slug or created, `subtopic` may be
omitted (a whole-topic set), and `seq` is assigned by the server.
`QuizValidator` rejects any question with fewer than 2 options or 0 correct
options, and any empty prompt.

---

## 5. Frontend

Next.js (static export, `basePath: '/quiz'`), TypeScript, served by a
static-assets Worker, the same pattern as the archive. Clickable sketch:
[`design/sparks.html`](../design/sparks.html) (open `#play` or `#results` to
jump straight to those screens).

### Theme

The quiz must look like part of the same site as `my-github-io/index.html` and
`ai-chat-archive`. It uses their shared palette and type, not its own:

- **Tokens**: copy the `:root` block of
  `ai-chat-archive/frontend/app/globals.css` as is: `--paper #EEF1F8`,
  `--paper-2`, `--ink #0F1220`, `--muted`, `--rule`, `--rule-2`,
  `--accent #3A4BD8`, `--card #FFF`, `--card-line #818A9F`, the `--s1…--s7`
  spacing and `--ease`. Status colours are also the archive's: danger
  `#b00020`, warn `#8a5a00`. The only new token is `--ok #1f6b45` (for "your
  pick ✓" on the results page), because neither site needed a success colour.
  **(my call)**
- **Type**: Newsreader for body and headings, IBM Plex Mono for labels, both
  loaded via `next/font`, as in the archive's `layout.tsx`.
- **The site's recurring elements**: a masthead with a 3px double rule; mono
  uppercase micro-cap labels and blue kickers; numbered section heads
  (`01 RAG`); white cards with a 3:1 border, a neutral ink shadow and a
  hover lift; mono pill chips; ink `.btn` turning accent on hover, with a
  `.ghost` variant; and the portfolio's three-cell hairline `.stats` row for
  the score.
- **Light only.** Neither existing site has a dark mode, so the quiz doesn't
  either.
- The masthead name "The Quiz Room" is a placeholder. **(my call)**
- **Sketch-only, must not ship:** the "Spark, not the product…" note, the
  sample data, the 60-second demo timer and its scaled amber/red thresholds,
  and the `#play`/`#results` screenshot hooks.

| Page | What's on it |
|---|---|
| `/quiz` | Topics as numbered section heads (`01 RAG`). Under each topic, a small sub-head per subtopic, with whole-topic sets first, then cards. Each card shows the set's name (`Embeddings and vector space · Set 1`), chips for difficulty, **Scenario**, **"15 min" or "Untimed"** and question count, and your last score. A card with an attempt in progress shows **Resume** with the time left. |
| `/quiz/set?id=` | Intro: rules, time limit, attempts left. **"The timer starts when you press Start."** |
| `/quiz/play?attempt=` | The quiz itself (below). |
| `/quiz/results?attempt=` | Score, then a per-question review (if `reveal_answers`): each option marked *your pick ✓*, *your pick ✗*, *missed*. Explanation underneath. Header says **"Time's up — auto-submitted"** when expired. |
| `/quiz/history` | Your attempts. |
| `/quiz/admin` | (phase 2) import, publish, attempts table. |

### The play screen

- **Sticky top bar**: set title · progress `7 / 20 answered` · timer
  (`MM:SS`; hidden for untimed sets). The timer turns amber under 5 min and
  red under 1 min.
- **One question per screen**, with a **question navigator** grid (answered /
  unanswered / current) that jumps anywhere. **(my call)**: easier on long
  sets than one scrolling page.
- **Options are rendered from the array, whatever its length.** Letters come
  from position: A…Z, then AA, AB… (spreadsheet-style), so N > 26 still works.
  Number keys `1–9` toggle options.
- **Every question uses checkboxes and says "Select all that apply" (my
  call).** Using radio buttons for single-answer questions would give away
  how many answers are correct. If you'd rather tell solvers "pick 1", it's a
  per-set flag later.
- **Autosave** each answer (debounced ~400 ms) with a quiet "Saved" tick. No
  correctness signal of any kind.
- **Submit** opens a confirm dialog: *"You've answered 18 of 20. 2 unanswered
  (Q4, Q11). Once submitted you can't change answers."* → **Submit** /
  **Keep going**.
- **At 00:00**: inputs lock, a "Time's up" overlay shows for ~1.5 s, then it
  redirects to results. Refreshing the page mid-quiz resumes with the same
  deadline.
- After a finished attempt, `/quiz/play?attempt=` redirects to results, so the
  back button can't reopen the quiz.

---

## 6. Repo layout

```
quiz-app/
├── backend/        Python Worker (above)
├── frontend/       Next.js static export + worker.js + wrangler.jsonc
├── design/         sparks.html, mockups
├── docs/design.md  this file
└── .github/workflows/ci.yml   (copy the archive's: tests, then deploy both Workers)
```

## 7. Deploy checklist (once built)

1. `npx wrangler d1 create quiz-app --location apac` and put its id in
   `backend/wrangler.jsonc`.
2. `npx wrangler d1 migrations apply quiz-app --remote`
3. `uv run pywrangler deploy` (backend: route `akshayprabhakant.com/quiz/api/*`)
4. Frontend: `next build` then `wrangler deploy` (routes `…/quiz` and `…/quiz/*`)
5. Zero Trust → Access → add an application for `akshayprabhakant.com/quiz`
   and `/quiz/*`, with a One-time PIN policy, Include → Emails → the invite list.
6. `curl -I https://akshayprabhakant.com/quiz` should return a 302 to the
   Access login. The archive at `/chat-archives` should still be public.
