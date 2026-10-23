/**
 * Serves the static export of the quiz app at /quiz/*.
 *
 * The export is built with basePath /quiz, so its pages and chunks are linked as
 * /quiz/..., but the files in `out/` sit at the root of the ASSETS binding. This
 * Worker strips the /quiz prefix and hands the request to ASSETS, which applies
 * Cloudflare's clean-URL handling (`/quiz/play` -> `play.html`).
 */
export default {
  fetch(req, env) {
    const u = new URL(req.url);
    u.pathname = u.pathname.replace(/^\/quiz(?=\/|$)/, '') || '/';
    return env.ASSETS.fetch(new Request(u, req));
  },
};
