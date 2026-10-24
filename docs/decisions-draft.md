# Decisions — pause, editing, deletion, history

**Status:** working note. **Not** an ADR. Mine it into per-decision ADRs, then delete it.

Scope: everything that came out of the admin in-place editor and the pause
feature colliding with the content model. Each entry is written so it can be
lifted into an ADR with little editing: *Context → Decision → Consequences →
Alternatives rejected.*

**Implementation status (2026-10-24).** D1–D10 are implemented: migration
`0003_attempt_papers.sql`, the paper-scoped repositories, atomic pause, unlinked
delete, and the frontend pause buffer. Tests: `test_paper.py` (the three scenarios),
`test_migration.py` (the backfill against a pre-0003 database), plus the existing
suites updated. **Not** implemented, still open: Q1 (content-addressed versions),
Q2 (media retention — the app has no images/videos yet, so there is nothing to
retain), Q4 (retention horizon), Q6, Q7. D9 made Q5 moot.

Legend:
- **LOCKED** — explicitly agreed.
- **ACCEPTED** — agreed in principle; mechanism agreed, details may move.
- **PROPOSED** — recommended, no sign-off yet.
- **OPEN** — genuinely undecided.

---

# Part 1 — Problems

## P1. A set that has been played can never be edited

**Symptom.** `PUT /admin/sets/{id}` returns `409 set has attempts — clone it to edit`,
even when the only change is the title, or when nothing changed at all.

**Where.** `backend/quiz_app/d1/authoring.py::update` — counts
`attempts WHERE set_id = ?` first and refuses unconditionally, before looking at
what changed.

**Root cause.** The schema stores *mutable* content that *immutable* history
references:

| constraint | effect |
| --- | --- |
| `options.question_id → questions ON DELETE CASCADE` | deleting a question cascades to its options |
| `attempt_selections.question_id → questions` (RESTRICT) | a question with history cannot be deleted |
| `attempt_selections.option_id → options` (RESTRICT) | an option with history cannot be deleted |
| `attempt_results.question_id → questions` (RESTRICT) | same, for the graded rows |

`update()` works by `DELETE FROM questions WHERE set_id = ?` + re-insert, so any
set with history violates the FKs. The refusal was the cheapest way to stop that.

**Why it matters.** It makes the editor useless for exactly the sets that matter
— the published, played ones. The invariant that was actually needed is *"a graded
attempt must stay explainable"*, not *"content must never change"*.

## P2. Pause is best-effort about the answers it freezes

**Symptom.** A solver can pause successfully with an answer that never reached the
server. On resume the answer simply isn't there.

**Where.** `frontend/app/play/page.tsx::togglePause` does
`await queue.flush()` then `await pauseAttempt(id)`.

**Root cause.** `frontend/lib/saveQueue.ts::flush(budgetMs = 0)`:

- default budget `0` → no deadline; retryable errors loop with backoff indefinitely;
- a **terminal 4xx rejection is dropped from the queue rather than raised** — the
  file states it: *"flush does not wait on or reject for it"*;
- so flush resolves whether or not the answer landed.

Once `paused_at` is set, `Attempt.accepts_writes()` returns false
(`backend/quiz_app/models.py`), so nothing can retry until resume. The queue's
retry loop cannot help — the door is locked behind it.

**Why it matters.** The freeze is guaranteed and the answers are not, which is
backwards: preserving state is the entire point of pausing. Two failure modes,
both bad: pause hangs forever (network down) or pause silently loses an answer.

## P3. Content drifts under an in-flight attempt

**Where.** `backend/quiz_app/d1/catalog.py::questions_for_solver` reads live
`questions`/`options` rows on every load, including resume.

**Why it matters.** Today this is *unreachable* — not because it is handled, but
because P1 forbids the edit that would trigger it. Correctness by prohibition.

## P4. History is a live join, and delete is unreachable

**Where.**
- `backend/quiz_app/serializers.py::history` reads `info.name` from the live
  `quiz_sets` row → **renaming a set retroactively rewrites the name on every past
  attempt.**
- `attempts.set_id INTEGER NOT NULL REFERENCES quiz_sets(id) ON DELETE RESTRICT` →
  a set with attempts cannot be deleted at all.

**Why it matters.** Two of the three lifecycle operations (edit, delete) are
blocked rather than designed. Archive happens to work.

## P5. Pause makes "in flight" unbounded

`resume` only adds the paused delta to `deadline_at`
(`backend/quiz_app/d1/attempts.py::resume`), and nothing bounds how long an attempt
may stay paused. **Consequence:** every solution of the form *"refuse the admin
action while an attempt is open"* is now dead — an abandoned paused attempt would
block that set forever. This invalidates the quiesce/drain approach that was
defensible when the in-flight window was bounded by the time limit.

