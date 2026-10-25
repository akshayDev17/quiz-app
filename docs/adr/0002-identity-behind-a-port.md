# 2. Identity resolves behind a port (`IdentityProvider`)

Status: Accepted
Date: 2026-10-24

## Context

Every `/quiz/api` route needs an authenticated identity, but the mechanism that
produces it (Cloudflare Access today) was expected to change, and must never leak
into the router or the repositories.

## Decision

Identity is a port: `IdentityProvider.identify(request) -> Identity | None`. The
router asks the port "who is this?" and never learns how the answer was produced.
Implementations:

- `CloudflareAccessIdentity` — reads the identity Cloudflare Access already
  established, via `ctx.access` (production).
- `DevIdentity` — one fixed local user, for `local_server.py`.
- `AnonymousIdentity` — always `None`; the safe default and the test double.

All implementations fail closed: any missing binding or unexpected shape resolves to
`None`, which every protected route turns into 401.

## Consequences

- Swapping the auth mechanism (a self-hosted OTP flow, or a token) means adding one
  more implementation of the ABC; nothing else in the backend changes. This is the
  seam the plugin's upload auth (ADR 8) is expected to grow into.
- `ctx.access` is undocumented for Python Workers, so the production provider was
  verified empirically after the first deploy rather than trusted from docs.
- Failure is silent-and-safe (401), so something must surface a provider that is
  always failing closed — a health check, not a happy path.

## Alternatives considered

- Verifying the `Cf-Access-Jwt-Assertion` JWT against the team's JWKS ourselves —
  considered and deferred, not built: Access already resolves the identity, and this
  stays as the documented fallback only if `ctx.access` proves absent in Python
  Workers.
- Reading identity directly inside the router (no port) — rejected: the mechanism was
  genuinely undecided and must stay swappable without touching routes or repositories.
