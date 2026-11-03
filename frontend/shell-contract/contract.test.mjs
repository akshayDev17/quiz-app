// The frontend Worker against the real site-shell, in local workerd: each test
// is one `wrangler dev` session over the static export (harness.mjs). It needs
// the export (`npm run build`, which writes out/) and a checkout of
// akshayDev17/site-themes:
//
//   SITE_THEMES_DIR=/path/to/site-themes npm run test:shell
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { before, test } from 'node:test';
import { pathToFileURL } from 'node:url';
import { unstable_readConfig } from 'wrangler';
import { APP, out, PAGES, SHELL, TAILS, THROWING_SHELL, UNBOUND, session, siteThemes } from './harness.mjs';

const META = '<meta charSet="utf-8"/>';

let build;
// site-themes' app list (src/apps.ts, built to dist/apps.js): what the site path lists.
let apps;
// Where composed pages load site-shell's files from: site-shell's own ASSET_BASE
// (the routed akshayprabhakant.com/_site/) wins over the assetBase this app
// passes; a site-shell without one uses the app's '/quiz/_site/'.
let assetBase;
before(async () => {
  ({ APPS: apps } = await import(pathToFileURL(join(siteThemes, 'dist/apps.js')).href));
  build = JSON.parse(readFileSync(join(siteThemes, 'shell/generated/build.json'), 'utf8'));
  assetBase = unstable_readConfig({ config: SHELL }).vars?.ASSET_BASE ?? '/quiz/_site/';
});

/** Worker console output reaches wrangler's stdout a moment after the response. */
async function logMatching(s, re) {
  for (let i = 0; i < 40 && !re.test(s.log()); i++) await new Promise((r) => setTimeout(r, 100));
  return s.log();
}

const asBuilt = (file) => readFileSync(join(out, file), 'utf8');

// The Masthead's <site-slot name="site-path">: site-shell replaces only its content.
const SLOT = /(<site-slot name="site-path"[^>]*>)([\s\S]*?)(<\/site-slot>)/g;
function slotContent(html) {
  const slots = [...html.matchAll(SLOT)];
  assert.equal(slots.length, 1, 'exactly one site path slot');
  return slots[0][2];
}
const withSlotContent = (html, content) => html.replace(SLOT, (_, open, _old, close) => open + content + close);

/**
 * The site path site-shell put in the slot: the row of every listed app, with the quiz
 * marked current and no other link to the site, then this page's trail on its own line
 * ("Quiz Room › History"), or no trail at the quiz home.
 */
function assertSitePath(html, tail, where) {
  const row = html.match(/<nav class="sp" aria-label="Site"><ul class="sp-apps">([\s\S]*?)<\/ul><\/nav>/);
  assert.ok(row, `${where}: the site row`);
  const quiz = apps.find((a) => a.id === 'quiz');
  const gated = (a) => (a.gated ? '<span class="site-vh"> (sign-in required)</span>' : '');
  const items = apps.filter((a) => a.listed).map((a) => a === quiz
    ? `<li><a class="sp-app" href="${a.path}" aria-current="${tail.length === 0 ? 'page' : 'true'}"><span class="sp-label">${a.label}</span>${gated(a)}</a></li>`
    : `<li><a href="${a.path}">${a.label}${gated(a)}</a></li>`);
  assert.equal(row[1], items.join(''), `${where}: every listed app, ${quiz.label} the current one`);

  const trail = html.slice(row.index + row[0].length);
  if (tail.length === 0) return assert.equal(trail, '', `${where}: no trail at the quiz home`);
  const crumbs = [{ label: quiz.label, href: quiz.path }, ...tail].map((c, i, all) => i === all.length - 1
    ? `<li><span aria-current="page">${c.label}</span></li>`
    : `<li><a href="${c.href}">${c.label}</a></li>`);
  assert.equal(trail, `<nav class="sp-trail" aria-label="Breadcrumb"><ol>${crumbs.join('')}</ol></nav>`, `${where}: the trail`);
}
/** The exported page plus site-shell's one insertion, right after its leading <meta charset>. */
function composed(file) {
  const page = asBuilt(file);
  assert.equal(page.split(META).length, 2, `${file} has exactly one ${META}`);
  const scripts = build.scripts.map((f) => `<script defer src="${assetBase}${build.id}/${f}"></script>`).join('');
  return page.replace(META, META + build.inline + scripts);
}