---

# Part 2 — Decisions

## D1. An attempt owns its paper (snapshot at start) — ACCEPTED

**Context.** P1, P3. Content must be free to change; history must stay explainable.
The DB cannot help across an attempt, because an attempt is a *long-running business
transaction* spanning many requests — no isolation level spans it.

**Decision.** When an attempt starts, copy the questions, options, points,
explanations and option ids into attempt-owned rows. Play, resume, grading and
review read **those rows only**, never the live tables.

**Consequences.**
- Editing a played set becomes safe ⇒ the P1 refusal is deleted outright.
- Resume is deterministic; content drift cannot occur.
- Storage grows per attempt. Estimate: a 100-question set is on the order of tens
  to a couple hundred KB of text; 1,000 attempts on it ≈ tens to a couple hundred MB.
  Acceptable at this scale; see Q1 if that stops being true.

**Alternatives rejected.**
- *Immutable versions + pinned `version_id`* — one copy per **edit** instead of per
  attempt, much cheaper at scale (Stripe Price / CMS revision shape), but needs
  reference-counted GC and buys storage we do not need yet. Revisit at Q1.
- *Effective dating / SCD Type 2, or temporal tables* — passes only if the as-of key
  is persisted on the attempt; a naive "current row" read is silently identical to
  live rows. Heavy for D1/D2–SQLite.
- *Event sourcing* — passes, but requires events to carry content or pin a retained
  version, i.e. it degenerates into D1 anyway.
- *Live rows + stable ids (the Google Forms model)* — **rejected on domain grounds**:
  a form collects opinions, so relabelling under a respondent is cosmetic; a quiz
  grades against an answer key, so changing a question under a paused solver corrupts
  fairness *and* storage (their partial selection may reference a deleted option).

## D2. An attempt owns the properties it is shown and graded by — ACCEPTED

**Decision.** Copy onto the attempt at start:

- display identity — `set_name`, `topic_name`, `difficulty` (history renders from it);
- **behaviour it is graded and shown by — `scoring_policy`, `reveal_answers`, and the
  shuffle outcome.**

**Why the second bullet.** `Scoring(award)` is called with the set's policy at grade
time (`backend/quiz_app/scoring.py`). Flip `partial` → `all_or_nothing` while someone
is paused mid-attempt and their score is decided by a rule that changed while they
were not looking. Same class of bug as P3, one layer up: time limit is already immune
(deadline computed at start), policy and reveal/shuffle are not.

**Consequences.** Fixes P4's rename problem; a past attempt keeps the name and the
rules it was played under. See Q3 for whether the label survives deletion.

## D3. Selections and results are rewired to the snapshot — ACCEPTED

**Context.** D1 alone is a half-measure. If `attempt_selections.option_id` still
points at live `options`, an option delete still violates an FK and still
reinterprets or orphans a partial answer.

**Decision.** `attempt_selections` and `attempt_results` reference the attempt-owned
option/question rows, not the live ones.

**Consequences.** Referential integrity is guaranteed by ownership rather than by
prohibiting edits (the point of the whole exercise). **D1 without D3 is not done** —
it looks complete and fails in exactly the scenario it was meant to fix.

## D4. Pause is atomic — LOCKED

**Context.** P2.

**Decision.** `POST /attempts/{id}/pause` carries the pending answers. The server
validates them, writes the selections and sets `paused_at` in **one transaction**.
Either both land or neither does.

**Client rules.**
- await with a **~10s timeout** — the endpoint must never hang the button;
- on failure show an actionable state (retry, or pause accepting the loss);
- page-hide keeps the existing fire-and-forget `flushKeepalive()` path, where there
  is nobody left to show a spinner to.

**Consequences.** Fewer round trips than today (1 instead of N+1), no unbounded
retry, and the failure becomes reportable. The endpoint is already idempotent
(`WHERE paused_at IS NULL`), so retries are safe. The timeout is **not optional** —
without it the change swaps "silently loses an answer" for "spins forever".

**Alternatives rejected.**
- *Budgeted flush + refuse to pause while `queue.unsaved()` is non-empty* — never
  loses an answer, but strands the solver until the network cooperates. Keep as the
  fallback if the request shape must not change.
- *Optimistic pause with rollback* — rollback assumes the user is still on the page;
  pause assumes they are leaving, so nobody ever sees the revert.

## D5. Optimistic for continuous, confirmed for boundary — ACCEPTED (principle)

