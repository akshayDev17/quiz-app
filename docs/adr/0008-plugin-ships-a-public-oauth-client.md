# 8. The plugin ships a public Google OAuth client

Status: Accepted
Date: 2026-10-25

## Context

The upload skill must cross Cloudflare Access without a browser, and every upload
must be attributable to the human who made it (an admin today, and later a
signed-up creator of private quizzes). Access's one-time PIN is the identity
mechanism: it binds a human's email to the session, and reading that email is what
lets a script complete the login hands-free.

## Decision

- Ship the Google OAuth client (a Desktop-app `client_id` + `client_secret`) inside
  the plugin, so a fresh machine writes `~/.gmail-mcp/gcp-oauth.keys.json` itself and
  goes straight to the consent screen. A Desktop client is a public client — Google
  marks the secret optional for this type — and the flow's real protection is PKCE
  plus user consent.
- The mailbox-OTP read is the identity mechanism, not an implementation detail: the
  uploader's email is established by Cloudflare Access mailing the code to their
  address and the script reading that mailbox. It must not be replaced by anything
  that authenticates the machine rather than the person.
- Reject a shared Cloudflare Access service token: it authenticates the plugin, so
  uploads lose their author. Reject per-user "bring your own client": a
  Google-console trip per user.
- `--copy-from` is retained only as "same human, second device": a token is bound to
  the mailbox that consented, so it can never onboard a different person.

## Consequences

- The client is public knowledge, so the project's quota and its unverified-app
  100-new-user cap cover everyone who installs; abuse is mitigated by rotating the
  client. The refresh token stays off the repo — it is the real secret.
- While the Google project is in *Testing* status, refresh tokens expire in 7 days
  and only listed test users can consent; flipping to *production-unverified* removes
  both without touching the invite-only Access gate.

## Alternatives considered

- A shared Cloudflare Access service token — rejected: it authenticates the plugin,
  not the person, so uploads lose their author (and it is a plaintext key to the whole
  app).
- Per-user "bring your own client" (each user creates a GCP project + Gmail API +
  desktop client) — rejected: a Google-console trip per user, the exact burden this
  plugin exists to remove.
- `--copy-from` as the general onboarding path — rejected: a token is bound to the
  mailbox that consented, so it can only move "your grant" to "your other device",
  never onboard a different human.
- A backend-proxied confidential client (device flow) — rejected: Google's device flow
  is for TVs/consoles without a browser, not desktop CLIs, and it hides only the
  secret, never the `client_id`, which is public in any flow.

## Open questions

- Whether the mailbox read stays on the Gmail MCP (which must be restarted after
  first consent) or moves to our own per-call reader.
- Whether to pursue Google verification (brand + restricted-scope + annual CASA), or
  adopt an app-issued upload token that removes Gmail from the plugin entirely.
