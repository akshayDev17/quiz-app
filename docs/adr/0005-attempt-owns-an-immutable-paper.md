# 5. An attempt owns an immutable paper

Status: Accepted
Date: 2026-10-24

## Context

Three defects shared one root cause: a played set could never be edited, content
could drift under an in-flight attempt, and history was a live join so renaming a
set rewrote every past attempt's name. The schema stored mutable content that
immutable history referenced, and an attempt is a long-running transaction no
isolation level spans.

## Decision

When an attempt starts, copy into attempt-owned rows:

- the questions, options, points, explanations and option ids (`attempt_questions`,
  `attempt_options`) — the paper;
- the display identity — `set_name`, `topic_name`, `difficulty` — so history renders
  from the copy;
- the behaviour it is graded and shown by — `scoring_policy`, `reveal_answers`, and
  the shuffle outcome — so flipping a rule mid-attempt cannot change a score.

Selections and results reference the attempt-owned rows, never the live tables.
Play, resume, grading and review read the paper only.

## Consequences

- Editing a played set becomes safe; the edit refusal is deleted outright.
- Resume is deterministic; content drift is impossible; rename no longer rewrites
  history.
- Storage grows per attempt (~8 KB of text per 10-question set; media is copied as
  URLs, never bytes).
- The paper is written in served order, shuffle happening once at start, so a later
  `shuffle_*` edit cannot reorder a running attempt.

## Alternatives rejected

- Immutable versions + pinned `version_id` (cheaper at scale; revisit when the
  duplication is uncomfortable).
- SCD Type 2 / temporal tables (heavy; silently identical to live rows unless the
  as-of key is persisted on the attempt).
- Event sourcing (degenerates into the snapshot model anyway).
- Live rows + stable ids, the Google Forms model (rejected on domain grounds: a form
  collects opinions, a quiz grades against an answer key).
