# 6. Pause is atomic — optimistic continuous, confirmed at the boundary

Status: Accepted
Date: 2026-10-24

## Context

Pause was best-effort about the answers it froze: a solver could pause with an
answer that never reached the server, and `flush(budgetMs=0)` both dropped terminal
4xx rejections and looped retryable errors forever. Once `paused_at` was set, no
write could retry.

## Decision

- `POST /attempts/{id}/pause` carries the pending answers; the server validates them,
  writes the selections and sets `paused_at` in one transaction. Either both land or
  neither.
- The client awaits with a ~10 s timeout, shows an actionable failure state on error,
  and keeps the fire-and-forget `flushKeepalive()` path on page-hide.
- The endpoint is idempotent (`WHERE paused_at IS NULL`), so retries are safe.
- Principle: per-keystroke answer saving stays debounced and optimistic; the
  phase-ending actions — pause, submit, resume — are confirmed, because a wrong
  boundary state is unrecoverable.

## Consequences

- Fewer round trips (1 instead of N+1), no unbounded retry, and pause failure becomes
  reportable instead of silent.
- The timeout is not optional: without it the change swaps "silently loses an answer"
  for "spins forever".

## Alternatives rejected

- Budgeted flush + refuse to pause while unsaved answers exist (never loses an answer
  but strands the solver until the network cooperates).
- Optimistic pause with rollback (rollback assumes the user is still on the page;
  pause assumes they are leaving).
