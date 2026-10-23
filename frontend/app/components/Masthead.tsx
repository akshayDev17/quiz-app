import Link from 'next/link';
import type { Me } from '../../lib/types';

/**
 * The page head: site name, who is signed in, and the way out.
 *
 * `me` is null while it loads. The display name is shown once there is one; until then the
 * email stands in for it. History is for everyone; Admin only for admins.
 */
export default function Masthead({ me, onSignOut }: { me: Me | null; onSignOut: () => void }) {
  return (
    <header className="masthead">
      <div>
        <div className="name">The Quiz Room</div>
        <div className="mc" style={{ marginTop: 'var(--s2)' }}>akshayprabhakant.com / quiz</div>
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
