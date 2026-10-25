# 3. Cloudflare Access email-OTP gate; `ADMIN_EMAILS` derives the admin role

Status: Accepted
Date: 2026-10-24

## Context

The app is invite-only. It reuses the archive's auth model: Cloudflare Access sits
in front of the app and issues an email one-time PIN; the backend trusts the
identity Access already resolved.

## Decision

- One Access application covers `akshayprabhakant.com/quiz` and `/quiz/*`, with a
  One-time PIN login and a policy of `Include → Emails` listing invited addresses.
  Both the `quiz` and `quiz/*` destinations are added, because a wildcard does not
  cover the parent path.
- The invite list is the Access policy. Inviting someone later is an Access edit, no
  deploy and no app code.
- Admin is not a stored role: it is derived at runtime from the Worker secret
  `ADMIN_EMAILS` (comma-separated, case-insensitive). It is a secret, never a
  `vars` entry, so admin emails never land in the repo.
- Session duration is 24 h or longer, comfortably exceeding the longest quiz.

## Consequences

- `ctx.access` is present on every API request, so the backend reads the email with
  no hand-rolled crypto.
- `Include → "Login Methods: One-time PIN"` alone is forbidden: it would admit any
  email, not the invite list.
- A missing `ADMIN_EMAILS` deploys fine but makes nobody an admin, so `/quiz/admin`
  reports "Not available" rather than failing the deploy.

## Alternatives considered

- `Include → "Login Methods: One-time PIN"` alone — rejected: it admits any email,
  which defeats invite-only.
- Admin emails in a `vars` entry or hardcoded — rejected: the emails would land in the
  repo; `ADMIN_EMAILS` is a secret for exactly that reason.
- An Access group ("Quiz solvers") instead of an inline Emails list — considered and
  acceptable; the inline list was chosen for simplicity, and a group can be adopted
  later to make inviting a one-list edit.
