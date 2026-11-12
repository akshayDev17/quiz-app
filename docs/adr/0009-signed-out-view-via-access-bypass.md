# 9. The signed-out View is a fixed Access Bypass list; the Worker still owns refusal

Status: Accepted
Date: 2026-11-12

## Context

Signed-out visitors should see the published quizzes: each card offers a
disabled "Sign up · coming soon" and a "View" that shows the quiz in the results
layout with every score removed and the correct options marked. Signed-in
solvers see the app exactly as before.

Until now one Access application (ADR 0003) covered `akshayprabhakant.com/quiz`
and `/quiz/*` with an Allow policy, and both deploy jobs refused to deploy if
the most specific application covering `/quiz` had a Bypass policy. A page can
be reached before sign-in only through an Access Bypass. Cloudflare evaluates
Bypass before Allow, and the more specific destination wins.

## Decision

- **A second Access application, `Quiz Room (public)`, with one Bypass policy
  (Include → Everyone), holds exactly these destinations and no others:**

  | Destination | What it serves |
  |---|---|
  | `akshayprabhakant.com/quiz` | the quiz list page |
  | `akshayprabhakant.com/quiz/index.txt` | the list page's Next.js data, for client-side moves |
  | `akshayprabhakant.com/quiz/view` | the View page |
  | `akshayprabhakant.com/quiz/view.txt` | the View page's data |
  | `akshayprabhakant.com/quiz/_next/*` | JS, CSS and fonts (code, no data) |
  | `akshayprabhakant.com/quiz/api/public/*` | the read-only public API (published sets, no solver data) |

  The bare `/quiz` moves off the Invited Solvers app onto this one, and
  `/quiz/*` stays on Invited Solvers. Every other path stays signed-in only,
  including `/quiz/set`, `/quiz/play`, `/quiz/results`, `/quiz/history`,
  `/quiz/admin`, `/quiz/signin` and every other `/quiz/api/*` route. Each
  public destination is more specific than `/quiz/*`, so it takes precedence.
  Access ignores query strings, so the list holds page paths, not page URLs.
- **The Worker still owns refusal.** A bypassed request carries no
  `ctx.access`, so the backend resolves no identity
  (`CloudflareAccessIdentity`, `backend/quiz_app/auth.py`). The router answers
  `401` to every route when the identity is `None`
  (`backend/quiz_app/api.py`), and only the `GET /quiz/api/public/*` routes are
  matched before that check. The Worker still never trusts the
  `Cf-Access-Jwt-Assertion` or `Cf-Access-Authenticated-User-Email` headers, and
  no JWT validation is added. Access decides who may reach a path; the Worker
  decides what an unidentified request may see, and that is only public data.
- **The deploy guard enforces the list.** Both deploy jobs run
  `.github/scripts/access_check.py`, which refuses to deploy unless:
  1. each signed-in-only probe path (`/quiz/set`, `/quiz/play`, `/quiz/results`,
     `/quiz/history`, `/quiz/admin`, `/quiz/signin`, `/quiz/api/me`,
     `/quiz/api/topics`, `/quiz/api/attempts`, `/quiz/api/admin/sets`) resolves
     to an application with an Allow policy and no Bypass policy;
  2. each public path resolves to an application with an Allow policy (before
     the change) or a Bypass policy (after it);
  3. any application with a Bypass policy whose destinations reach `/quiz` or
     anything below it holds only the six destinations above. That includes a
     Bypass over the whole host, or a glob such as `quiz/view*`.

  `.github/scripts/test_access_check.py` runs these rules in the test job
  against fixtures: today's config and the planned one pass, and every widening
  is refused.

## Consequences

- The guard passes both before and after the Access change, so the change can
  be applied after the code is live without a deploy freeze.
- Widening the Bypass by mistake is caught twice. The deploy refuses it, and
  even a live mistake exposes nothing new from the API, because every
  non-public route still answers `401` without identity.
- A missing public entry fails closed: the visitor gets the Access login
  instead of the page.
- Adding a public page means editing three places: the Access app, the
  `PUBLIC_DESTINATIONS` list in `access_check.py`, and this ADR. The guard
  refuses the Access edit until the list in the code matches it.
- The public API cannot tell who is asking, so it serves the same anonymous
  payload to signed-in and signed-out callers alike.

## Alternatives considered

- **Bypass `/quiz/*` and let the Worker decide everything.** Rejected: the
  Worker would then see no identity for signed-in solvers either. It would need
  to validate the Access JWT itself, which ADR 0003 and `auth.py`'s no-header
  rule avoid.
- **Keep the old single-path check and drop the Bypass rule.** Rejected: it
  would let any Bypass under `/quiz` deploy, so nothing would keep it to the
  public pages.
- **Put the public pages outside `/quiz`.** Rejected: everything the quiz app
  serves stays under `/quiz` and `/quiz/*`.