test('bound to site-shell: every page gains the theme head block and the site path, and nothing else', async (t) => {
  const s = await session(t, [APP, SHELL]);
  for (const [path, file] of Object.entries(PAGES)) {
    const res = await fetch(`${s.base}${path}`);
    const body = await res.text();
    assert.equal(res.status, 200, path);
    assert.equal(res.headers.get('x-site-shell'), `${build.id}; app=quiz`, path);
    assert.equal(res.headers.get('etag'), null, `${path}: composed HTML carries no validator`);
    const sitePath = slotContent(body);
    assert.equal(withSlotContent(body, slotContent(asBuilt(file))), composed(file),
      `${path}: the exported page plus the head block, with only the slot's content replaced`);
    assert.ok(body.indexOf(META) < 1024, `${path}: <meta charset> stays inside the first 1024 bytes`);
    const head = body.slice(0, body.indexOf('</head>'));
    assert.equal(head.match(/data-site-shell/g).length, 2, `${path}: one boot <script> and one tokens <style>`);
    assert.ok(body.includes(`data-tail="${JSON.stringify(TAILS[file]).replaceAll('"', '&quot;')}"`),
      `${path}: the slot carries this page's crumbs`);
    assertSitePath(sitePath, TAILS[file], path);
  }

  // A redirect is re-prefixed and never composed.
  const redirect = await fetch(`${s.base}/quiz/play/`, { redirect: 'manual' });
  assert.ok(redirect.status >= 300 && redirect.status < 400, `/quiz/play/ redirects (got ${redirect.status})`);
  assert.equal(redirect.headers.get('location'), '/quiz/play');
  assert.equal(redirect.headers.get('x-site-shell'), null);

  // Non-HTML passes through untouched, validators and 304 included.
  const css = asBuilt('index.html').match(/href="(\/quiz\/_next\/static\/css\/[^"]+\.css)"/g)
    .map((m) => m.slice(6, -1));
  const sheets = await Promise.all(css.map(async (href) => {
    const r = await fetch(`${s.base}${href}`);
    return { href, r, text: await r.text() };
  }));
  for (const { href, r } of sheets) {
    assert.equal(r.status, 200, href);
    assert.equal(r.headers.get('x-site-shell'), null, href);
  }
  const { href, r: sheet } = sheets[0];
  const etag = sheet.headers.get('etag');
  assert.ok(etag, 'the stylesheet keeps its ETag');
  assert.equal((await fetch(`${s.base}${href}`, { headers: { 'if-none-match': etag } })).status, 304);
  assert.ok(sheets.some(({ text }) => /:where\(:root\)\{color-scheme:light;--surface:#EEF1F8/.test(text)),
    'the Classic Light fallback ships in the CSS');

  // site-shell's own files through this app's route: immutable; a missing build is never cached.
  const js = await fetch(`${s.base}/quiz/_site/${build.id}/site.js`);
  assert.equal(js.status, 200);
  assert.equal(js.headers.get('cache-control'), 'public, max-age=31536000, immutable');
  assert.match(await js.text(), /site-theme-picker/);
  const missing = await fetch(`${s.base}/quiz/_site/000000000000/site.js`);
  assert.equal(missing.status, 404);
  assert.equal(missing.headers.get('cache-control'), 'no-store');
});

test('unbound: with no SHELL binding every page is served exactly as built', async (t) => {
  const s = await session(t, [UNBOUND]);
  for (const [path, file] of Object.entries(PAGES)) {
    const res = await fetch(`${s.base}${path}`);
    assert.equal(res.status, 200, path);
    assert.equal(res.headers.get('x-site-shell'), null, path);
    assert.equal(await res.text(), asBuilt(file), path);
  }
});

test('bound, site-shell not running: compose rejects and the page is fetched again as built', async (t) => {
  const s = await session(t, [APP]);
  for (const [path, file] of Object.entries(PAGES)) {
    const res = await fetch(`${s.base}${path}`);
    assert.equal(res.status, 200, path);
    assert.equal(res.headers.get('etag'), null, `${path}: the fallback carries no validator`);
    assert.equal(res.headers.get('last-modified'), null, path);
    assert.equal(await res.text(), asBuilt(file), path);
  }
  assert.match(await logMatching(s, /site-shell: compose failed/), /site-shell: compose failed/);
});

test('site-shell throws: fail open to the page as built', async (t) => {
  const s = await session(t, [APP, THROWING_SHELL]);
  for (const [path, file] of Object.entries(PAGES)) {
    const res = await fetch(`${s.base}${path}`);
    assert.equal(res.status, 200, path);
    assert.equal(res.headers.get('x-site-shell'), null, path);
    assert.equal(res.headers.get('etag'), null, `${path}: the fallback carries no validator`);
    assert.equal(res.headers.get('last-modified'), null, path);
    assert.equal(await res.text(), asBuilt(file), path);
  }
  assert.match(await logMatching(s, /fault: compose threw/), /fault: compose threw/);
});
