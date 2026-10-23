/** sessionStorage key holding when we last reloaded to re-authenticate (epoch ms). */
const REAUTH_KEY = 'quiz:reauth';
/** A second expiry within this window means the reload did not sign the reader in. */
const REAUTH_WINDOW_MS = 30_000;

/**
 * Reacts to an expired Access session.
 *
 * Access re-authenticates on a top-level navigation, so a reload is normally the way back in.
 * If we already reloaded for this less than 30 s ago, reloading again would loop, so this does
 * nothing: the caller is expected to show the "Your sign-in expired. Sign in again" banner
 * (`SignInAgain`) whenever it handles an expiry, and that banner is all the reader sees.
 */
export function handleSessionExpired(): void {
  const now = Date.now();
  try {
    const last = Number(window.sessionStorage.getItem(REAUTH_KEY));
    if (last && now - last < REAUTH_WINDOW_MS) return;
    window.sessionStorage.setItem(REAUTH_KEY, String(now));
  } catch {
    // Storage blocked: we cannot tell a loop from a first expiry, so leave it to the banner.
    return;
  }
  window.location.reload();
}

/** Forget the reload marker; call after a request proves the session is good. */
export function clearReauthFlag(): void {
  try {
    window.sessionStorage.removeItem(REAUTH_KEY);
  } catch {
    // Nothing to clear if storage is unavailable.
  }
}
