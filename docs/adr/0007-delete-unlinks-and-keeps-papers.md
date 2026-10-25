# 7. Delete unlinks and never closes an attempt

Status: Accepted
Date: 2026-10-24

## Context

Delete was unreachable: `attempts.set_id NOT NULL REFERENCES quiz_sets ON DELETE
RESTRICT` meant a set with attempts could not be deleted. With attempts owning their
paper (ADR 5), deleting a set no longer deletes the content a solver's record needs.

## Decision

- `attempts.set_id` is nullable with `ON DELETE SET NULL`; delete is a real
  `DELETE FROM quiz_sets`, not a tombstone.
- Deleting a set removes the catalogue — `quiz_sets`, `questions`, `options`, blobs —
  and nothing else. `attempt_questions`, `attempt_options`, `attempt_selections`,
  `attempt_results` all survive.
- Delete is one immediate step: no grace window, no purge. The grace window existed
  only to defer a destructive act, and there is no destructive act left.
- Delete never closes an open attempt: it succeeds, and the attempt continues and
  finishes normally from its intact paper.
- Archive is unchanged: reversible, hides from solvers only, and attempts on archived
  sets resume and finish.

## Consequences

- Edit, archive and delete no longer degrade history; the full breakdown survives a
  deleted set, including question text and the answer key, readable by anyone who
  attempted it — the intent, since the record belongs to the solver.
- Force-close machinery, the `cancelled` status, and "attempt was removed by its
  author" messaging are all deleted with the purge model.
- Retention (how long papers and blobs are kept) is now an open question, not a
  purge question.

## Alternatives rejected

- Tombstone / soft delete (contradicts "gone forever" and needs a filter in every
  read path).
- Refuse delete when attempts exist (the status quo, rejected with ADR 5).
- Refuse delete while an attempt is open (an abandoned paused attempt would block
  deletion indefinitely).
