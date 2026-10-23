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
 */
const PREFIX = /^\/quiz(?=\/|$)/;

export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    u.pathname = u.pathname.replace(PREFIX, '') || '/';
    const res = await env.ASSETS.fetch(new Request(u, req));
    return reprefixRedirect(res, u);
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
