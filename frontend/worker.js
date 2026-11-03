/**
 * Serves the static export of the quiz app at /quiz/*.
 *
 * The export is built with basePath /quiz, so its pages and chunks are linked as
 * /quiz/..., but the files in `out/` sit at the root of the ASSETS binding. This
 * Worker strips the /quiz prefix and hands the request to ASSETS, which applies
 * Cloudflare's clean-URL handling (`/quiz/play` -> `play.html`).
 *
 * ASSETS knows nothing of the prefix, so its redirects point at prefix-less paths
 * (`/play/` -> `/play`). Left alone, the browser would follow that out of the app
 * to GitHub Pages, so a same-origin Location is re-prefixed on the way out.
 *
 * Every HTML page then passes through site-shell (the `SHELL` service binding,
 * akshayDev17/site-themes `shell/`), which adds the shared site theme to the
 * page's <head> as it streams out; the app bundles no theme code of its own.
 * `/quiz/_site/*` and `/_site/*` forward to site-shell's own files (its picker
 * script). In production the zone routes akshayprabhakant.com/_site/* to
 * site-shell directly, so this Worker sees a bare `/_site/*` only under
 * `wrangler dev`, where it stands in for that route.
 */
const PREFIX = /^\/quiz(?=\/|$)/;

export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    u.pathname = u.pathname.replace(PREFIX, '') || '/';
    if (u.pathname.startsWith('/_site/') && env.SHELL) return env.SHELL.fetch(new Request(u, req));
    const page = async () => reprefixRedirect(await env.ASSETS.fetch(new Request(u, req)), u);
    return withShell(await page(), env, page, 'quiz', '/quiz/_site/');
  },
};

function reprefixRedirect(res, origin) {
  const location = res.status >= 300 && res.status < 400 ? res.headers.get('location') : null;
  if (!location) return res;
  const target = new URL(location, origin);
  if (target.origin !== origin.origin || PREFIX.test(target.pathname)) return res;
  const headers = new Headers(res.headers);
  headers.set('location', `/quiz${target.pathname}${target.search}${target.hash}`);
  return new Response(res.body, { status: res.status, statusText: res.statusText, headers });
}

/**
 * Passes an HTML page through site-shell's compose(), failing open: with no
 * binding, or when site-shell is missing, unreachable or throws, the visitor
 * gets the page exactly as built. The page's body went to site-shell with the
 * call, so the fallback fetches the page again (a static asset, so free);
 * returning `res` there would answer 500 ("Body has already been used").
 */
async function withShell(res, env, refetch, app, assetBase) {
  const type = res.headers.get('content-type') || '';
  if (!env.SHELL || res.status !== 200 || !type.startsWith('text/html')) return res;
  try {
    return await env.SHELL.compose(res, { app, assetBase });
  } catch (err) {
    console.error('site-shell: compose failed, serving the page as built:', String(err));
    const fallback = await refetch();
    const headers = new Headers(fallback.headers);
    headers.delete('etag');
    headers.delete('last-modified');
    return new Response(fallback.body, { status: fallback.status, statusText: fallback.statusText, headers });
  }
}
