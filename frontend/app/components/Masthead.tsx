import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import type { Me } from '../../lib/types';

/** One of this app's own crumbs after "Quiz Room" in the site path; the last is the current page. */
export type Crumb = { label: string; href?: string };

/** next.config.mjs `basePath`: where this app's pages are served on the site. */
const BASE_PATH = '/quiz';

/**
 * What the site path slot shows when site-shell has not filled it (no binding, site-shell
 * down, `next dev`): the breadcrumb this app had before the shared switcher.
 */
const FALLBACK =
  '<nav class="mc crumb" aria-label="Breadcrumb">' +
  '<a href="https://akshayprabhakant.com">akshayprabhakant.com</a>' +
  '<span class="sep" aria-hidden="true">/</span><span aria-current="page">quiz</span></nav>';

/**
 * The composed site path per route (`usePathname()`), or null where the page came back
 * without one. site-shell fills the slot only in the HTML it serves, but most moves around
 * the quiz are client-side navigations, which render a fresh Masthead. Each route's
 * composed markup is read once, from the page the visit started on or by fetching that
 * route's page, and reused from here.
 */
const sitePaths = new Map<string, string | null>();
let startPageRead = false;

/** The slot's content when site-shell filled it (its markup carries `data-site-shell`). */
function composedSitePath(doc: ParentNode): string | null {
  const slot = doc.querySelector('site-slot[name="site-path"]');
  return slot?.querySelector('[data-site-shell]') ? slot.innerHTML : null;
}

/**
 * The markup to render first. On the first client render the document is still the one
 * the server sent (hydrating, or about to be replaced by a Suspense boundary that renders
 * on the client), so its composed slot is read before React replaces it.
 */
function initialSitePath(pathname: string): string {
  if (typeof document === 'undefined') return FALLBACK;
  if (!startPageRead) {
    startPageRead = true;
    sitePaths.set(pathname, composedSitePath(document));
  }
  return sitePaths.get(pathname) ?? FALLBACK;
}

/** Fetches the route's page (composed at the edge) and reads its site path; null on any failure. */
async function fetchSitePath(pathname: string): Promise<string | null> {
  try {
    const res = await fetch(`${BASE_PATH}${pathname}`, { credentials: 'same-origin' });
    if (!res.ok || !(res.headers.get('content-type') ?? '').startsWith('text/html')) return null;
    return composedSitePath(new DOMParser().parseFromString(await res.text(), 'text/html'));
  } catch {
    return null;
  }
}

/**
 * The page head: site name, the site path, who is signed in, and the way out.
 *
 * This is the only navigation every page shares, so the ways home live here rather than
 * being repeated per page: the wordmark goes to the quiz home (a logo that navigates home
 * is the one convention every user already has), and the site path under it goes to the
 * site and to every other app.
 *
 * The site path is the shared switcher, `<site-slot name="site-path">`, which site-shell
 * (akshayDev17/site-themes, shell/) fills at the edge from the site's app list; `tail` is
 * this page's crumbs after "Quiz Room", passed as `data-tail`. React must never replace
 * what site-shell put there, so the slot renders through dangerouslySetInnerHTML with
 * suppressHydrationWarning, and client-side navigations reuse the composed markup (see
 * `sitePaths`). Where site-shell is absent, the slot keeps the old breadcrumb (`FALLBACK`).
 *
 * `me` is null while it loads. The display name is shown once there is one; until then the
 * email stands in for it. History is for everyone; Admin only for admins. The theme picker
 * is the shared <site-theme-picker>, which site-shell's site.js defines (it stays an empty
 * element where site-shell is absent, such as `next dev`), so a choice made here carries
 * over to the other apps.
 */
export default function Masthead({ me, onSignOut, tail }: { me: Me | null; onSignOut: () => void; tail: Crumb[] }) {
  const pathname = usePathname();
  const [sitePath, setSitePath] = useState(() => initialSitePath(pathname));

  useEffect(() => {
    if (sitePaths.has(pathname)) return;
    let live = true;
    fetchSitePath(pathname).then((html) => {
      sitePaths.set(pathname, html);
      if (live && html) setSitePath(html);
    });
    return () => {
      live = false;
    };
  }, [pathname]);

  return (
    <header className="masthead">
      <div>
        <Link className="name" href="/">The Quiz Room</Link>
        <site-slot
          name="site-path"
          data-tail={JSON.stringify(tail)}
          style={{ marginTop: 'var(--s2)' }}
          dangerouslySetInnerHTML={{ __html: sitePath }}
          suppressHydrationWarning
        />
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
        <site-theme-picker hide-label="" />
      </div>
    </header>
  );
}