**Decision.** Per-keystroke answer saving stays debounced and optimistic
(`SaveQueue` as-is). Phase-ending actions — pause, submit, resume — are confirmed,
because a wrong boundary state is unrecoverable.

**Consequences.** Guards against "make every save synchronous to feel safe", which
is the change that would actually make the app feel bad.

## D6. Delete is hard and unlinks; it is not a tombstone — ACCEPTED

**Context.** P4. Delete is defined as *gone forever*; tombstones are not.

**Decision.**
- `attempts.set_id` becomes **nullable** with `ON DELETE SET NULL`, so a real
  `DELETE FROM quiz_sets` works and the attempt keeps rendering from D2's copy.
- Row is removed; questions/options go with it.

**Alternatives rejected.**
- *Tombstone / soft delete (`deleted_at`)* — contradicts "gone forever", retains
  content, and needs a `deleted_at IS NULL` filter in **every** read path (one
  forgotten filter resurfaces a deleted quiz). Also useless for media: the blobs
  either go (dead URLs in a "preserved" row) or leak forever.
- *Refuse delete when attempts exist* — the status quo, rejected with P1.

## D7. Deleting a set keeps every attempt's paper — LOCKED

**Context.** D1 means deleting a set no longer deletes its content: it lives on inside
attempts. That was first treated as a defect to be closed by purging the papers and
degrading history to receipts.

**Superseded rationale → decision.** Purging was rejected. Deleting a quiz is an
*authoring* act. It says nothing about the solvers who already sat it, and their
record must not be rewritten because an author changed their mind. The breakdown,
including question text and the answer key, is retained for every attempt on a
deleted set.

**Decision.** A set delete removes the catalogue — `quiz_sets`, `questions`, `options`,
blobs — and **nothing else**. `attempt_questions`, `attempt_options`,
`attempt_selections`, `attempt_results` all survive.

**Result.** *"Raft basics · 72% · 24 Oct"* with the full per-question review still
available, forever. Nothing in the lifecycle degrades history any more: not edit, not
archive, not delete.

**Consequence to be aware of.** A deleted quiz's text and answer key remain readable to
anyone who attempted it. That is the intent — the record belongs to the solver.

## D8. Delete is one immediate step — no grace window, no purge — LOCKED

**Context.** D8 previously split the delete into "catalogue now, papers later (TTL)",
purely to avoid yanking a paper from someone mid-attempt.

**Decision.** With D7 there is nothing to purge, so the split disappears. Delete does
exactly one thing, immediately: removes the set's rows and blobs, nulls `set_id` on its
attempts, and leaves every paper untouched.

**Why this is simpler, not weaker.** The grace window and its TTL existed only to defer
a destructive act. Remove the destructive act and the timing problem evaporates. The
in-flight solver is protected by *never being affected* rather than by being affected
later.

**Retention is now the open question, not purge** — see Q4.

## D9. Delete never closes an open attempt — LOCKED

**Decision.** Delete always succeeds, and open attempts on that set are **not**
force-closed. They continue and finish normally, because their paper is intact and
nothing they read was deleted.

**Consequences.** This removes three pieces of machinery that the purge model needed:
the force-close path, the `cancelled` status (Q5 — no longer needed), and the
"attempt was removed by its author" messaging. A solver mid-attempt notices nothing.

**Alternatives rejected.** *Refuse delete while an attempt is open* — via P5 an
abandoned paused attempt would block deletion indefinitely.

## D10. Archive semantics are unchanged — LOCKED

**Decision.** Archive stays as-is: reversible, hides from solvers only,
`set_for_attempt()` deliberately reads **any** status
(`backend/quiz_app/d1/catalog.py`) so attempts on archived sets resume and finish.
Unarchive is already allowed — `set_status()` is an unconditional `UPDATE` with no
state machine, so archived → published is a normal one-click path.

**Note.** Archive was never the dangerous operation: it moves no rows and destroys
nothing.

---

# Part 3 — Open

**Q1. Snapshot-per-attempt vs versions-per-edit.** D1 copies per attempt. If sets
grow to 100 questions plus media *and* accumulate many attempts, versions (one copy
per edit, attempts pin `version_id`) are materially cheaper. Revisit when either
number gets uncomfortable; the schema seam (attempt references a version row vs its
own rows) is the only thing that would change.

*What the duplication actually is.* Content is copied per **attempt**, not per user —
someone retaking an unchanged quiz gets another identical copy. A 10-question ×
4-option set is 10 + 40 = 50 rows and roughly 8 KB of text per attempt; a 100-question
set is ~500 rows and ~80 KB. Ten concurrent solvers ≈ 80 KB; a thousand attempts on
the big set ≈ 80 MB. **Media is not duplicated** — a snapshot copies the image/video
*URL*, not the blob, so every attempt shares one object.

