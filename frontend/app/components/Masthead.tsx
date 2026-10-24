import Link from 'next/link';
import type { Me } from '../../lib/types';

/** The site this app lives under — the first crumb of the breadcrumb. */
const SITE = 'https://akshayprabhakant.com';

/**
 * The page head: site name, who is signed in, and the way out.
 *
 * This is the only navigation every page shares, so the two ways home live here rather
 * than being repeated per page: the wordmark goes to the quiz home (a logo that navigates
 * home is the one convention every user already has), and the first crumb to the site
 * above it. Without this, /play and /admin/edit had no route to the quiz index at all.
 *
 * `me` is null while it loads. The display name is shown once there is one; until then the
 * email stands in for it. History is for everyone; Admin only for admins.
 */
export default function Masthead({ me, onSignOut }: { me: Me | null; onSignOut: () => void }) {
  return (
    <header className="masthead">
      <div>
        <Link className="name" href="/">The Quiz Room</Link>
        <nav className="mc crumb" aria-label="Breadcrumb" style={{ marginTop: 'var(--s2)' }}>
          <a href={SITE}>akshayprabhakant.com</a>
          <span className="sep" aria-hidden="true">/</span>
          <span aria-current="page">quiz</span>
        </nav>
      </div>
      <div className="who">
        {me &&
          (me.display_name ? (
            <span className="uname">{me.display_name}</span>
          ) : (
            <span className="mc">{me.email}</span>
          ))}
        <Link className="linkbtn" href="/history">History</Link>
        {me?.role === 'admin' && (
          <Link className="linkbtn" href="/admin">Admin</Link>
        )}
        <button className="linkbtn" onClick={onSignOut}>Sign out</button>
      </div>
    </header>
  );
}
