// The static export carries no theme of its own: site-shell owns the boot
// script, the theme tokens and the picker's definition, and adds them at the
// edge (worker.js). What the export must still carry is the picker element and
// the Classic Light fallback for when site-shell is absent.
//
//   npm run build && npm run test:export
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { before, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const out = join(dirname(fileURLToPath(import.meta.url)), 'out');
// The shared token names (site-themes' catalogue).
const TOKENS = ['surface', 'surface-2', 'card', 'text', 'text-body', 'text-muted', 'line', 'line-strong', 'card-line',
  'card-line-hover', 'accent', 'focus', 'danger', 'warn', 'ok', 'shadow-rest', 'shadow-hover', 'radius-card',
  'font-serif', 'font-mono'];

const walk = (dir) => readdirSync(dir, { withFileTypes: true })
  .flatMap((e) => (e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)]));
let files;
before(() => {
  assert.ok(existsSync(join(out, 'index.html')), 'no static export: run `npm run build` first');
  files = walk(out);
});
const pages = () => files.filter((f) => f.endsWith('.html'));
const sheets = () => files.filter((f) => f.endsWith('.css'));

/** Every rule in a minified stylesheet, as { selector, body }, at-rule blocks flattened. */
function rules(css) {
  const found = [];
  const re = /([^{}]+)\{([^{}]*)\}/g;
  for (const m of css.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(re)) found.push({ selector: m[1].trim(), body: m[2] });
  return found;
}

test('no exported page carries a theme boot script or theme tokens of its own', () => {
  assert.ok(pages().length >= 10, 'the quiz pages were exported');
  for (const file of pages()) {
    const html = readFileSync(file, 'utf8');
    const head = html.slice(0, html.indexOf('</head>'));
    assert.equal(html.includes('__siteThemeBoot'), false, `${relative(out, file)}: no bundled boot script`);
    assert.equal(head.includes('data-site-shell'), false, `${relative(out, file)}: site-shell's block is added at the edge, not built in`);
    assert.equal(/<style[^>]*>[^<]*--surface:/.test(head), false, `${relative(out, file)}: no inline theme tokens`);
  }
});

// Every page prerenders its masthead (the pages that read the query string have
// it as their Suspense fallback), so site-shell finds the site path slot in each.
const MASTHEAD_PAGES = ['index.html', 'set.html', 'play.html', 'results.html', 'history.html', 'admin.html', 'admin/edit.html',
  'view.html', 'signin.html'];

test('every page\'s masthead renders the plain <site-theme-picker hide-label> element', () => {
  for (const name of MASTHEAD_PAGES) {
    const html = readFileSync(join(out, name), 'utf8');
    assert.match(html, /<site-theme-picker hide-label=""><\/site-theme-picker>/, name);
  }
});

test('every page\'s masthead has one site path slot, empty until site-shell fills it', () => {
  for (const name of MASTHEAD_PAGES) {
    const html = readFileSync(join(out, name), 'utf8');
    const slots = [...html.matchAll(/<site-slot name="site-path" data-tail="[^"]*"[^>]*>([\s\S]*?)<\/site-slot>/g)];
    assert.equal(slots.length, 1, `${name}: one site path slot`);
    assert.equal(slots[0][1], '', `${name}: no fallback of the app's own`);
    assert.ok(html.indexOf('<site-slot') > html.indexOf('<header class="masthead">'), `${name}: the slot is in the masthead`);
  }
});

// The pages a signed-out visitor can reach prerender neither set of masthead links: which one
// applies is known only once /me answers, so neither History/Sign out nor Sign in flashes wrongly.
test('the home page and View prerender no sign-in links; protected pages keep History and Sign out', () => {
  for (const name of ['index.html', 'view.html', 'signin.html']) {
    const html = readFileSync(join(out, name), 'utf8');
    assert.equal(/>(History|Sign out|Sign in)</.test(html), false, `${name}: no masthead links before /me answers`);
  }
  for (const name of ['set.html', 'results.html', 'history.html']) {
    const html = readFileSync(join(out, name), 'utf8');
    assert.match(html, />History</, name);
    assert.match(html, />Sign out</, name);
  }
});

test('the CSS declares the shared tokens only in the :where(:root) Classic Light fallback', () => {
  const all = sheets().flatMap((f) => rules(readFileSync(f, 'utf8')));
  const declaring = all.filter((r) => TOKENS.some((t) => new RegExp(`(^|;)\\s*--${t}\\s*:`).test(r.body)));
  assert.deepEqual([...new Set(declaring.map((r) => r.selector))], [':where(:root)'], 'no theme rule ships in the app CSS');
  const fallback = declaring[0].body;
  for (const t of TOKENS) assert.match(fallback, new RegExp(`(^|;)--${t}:`), `the fallback defines --${t}`);
  assert.match(fallback, /--surface:#EEF1F8/i, 'the fallback is Classic Light');
  assert.equal(all.some((r) => r.selector.includes('[data-theme')), false, 'no per-theme selectors in the app CSS');
});
