# 1. Topology — Worker + D1 + static-assets Worker under `/quiz`

Status: Accepted
Date: 2026-10-24

## Context

The quiz app must live on `akshayprabhakant.com` without disturbing three existing
tenants: the archive's backend (`/api/*`), the archive's frontend
(`/chat-archives/*`, `/_next/*`), and GitHub Pages (everything else).

## Decision

- The API is a Python Worker + D1, routed at `akshayprabhakant.com/quiz/api/*`.
- The frontend is a Next.js static export served by a static-assets Worker, routed at
  `/quiz` and `/quiz/*`.
- The API lives under `/quiz/api/*`, not `/api/quiz/*`, so the archive's Worker route
  is untouched and one Access application covers the whole quiz app.
- Next.js `basePath` is `/quiz`: the archive already claims `/_next/*`, so without it
  the quiz's chunks would be served by the archive's Worker and 404.
- Same hostname throughout, so a single `CF_Authorization` cookie covers pages and
  API in one sign-in.
- `workers_dev: false` on both Workers, reached via Routes, never a Custom Domain.
- D1 database `quiz-app`, created `--location apac`.

## Consequences

- Most-specific route wins, so `/quiz/api/*` beats `/quiz/*`.
- Routing is declared entirely in `wrangler.jsonc`; nothing is set in the dashboard.
- A Custom Domain is deliberately not used: it would swallow every path on the host.

## Alternatives considered

- API under `/api/quiz/*` instead of `/quiz/api/*` — rejected: it would have to
  coexist with the archive's `/api/*` Worker route, and nesting under `/quiz` lets one
  Access application cover the whole quiz app.
- A Custom Domain instead of Routes — rejected: a Custom Domain would swallow every
  path on the host, displacing the archive and GitHub Pages.
- Serving the frontend without a `basePath` — rejected: the archive already claims
  `/_next/*`, so the quiz's chunks would be served by the archive's Worker and 404.
