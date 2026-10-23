/**
 * Banner for an expired sign-in. The link is a plain `<a>` (not `next/link`) so following it is a
 * full navigation, which is what lets Cloudflare Access sign the reader in again.
 */
export default function SignInAgain() {
  return (
    <div className="banner">
      Your sign-in expired. <a href={window.location.href}>Sign in again</a>
    </div>
  );
}
