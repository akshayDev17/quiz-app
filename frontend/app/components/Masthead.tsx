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
 * site-shell's site path, as first composed into a page this tab loaded: undefined until the
 * start page is read, null while no page has come back composed. site-shell fills the slot
 * only in the HTML it serves, but most moves around the quiz are client-side navigations,
 * which render a fresh Masthead. The app list is the same on every page, so those reuse
 * this markup with their own crumbs (`sitePathWithTail`) rather than waiting for a fetch.
 */
let composed: string | null | undefined;
/** Routes whose page was fetched while no site path was composed yet and came back without one. */
const fetched = new Set<string>();

/**
 * The slot's content when site-shell filled it: its markup carries `data-site-shell`, and
 * the quiz is the current app both in the row and in the phone sheet.
 */
function composedSitePath(doc: ParentNode): string | null {
  const slot = doc.querySelector('site-slot[name="site-path"]');
  if (!slot?.querySelector('[data-site-shell]')) return null;
  const complete = slot.querySelector('nav.sp .sp-apps .sp-app[aria-current]') && slot.querySelector('dialog a[aria-current]');
  return complete ? slot.innerHTML : null;
}

/**
 * `html` (a composed site path) for a page whose crumbs after "Quiz Room" are `tail`, in
 * site-shell's markup: the quiz is plain text with aria-current="page" at the quiz home and
 * a link with aria-current="true" below it, and the last crumb is the current page.
 */
function sitePathWithTail(html: string, tail: Crumb[]): string {
  const box = document.createElement('template');
  box.innerHTML = html;
  const nav = box.content.querySelector('nav.sp')!;
  const app = nav.querySelector('.sp-apps .sp-app[aria-current]')!;
  const sheetApp = box.content.querySelector('dialog a[aria-current]')!;
  const atHome = tail.length === 0;

  const here = document.createElement(atHome ? 'span' : 'a');
  here.className = atHome ? 'sp-here sp-app' : 'sp-app';
  if (!atHome) here.setAttribute('href', sheetApp.getAttribute('href')!);
  here.setAttribute('aria-current', atHome ? 'page' : 'true');
  here.append(...app.childNodes);
  app.replaceWith(here);
  sheetApp.setAttribute('aria-current', atHome ? 'page' : 'true');

  nav.querySelectorAll('.sp-crumb').forEach((c) => c.remove());
  tail.forEach((c, i) => {
    const last = i === tail.length - 1;
    const sep = document.createElement('span');
    sep.className = 'sp-sep';
    sep.setAttribute('aria-hidden', 'true');
    sep.textContent = '/';
    const item = document.createElement(!last && c.href ? 'a' : 'span');
    if (last) {
      item.className = 'sp-here sp-page';
      item.setAttribute('aria-current', 'page');
    } else if (c.href) {
      item.setAttribute('href', c.href);
    } else {
      item.className = 'sp-here';
    }
    item.textContent = c.label;
    const crumb = document.createElement('span');
    crumb.className = 'sp-crumb';
    crumb.append(sep, item);
    nav.append(crumb);
  });
  return box.innerHTML;
}

/**
 * The markup to render first. On the first client render the document is still the one
 * the server sent (hydrating, or about to be replaced by a Suspense boundary that renders
 * on the client), so its composed slot is read before React replaces it and rendered as is.
 */
function initialSitePath(tail: Crumb[]): string {
  if (typeof document === 'undefined') return FALLBACK;
  if (composed === undefined) {
    composed = composedSitePath(document);
    return composed ?? FALLBACK;
  }
  return composed === null ? FALLBACK : sitePathWithTail(composed, tail);
}

/**
 * Fetches the route's page (composed at the edge) and reads its site path: null when the
 * page came back without one; rejects when no page came back (network, status, sign-in).
 */
async function fetchSitePath(pathname: string): Promise<string | null> {
  const res = await fetch(`${BASE_PATH}${pathname}`, { credentials: 'same-origin' });
  if (!res.ok || !(res.headers.get('content-type') ?? '').startsWith('text/html')) throw new Error(`${pathname}: no page`);
  return composedSitePath(new DOMParser().parseFromString(await res.text(), 'text/html'));
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
 * suppressHydrationWarning, and client-side navigations reuse the composed markup with
 * their own crumbs (see `composed`). Where site-shell is absent, the slot keeps the old breadcrumb (`FALLBACK`).
 *
 * `me` is null while it loads. The display name is shown once there is one; until then the
 * email stands in for it. History is for everyone; Admin only for admins. The theme picker
 * is the shared <site-theme-picker>, which site-shell's site.js defines (it stays an empty
 * element where site-shell is absent, such as `next dev`), so a choice made here carries
 * over to the other apps.
 */
export default function Masthead({ me, onSignOut, tail }: { me: Me | null; onSignOut: () => void; tail: Crumb[] }) {
  const pathname = usePathname();
  const [sitePath, setSitePath] = useState(() => initialSitePath(tail));

  useEffect(() => {
    if (composed || fetched.has(pathname)) return;
    let live = true;
    fetchSitePath(pathname).then((html) => {
      fetched.add(pathname);
      if (!html) return;
      composed ??= html;
      if (live) setSitePath(html);
    }, () => {});
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
