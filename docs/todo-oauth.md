# Parked: Google OAuth + plugin first-run

Parked mid-discussion. Only "Decided" is settled; the rest is open.

## Where things stand

- **0.3.2 is committed and pushed** (`a139c4c`; ADRs `4809d40`, dynamic version badge
  `0c3c1f8`). The plugin ships its own Google OAuth client in
  `tools/skills/quiz-upload/scripts/gmail_auth.py`, so a fresh machine writes
  `~/.gmail-mcp/gcp-oauth.keys.json` itself and goes straight to the consent screen.
  19 offline tests pass; all three manifests bumped.
- Identity comes from Cloudflare Access's one-time PIN, read out of the uploader's own
  mailbox. That flow is the identity mechanism, not an implementation detail: do not
  replace it with a shared secret.

## Steps

- [x] **Commit + push 0.3.2** — done (`a139c4c`). Still to do: verify the update path
      against an actually-installed copy rather than telling anyone to reinstall blind.
- [ ] **Option 1 — flip the Google Cloud project to "In production", unverified.**
      No code. Kills the 7-day refresh-token expiry (Testing-only) and the per-admin
      test-user-list chore in one toggle.
- [ ] **Option 1 risk accepted:** cap of **100 new users** until verified
      ([Unverified apps](https://support.google.com/cloud/answer/7454865));
      the 7-day rule is in
      [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2).
- [ ] **Brand verification — cheap, ~2-3 business days.** Blocked on a privacy policy:
      none exists on the site today (homepage is public and 200, no `/privacy` route).
- [ ] **Restricted-scope verification — deliberately NOT submitted yet.** Weak
      justification, needs an unlisted demo video, and triggers an **annual paid CASA
      assessment**. Option 4 makes it unnecessary.
- [ ] **Option 2 — our own mail reader, drop the Gmail MCP (keep Gmail).** The MCP is
      the source of the restart-after-consent wart: it reads `credentials.json` once
      at process boot (verified against its `dist/index.js`), so a token created
      mid-session is invisible until the client restarts. Replace it with a
      `gmail_read.py` (urllib) that reads the token fresh on **every call** — no
      long-lived process, so no restart. Contract: `--wait N` polls for the code email;
      exit `0` = code found, `3` = not arrived yet, non-zero = real fault. We take on
      token refresh, MIME decoding (multipart/alternative, base64url, Cloudflare's
      HTML-only body) and quota errors; we shed `npx`/`node`, the MCP, and the restart
      step. Full removal also means `gmail_auth.py` runs the loopback consent + PKCE
      token exchange itself instead of shelling out to `npx … auth`.
- [ ] **Option 4 — the endgame: remove Gmail from the plugin.** Upload authenticates
      with a token the app issues to a signed-in account. Removes the client, the
      consent screen, the 100-user cap, the 7-day expiry, the reader, the Playwright
      bootstrap and the restart wart — while keeping per-human identity, because the
      token belongs to an account. Costs: a `tokens` table, a mint/revoke screen, one
      Cloudflare Access routing decision, and a `TokenIdentity` alongside
      `CloudflareAccessIdentity` (the `IdentityProvider` port already anticipates it).
- [ ] **Do not delete the OTP flow under any option.** It is how a human's email is
      proven; options 2/4 change what the *plugin* authenticates with, not who the
      uploader is.

## Decided

- Ship the client rather than ask each user for their own — same as `gh` and rclone do;
  a desktop client is a public client by Google's own wording. Consequence accepted:
  the project's quota and its 100-new-user cap cover everyone who installs.
- No shared Cloudflare Access service token: it authenticates the plugin, not the
  person, so it cannot attribute a quiz to an uploader.
