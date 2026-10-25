# 4. Time is server-authoritative

Status: Accepted
Date: 2026-10-24

## Context

A timed quiz's deadline must not depend on the solver's laptop clock, a tab
refresh, or closing and reopening the browser.

## Decision

- `deadline_at` is computed once at start (`now + minutes × 60 000`) and stored. It
  is never a countdown; time left is always derived from it.
- Responses that matter carry `server_now`. The browser stores
  `offset = server_now − Date.now()` and counts down against its corrected clock.
- At zero the browser flushes any unsaved answer, calls `submit`, and redirects to
  results.
- If the tab was closed, no one calls `submit`: any subsequent read of that attempt
  runs `expire_if_due()`, which grades whatever was saved and sets
  `status = expired`. No cron is required.
- Writes after the deadline are rejected beyond a 10 s grace, which absorbs the
  in-flight autosave at the buzzer.

## Consequences

- A wrong laptop clock cannot move the deadline.
- The server clock is the single source of truth; the browser only renders it.
- Expiry is lazy (triggered by any read), with an optional Cron Trigger sweep later
  if admin views need finished rows without a read.

## Alternatives considered

- Trusting the client clock, or storing a decrementing `remaining_ms` — rejected: a
  wrong laptop clock corrupts the deadline, and a stored countdown freezes the moment
  the tab closes. Time left is always derived from the stored `deadline_at`.
- An eager cron sweep for expiry instead of lazy read-triggered expiry — considered
  and deferred: `expire_if_due()` on any read needs no scheduler, and a Cron Trigger
  can be added later if admin views need finished rows without a read.