*Cheapest dedupe if it ever matters:* content-addressed versions — hash the rendered
paper at attempt start and reuse an existing version row-set when the hash matches.
Ten attempts on an unedited quiz collapse to one copy; the next edit produces a new
hash. It preserves D1's guarantees exactly, and delete becomes refcounted (purge a
version when no attempt references it) — if a purge verb ever exists. Under D7
nothing purges, so this dedupe is purely a storage optimisation.
Cost: a refcount plus an indirection on every read. Not worth building at current
scale.

**Q2. Media retention (now required, not optional).** Images/videos live in object
storage with URLs in the paper. D7 keeps the paper, so the **blobs must be kept too**
or the retained breakdown renders broken images — which defeats the point of keeping
it. Needs one of:

- *refcount at the object layer* — a `media` table with a reference count, blobs deleted
  only when their last referrer goes. Full fidelity, storage grows without bound.
  Recommended, since D7 already accepts unbounded retention.
- *retain text only* — media shows a placeholder in old reviews. Cheap, and the one
  place the record is incomplete.
- *copy the blob per attempt* — rejected; multiplies video storage by attempt count.

Note what this does **not** mean: the paper copies URLs, never bytes, so ten attempts
share one object. The cost is retention horizon, not fan-out.

**Q3. Does the copied label survive deletion?** D2's `set_name` outliving the set is
what lets a surviving attempt say which quiz it was. Under D7 the label is never
purged anyway, so this is settled by construction rather than by choice.

**Q4. Retention horizon for papers (and blobs).** Nothing purges by default any more
(D7), so growth is proportional to attempts and never reclaimed. Keep forever (coherent
with the transparency the design is built on), or degrade after N years. Either is
defensible; what is not defensible is having no answer and discovering it as a bill.

**Q5. ~~Terminal status for a force-closed attempt.~~ Resolved by D9.** Nothing is
force-closed any more, so no `cancelled` status and no enum change are needed.

**Q6. "Edited since you attempted" marker.** Cheap once attempts pin content
(compare snapshot against the live set). Optional; not required for correctness.

**Q7. Should a paused attempt ever expire on its own?** Nothing forces it for
content correctness (D1 makes pinned papers safe), but it shows up in any
"attempts in progress" UI.

---

# Part 4 — Consequences

**Schema**
- attempt-owned question/option tables;
- `attempt_selections` / `attempt_results` re-pointed at them (D3);
- `attempts.set_id` nullable + `ON DELETE SET NULL` (D6);
- copied label columns, plus pinned scoring policy / reveal / shuffle (D2);

**Backend**
- attempt start writes the paper (D1);
- solver read, grading and review read the paper, not `questions_for_solver()`;
- `authoring.update()` **loses the attempts check entirely** (P1 removed at the root);
- delete unlinks and stops there — no purge, no force-close (D6–D9);
- media retention / refcounting so kept papers do not render dead URLs (Q2);
- pause accepts a body and commits atomically (D4).

**Frontend**
- pause sends the pending buffer with a timeout and a real error state (D4);
- history renders from the copied label; the review page resolves against the paper,
  so a deleted quiz still shows its full breakdown (D7).

**Tests** — one per scenario: pause/resume unchanged; pause → edit → resume
unaffected; pause → archive → resume works; **pause → delete → resume still works and
the full breakdown survives**; deleting never closes an open attempt; pause
with an unsaved answer either saves it or refuses; flipping `scoring_policy`
mid-attempt does not change how a paused attempt grades (D2).

---

# Part 5 — Rejected alternatives, at a glance

| Alternative | Rejected because |
| --- | --- |
| Refuse edits when attempts exist (status quo) | Makes every played set read-only; no attempt to preserve history, just forbids the write |
| Soft delete / tombstone | Contradicts "gone forever"; needs a filter in every read; useless for blobs |
| Quiesce / drain (block admin action while open) | P5 — pause makes "open" unbounded |
| Live rows + stable ids (Forms model) | A quiz grades against an answer key; content drift corrupts a partial answer |
| Version-on-publish alone | A gate (when changes appear), not a pin (what this attempt reads) |
| Immutable versions + refcounted GC | Correct but heavier than needed now; revisit at Q1 |
| Optimistic pause with rollback | Rollback needs the user to still be on the page; pause assumes they are leaving |
| Pause with unbudgeted flush + hope | Loses answers silently and can hang forever (P2) |
| Purge papers on delete; degrade history to receipts | Deleting a quiz is an authoring act; it must not rewrite a solver's record. Breakdowns stay |
