// Every exported page loaded in headless Chrome. Composed by the real
// site-shell (harness.mjs): React must hydrate it with no hydration warning or
// error and nothing logged as a console error, site-shell's site.js must
// define <site-theme-picker>, which the app no longer bundles, and the site
// path site-shell put in the masthead must survive hydration and client-side
// navigation. Unbound: the page falls back to Classic Light from globals.css
// and the masthead keeps the old breadcrumb. The quiz API is not part
// of this session, so its calls are held open and the page hydrates into its
// loading state. So are Next's RSC prefetches (`?_rsc=`), which fetch later
// navigations, not this page.
//
//   SITE_THEMES_DIR=/path/to/site-themes npm run test:hydration
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright-core';
import { APP, PAGES, SHELL, TAILS, UNBOUND, session } from './harness.mjs';

let browser;
before(async () => {
  browser = await chromium.launch({ channel: 'chrome' });
});
after(() => browser?.close());

/**
 * Opens `path` with the API and prefetches held open; resolves once React has hydrated.
 * `navigableTo` lets through the RSC fetches for those pages (each exported page's path
 * without its extension), which a client-side navigation to them needs.
 */
async function open(base, path, problems, { viewport = { width: 1280, height: 800 }, navigableTo = [] } = {}) {
  const page = await browser.newPage({ viewport });
  page.on('pageerror', (err) => problems.push(`uncaught: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error' || /hydrat/i.test(msg.text())) problems.push(`console.${msg.type()}: ${msg.text()} (${msg.location().url})`);
  });
  await page.route((url) => url.pathname.startsWith('/quiz/api/') || (url.searchParams.has('_rsc') && !navigableTo.some((p) => url.pathname.startsWith(`${p}.`))), () => {});
  const res = await page.goto(`${base}${path}`, { waitUntil: 'load' });
  await page.waitForFunction(() => Object.keys(document.body).some((k) => k.startsWith('__reactFiber$')));
  return { page, res };
}

/**
 * The masthead's site path as the reader gets it: the app marked current, the crumbs
 * shown after it, and any visible link or plain-text item shorter than 44 px. Null when
 * the slot holds something else (the fallback breadcrumb).
 */
function readSitePath(page) {
  return page.evaluate(() => {
    const nav = document.querySelector('header.masthead site-slot[name="site-path"] nav[aria-label="Site path"]');
    if (!nav) return null;
    const shown = (el) => el.getClientRects().length > 0;
    const current = nav.querySelector('.sp-apps [aria-current]');
    return {
      current: current && { label: current.querySelector('.sp-label')?.textContent, ariaCurrent: current.getAttribute('aria-current') },
      crumbs: [...nav.querySelectorAll('.sp-crumb')].filter(shown).map((c) => c.lastElementChild.textContent),
      small: [...nav.querySelectorAll('a, .sp-here, button')].filter(shown)
        .filter((el) => el.getBoundingClientRect().height < (el.matches('.sp-pill') ? 34 : 44)).map((el) => el.textContent),
    };
  });
}

/** What readSitePath() must return on a page whose crumbs are `tail`. */
const expectedSitePath = (tail) => ({
  current: { label: 'Quiz Room', ariaCurrent: tail.length === 0 ? 'page' : 'true' },
  crumbs: tail.map((c) => c.label),
  small: [],
});

test('bound to site-shell: every composed page hydrates with no console error and defines <site-theme-picker>', async (t) => {
  const s = await session(t, [APP, SHELL]);
  for (const path of Object.keys(PAGES)) {
    const problems = [];
    const { page, res } = await open(s.base, path, problems);
    assert.match(res.headers()['x-site-shell'] ?? '', /; app=quiz$/, `${path} was composed`);
    await page.waitForFunction(() => customElements.get('site-theme-picker') !== undefined, null, { timeout: 10_000 });
    await page.waitForTimeout(500);
    const pickers = await page.evaluate(() => [...document.querySelectorAll('site-theme-picker')].map((el) => el.matches(':defined') && el.shadowRoot !== null));
    const sitePath = await readSitePath(page);
    await page.close();

    assert.ok(pickers.every(Boolean), `${path}: every <site-theme-picker> is upgraded`);
    assert.deepEqual(sitePath, expectedSitePath(TAILS[PAGES[path]]), `${path}: the site path survives hydration`);
    assert.deepEqual(problems, [], path);
  }
});

test('bound: client-side navigations never show the fallback breadcrumb and fetch no page once the switcher is there', async (t) => {
  const s = await session(t, [APP, SHELL]);
  const problems = [];
  const { page } = await open(s.base, '/quiz/', problems, { navigableTo: ['/quiz/history', '/quiz/index'] });
  const pageFetches = [];
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (r.resourceType() === 'fetch' && !url.searchParams.has('_rsc') && !url.pathname.startsWith('/quiz/api/')) pageFetches.push(url.pathname);
  });
  await page.evaluate(() => {
    window.sawFallback = false;
    const isFallback = (n) => n.nodeType === 1 && (n.matches('nav[aria-label="Breadcrumb"]') || n.querySelector('nav[aria-label="Breadcrumb"]'));
    new MutationObserver((records) => {
      if (records.some((r) => [...r.addedNodes].some(isFallback))) window.sawFallback = true;
    }).observe(document, { childList: true, subtree: true });
  });
  const atHome = await readSitePath(page);

  await page.click('header.masthead .who a[href="/quiz/history"]');
  await page.waitForURL('**/quiz/history');
  await page.waitForFunction(() => document.querySelector('header.masthead .sp-page')?.textContent === 'History', null, { timeout: 10_000 });
  await page.waitForTimeout(500);
  const atHistory = await readSitePath(page);

  await page.goBack();
  await page.waitForURL((url) => url.pathname === '/quiz/');
  await page.waitForFunction(() => !document.querySelector('header.masthead .sp-page'), null, { timeout: 10_000 });
  await page.waitForTimeout(500);
  const back = await readSitePath(page);
  const sheetCurrent = await page.evaluate(() => document.querySelector('#site-path-sheet a[aria-current]')?.getAttribute('aria-current'));
  const sawFallback = await page.evaluate(() => window.sawFallback);
  await page.close();

  assert.deepEqual(atHome, expectedSitePath(TAILS['index.html']), 'the quiz home as composed');
  assert.deepEqual(atHistory, expectedSitePath(TAILS['history.html']), 'History: the quiz is a link and History the current page');
  assert.deepEqual(back, expectedSitePath(TAILS['index.html']), 'back home: the quiz is the current page again, with no crumbs');
  assert.equal(sheetCurrent, 'page', 'the phone sheet marks the quiz home as the current page');
  assert.equal(sawFallback, false, 'the fallback breadcrumb never rendered');
  assert.deepEqual(pageFetches, [], 'no page was fetched for its site path');
  assert.deepEqual(problems, [], 'no console error');
});

test('bound: on a portrait phone the apps fold into a button that opens a bottom sheet; in landscape they stay inline', async (t) => {
  const s = await session(t, [APP, SHELL]);
  const problems = [];
  const portrait = (await open(s.base, '/quiz/admin/edit', problems, { viewport: { width: 390, height: 844 } })).page;
  await portrait.waitForFunction(() => customElements.get('site-theme-picker') !== undefined, null, { timeout: 10_000 });
  const folded = await portrait.evaluate(() => {
    const shown = (sel) => document.querySelector(`header.masthead ${sel}`)?.getClientRects().length > 0;
    return { apps: shown('.sp-apps'), pill: shown('.sp-pill') };
  });
  const before = await readSitePath(portrait);
  await portrait.click('header.masthead .sp-pill');
  await portrait.waitForFunction(() => document.getElementById('site-path-sheet')?.open, null, { timeout: 5_000 });
  const sheet = await portrait.evaluate(() => {
    const dialog = document.getElementById('site-path-sheet');
    const r = dialog.getBoundingClientRect();
    return {
      atBottom: Math.round(r.bottom) === window.innerHeight,
      apps: [...dialog.querySelectorAll('li .sp-name')].map((n) => n.firstChild.textContent),
      current: dialog.querySelector('li a[aria-current]')?.querySelector('.sp-name').firstChild.textContent,
    };
  });
  await portrait.click('#site-path-sheet .sp-close');
  await portrait.waitForFunction(() => !document.getElementById('site-path-sheet').open, null, { timeout: 5_000 });
  await portrait.close();

  assert.deepEqual(folded, { apps: false, pill: true }, 'portrait: the apps fold into the button');
  assert.deepEqual(before.crumbs, ['Edit set'], 'portrait: only the last crumb shows');
  assert.deepEqual(before.small, [], 'portrait: every target is at least 44 px (the button is drawn 34 px)');
  assert.equal(sheet.atBottom, true, 'the sheet sits at the bottom of the screen');
  assert.ok(sheet.apps.includes('Portfolio') && sheet.apps.includes('Quiz Room'), `the sheet lists the apps: ${sheet.apps}`);
  assert.equal(sheet.current, 'Quiz Room');

  const landscape = (await open(s.base, '/quiz/history', problems, { viewport: { width: 844, height: 390 } })).page;
  const inline = await landscape.evaluate(() => {
    const shown = (sel) => document.querySelector(`header.masthead ${sel}`)?.getClientRects().length > 0;
    return { apps: shown('.sp-apps'), pill: shown('.sp-pill') };
  });
  const sitePath = await readSitePath(landscape);
  await landscape.close();

  assert.deepEqual(inline, { apps: true, pill: false }, 'landscape: the apps sit inline');
  assert.deepEqual(sitePath, expectedSitePath(TAILS['history.html']));
  assert.deepEqual(problems, [], 'no console error');
});

test('unbound: every page falls back to Classic Light from globals.css, with no console error', async (t) => {
  const s = await session(t, [UNBOUND]);
  for (const path of Object.keys(PAGES)) {
    const problems = [];
    const { page, res } = await open(s.base, path, problems);
    assert.equal(res.headers()['x-site-shell'], undefined, `${path} was not composed`);
    await page.waitForTimeout(500);
    const state = await page.evaluate(() => {
      const css = getComputedStyle(document.documentElement);
      return {
        theme: document.documentElement.getAttribute('data-theme'),
        surface: css.getPropertyValue('--surface').trim(),
        accent: css.getPropertyValue('--accent').trim(),
        picker: customElements.get('site-theme-picker') !== undefined,
        breadcrumb: document.querySelector('header.masthead site-slot[name="site-path"] nav[aria-label="Breadcrumb"]')?.textContent,
      };
    });
    await page.close();

    assert.deepEqual(state, { theme: null, surface: '#EEF1F8', accent: '#3A4BD8', picker: false, breadcrumb: 'akshayprabhakant.com/quiz' }, path);
    assert.deepEqual(problems, [], path);
  }
});
