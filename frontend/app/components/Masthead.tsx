import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { SIGN_IN_HREF } from '../../lib/api';
import type { Me } from '../../lib/types';

/** One of this app's own crumbs after "Quiz Room" in the site path; the last is the current page. */
export type Crumb = { label: string; href?: string };

/**
 * Who is reading, as far as the page knows. Protected pages are always `signed-in` (Access let
 * the reader in). Pages anyone may open start `pending` until `/me` answers, so a signed-out
 * visitor never sees History and Sign out and a signed-in reader never sees Sign in.
 */
export type Session = 'signed-in' | 'signed-out' | 'pending';

/** next.config.mjs `basePath`: where this app's pages are served on the site. */
const BASE_PATH = '/quiz';

/**
 * site-shell's site row ("Home  AI Digest  Quiz Room  Graph Notes  Election Atlas", its
 * <style> and the row's <nav>, without the page's trail line), as first composed into a
 * page this tab loaded: undefined until the start page is read, null while no page has
 * come back composed. site-shell fills the slot only in the HTML it serves, but most moves
 * around the quiz are client-side navigations, which render a fresh Masthead. The row is
 * the same on every quiz page, so those reuse it as composed and rebuild only the trail
 * line under it (`sitePathFor`), rather than waiting for a fetch.
 */
let composedRow: string | null | undefined;
/** Routes whose page was fetched while no row was composed yet and came back without one. */
const fetched = new Set<string>();
/**
 * Where the row was scrolled when the last Masthead left (a portrait phone scrolls the row
 * sideways), so the next page's row opens exactly there instead of jumping back to the start.
 */
let rowScroll: { left: number; more?: string } | undefined;

/**
 * The row site-shell put in `doc`'s site path slot, or null where it did not fill the slot:
 * its markup carries `<style data-site-shell>` and marks the quiz as the current app.
 * Returned without the trail line and without site.js's scroll-edge marker.
 */
function readComposedRow(doc: ParentNode): string | null {
  const slot = doc.querySelector('site-slot[name="site-path"]');
  const style = slot?.querySelector(':scope > style[data-site-shell]');
  const nav = slot?.querySelector(':scope > nav.sp');
  if (!style || !nav?.querySelector('.sp-apps .sp-app[aria-current]')) return null;
  const box = document.createElement('template');
  box.content.append(style.cloneNode(true), nav.cloneNode(true));
  box.content.querySelector('.sp-apps')!.removeAttribute('data-more');
  return box.innerHTML;
}

/**
 * The page's trail, by site-shell's rule (site-themes shell/nav.ts `trailOf`): the app's
 * crumbs led by the app itself (a link to its root) unless the first crumb already links
 * there; none at the app's root, nor when that leaves a single crumb.
 */
function trailOf(app: Required<Crumb>, tail: Crumb[]): Crumb[] {
  if (tail.length === 0) return [];
  const trail = tail[0].href === app.href ? tail : [app, ...tail];
  return trail.length < 2 ? [] : trail;
}

/**
 * The slot's content for a page whose crumbs after "Quiz Room" are `tail`, in site-shell's
 * markup: `row` as composed, with the quiz marked aria-current="page" at the quiz home and
 * "true" below it, then the trail on its own line, links but for the current page.
 */
function sitePathFor(row: string, tail: Crumb[]): string {
  const box = document.createElement('template');
  box.innerHTML = row;
  const app = box.content.querySelector('.sp-apps .sp-app[aria-current]')!;
  app.setAttribute('aria-current', tail.length === 0 ? 'page' : 'true');
  const trail = trailOf({ label: app.querySelector('.sp-label')?.textContent ?? '', href: app.getAttribute('href') ?? '' }, tail);
  if (trail.length === 0) return box.innerHTML;

  const nav = document.createElement('nav');
  nav.className = 'sp-trail';
  nav.setAttribute('aria-label', 'Breadcrumb');
  const list = document.createElement('ol');
  trail.forEach((c, i) => {
    const last = i === trail.length - 1;
    const item = document.createElement(!last && c.href ? 'a' : 'span');
    if (last) item.setAttribute('aria-current', 'page');
    else if (c.href) item.setAttribute('href', c.href);
    item.textContent = c.label;
    const li = document.createElement('li');
    li.append(item);
    list.append(li);
  });
  nav.append(list);
  box.content.append(nav);
  return box.innerHTML;
}

/**
 * The markup to render first. On the first client render the document is still the one
 * the server sent (hydrating, or about to be replaced by a Suspense boundary that renders
 * on the client), so its composed slot is read before React replaces it and rendered as is.
 * Where site-shell did not fill the slot (no binding, site-shell down, `next dev`), it stays empty.
 */
