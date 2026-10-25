# Parked: Google OAuth + plugin first-run

Parked mid-discussion. Nothing here is decided beyond step 0.

## Where things stand

- **0.3.2 (uncommitted, working tree only)** — the plugin now ships its own Google
  OAuth client in `tools/skills/quiz-upload/scripts/gmail_auth.py`, so a fresh machine
  writes `~/.gmail-mcp/gcp-oauth.keys.json` itself and goes straight to the consent
  screen. 19 offline tests pass; all three manifests bumped.
- Identity comes from Cloudflare Access's one-time PIN, read out of the uploader's own
  mailbox. That flow is the identity mechanism, not an implementation detail: do not
  replace it with a shared secret.

## Steps

- [ ] **Commit + push 0.3.2** (`tools/`), then verify the update path against an
      actually-installed copy rather than telling anyone to reinstall blind.
- [ ] **Option 1 — flip the Google Cloud project to "In production", unverified.**
      No code. Kills two things at once: the 7-day refresh-token expiry that only
      applies to *Testing* status, and the chore of adding every admin to the
      test-user list in the console before they can consent.
- [ ] **Option 1 risk accepted:** cap of **100 new users** until verified
      ([Unverified apps](https://support.google.com/cloud/answer/7454865));
      the 7-day rule is in
      [OAuth 2.0 overview](https://developers.google.com/identity/protocols/oauth2).
- [ ] **Brand verification — worth doing, cheap, ~2-3 business days.** Blocked on a
      privacy policy: none exists on the site today (homepage is public and 200, no
      `/privacy` route, zero "privacy" strings in the repo).
- [ ] **Restricted-scope verification — deliberately NOT submitted yet.** Weak
      justification ("we read Gmail to get our own site's login code"), needs an
      unlisted demo video, and triggers an **annual paid CASA assessment**. Option 4
      below makes it unnecessary.
- [ ] **Option 4 — the endgame: remove Gmail from the plugin.** Upload authenticates
      with a token the app issues to a signed-in account. Removes the client, the
      consent screen, the 100-user cap, the 7-day expiry, the Gmail MCP, the Playwright
      bootstrap and the restart-after-consent wart — while keeping per-human identity,
      because the token belongs to an account. Costs: a `tokens` table, a mint/revoke
      screen, one Cloudflare Access routing decision, and a `TokenIdentity` alongside
      `CloudflareAccessIdentity` (the `IdentityProvider` port already anticipates it).
- [ ] **Do not delete the OTP flow under any option.** It is how a human's email is
      proven; options 3/4 change what the *plugin* authenticates with, not who the
      uploader is.

## Decided

- Ship the client rather than ask each user for their own — same as `gh` and rclone do;
  a desktop client is a public client by Google's own wording. Consequence accepted:
  the project's quota and its 100-new-user cap cover everyone who installs.
- No shared Cloudflare Access service token: it authenticates the plugin, not the
  person, so it cannot attribute a quiz to an uploader.