function initialSitePath(tail: Crumb[]): string {
  if (typeof document === 'undefined') return '';
  if (composedRow === undefined) {
    composedRow = readComposedRow(document);
    return composedRow === null ? '' : document.querySelector('site-slot[name="site-path"]')!.innerHTML;
  }
  return composedRow === null ? '' : sitePathFor(composedRow, tail);
}

/**
 * Fetches the route's page (composed at the edge) and reads its row: null when the page
 * came back without one; rejects when no page came back (network, status, sign-in).
 */
async function fetchComposedRow(pathname: string): Promise<string | null> {
  const res = await fetch(`${BASE_PATH}${pathname}`, { credentials: 'same-origin' });
  if (!res.ok || !(res.headers.get('content-type') ?? '').startsWith('text/html')) throw new Error(`${pathname}: no page`);
  return readComposedRow(new DOMParser().parseFromString(await res.text(), 'text/html'));
}

/**
 * The page head: site name, the site path, who is signed in, and the way out.
 *
 * This is the only navigation every page shares, so the ways home live here rather than
 * being repeated per page: the wordmark goes to the quiz home (a logo that navigates home
 * is the one convention every user already has), and the site row under it goes to the
 * site's home and to every other app.
 *
 * The site path is the shared switcher, `<site-slot name="site-path">`, which site-shell
 * (akshayDev17/site-themes, shell/) fills at the edge from the site's app list: the site
 * row, and on pages below the quiz home the page's trail on its own line under it. `tail`
 * is this page's crumbs after "Quiz Room", passed as `data-tail`. React must never replace
 * what site-shell put there, so the slot renders through dangerouslySetInnerHTML with
 * suppressHydrationWarning, and client-side navigations keep the composed row (and where
 * it was scrolled) and redraw only the trail (see `composedRow`).
 *
 * `me` is null while it loads. The display name is shown once there is one; until then the
 * email stands in for it. History is for everyone signed in; Admin only for admins. Signed
 * out, a single Sign in takes their place: a full navigation to a protected page, so Access
 * shows its sign-in on the way (`SIGN_IN_HREF`). The theme picker
 * is the shared <site-theme-picker>, which site-shell's site.js defines (it stays an empty
 * element where site-shell is absent, such as `next dev`), so a choice made here carries
 * over to the other apps.
 */
export default function Masthead({
  me,
  onSignOut,
  tail,
  session = 'signed-in',
}: {
  me: Me | null;
  onSignOut: () => void;
  tail: Crumb[];
  session?: Session;
}) {
  const pathname = usePathname();
  const [sitePath, setSitePath] = useState(() => initialSitePath(tail));
  const slot = useRef<HTMLElement>(null);
  // One object per markup: React sets a custom element's innerHTML again whenever this
  // object is a new one, which would redraw the row (and lose its scroll) on every render.
  const slotHtml = useMemo(() => ({ __html: sitePath }), [sitePath]);

  // Before the first paint: open the row where the last page left it, and remember where
  // this one is when it goes.
  useLayoutEffect(() => {
    const row = slot.current?.querySelector<HTMLElement>('.sp-apps');
    if (!row) return;
    if (rowScroll) {
      row.scrollLeft = rowScroll.left;
      if (rowScroll.more) row.dataset.more = rowScroll.more;
    }
    return () => {
      rowScroll = { left: row.scrollLeft, more: row.dataset.more };
    };
  }, [sitePath]);

  useEffect(() => {
    if (composedRow || fetched.has(pathname)) return;
    let live = true;
    fetchComposedRow(pathname).then((row) => {
      fetched.add(pathname);
      if (!row) return;
      composedRow ??= row;
      if (live) setSitePath(sitePathFor(composedRow, tail));
    }, () => {});
    return () => {
      live = false;
    };
    // `tail` is fixed per page, so the route alone decides it.
  }, [pathname]);

  return (
    <header className="masthead">
      <div>
        <Link className="name" href="/">The Quiz Room</Link>
        <site-slot
          ref={slot}
          name="site-path"
          data-tail={JSON.stringify(tail)}
          style={{ marginTop: 'var(--s2)' }}
          dangerouslySetInnerHTML={slotHtml}
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
        {session === 'signed-in' && (
          <>
            <Link className="linkbtn" href="/history">History</Link>
            {me?.role === 'admin' && (
              <Link className="linkbtn" href="/admin">Admin</Link>
            )}
            <button className="linkbtn" onClick={onSignOut}>Sign out</button>
          </>
        )}
        {session === 'signed-out' && <a className="linkbtn" href={SIGN_IN_HREF}>Sign in</a>}
        <site-theme-picker hide-label="" />
      </div>
    </header>
  );
}
