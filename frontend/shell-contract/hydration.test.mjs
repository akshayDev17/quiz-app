// Every exported page loaded in headless Chrome. Composed by the real
// site-shell (harness.mjs): React must hydrate it with no hydration warning or
// error and nothing logged as a console error, site-shell's site.js must
// define <site-theme-picker>, which the app no longer bundles, and the site
// path site-shell put in the masthead (the site row, and the page's trail on
// its own line under it) must survive hydration and client-side navigation.
// Unbound: the page falls back to Classic Light from globals.css and the slot
// stays empty. The quiz API is not part
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

/** A signed-in reader, for the one API call the masthead's links wait on. */
const ME = { email: 'reader@example.com', display_name: 'Reader', role: 'solver' };

/**
 * Opens `path` with the API and prefetches held open, except /me, which answers signed in
 * (the quiz home shows History and Sign out once it does); resolves once React has hydrated.
 * `navigableTo` lets through the RSC fetches for those pages (each exported page's path
 * without its extension), which a client-side navigation to them needs.
 */
async function open(base, path, problems, { viewport = { width: 1280, height: 800 }, navigableTo = [] } = {}) {
  const page = await browser.newPage({ viewport });
  page.on('pageerror', (err) => problems.push(`uncaught: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error' || /hydrat/i.test(msg.text())) problems.push(`console.${msg.type()}: ${msg.text()} (${msg.location().url})`);
  });
  await page.route((url) => url.pathname.startsWith('/quiz/api/') || (url.searchParams.has('_rsc') && !navigableTo.some((p) => url.pathname.startsWith(`${p}.`))), (route) => {
    if (new URL(route.request().url()).pathname === '/quiz/api/me') return route.fulfill({ json: ME });
  });
  const res = await page.goto(`${base}${path}`, { waitUntil: 'load' });
  await page.waitForFunction(() => Object.keys(document.body).some((k) => k.startsWith('__reactFiber$')));
  return { page, res };
}

/**
 * The masthead's site path as the reader gets it: the apps in the row, the one marked
 * current, the trail line's crumbs, and any visible target shorter than 44 px in the row
 * or 32 px in the trail. Null when the slot holds no site row.
 */
function readSitePath(page) {
  return page.evaluate(() => {
    const slot = document.querySelector('header.masthead site-slot[name="site-path"]');
    const row = slot?.querySelector('nav.sp[aria-label="Site"] .sp-apps');
    if (!row) return null;
    const shown = (el) => el.getClientRects().length > 0;
    const name = (a) => (a.querySelector('.sp-label') ?? a).firstChild.textContent;
    const current = row.querySelector('[aria-current]');
    const trail = slot.querySelector('nav.sp-trail[aria-label="Breadcrumb"]');
    return {
      apps: [...row.querySelectorAll('a')].map(name),
      current: current && { label: name(current), ariaCurrent: current.getAttribute('aria-current') },
      trail: trail ? [...trail.querySelectorAll('li')].map((li) => li.textContent) : [],
      small: [...row.querySelectorAll('a')].filter((el) => el.getBoundingClientRect().height < 44)
        .concat(trail ? [...trail.querySelectorAll('a')].filter((el) => el.getBoundingClientRect().height < 32) : [])
        .filter(shown).map((el) => el.textContent),
    };
  });
}

const APP_LABELS = ['Home', 'AI Digest', 'Quiz Room', 'Graph Notes', 'Election Atlas'];

/** What readSitePath() must return on a page whose crumbs after "Quiz Room" are `tail`. */
const expectedSitePath = (tail) => ({
  apps: APP_LABELS,
  current: { label: 'Quiz Room', ariaCurrent: tail.length === 0 ? 'page' : 'true' },
  trail: tail.length === 0 ? [] : ['Quiz Room', ...tail.map((c) => c.label)],
  small: [],
});

/** Pages that leave as soon as they load, by design: /signin hands the reader back to the quiz home. */
const LEAVES = { '/quiz/signin': '/quiz' };

test('bound to site-shell: every composed page hydrates with no console error and defines <site-theme-picker>', async (t) => {
  const s = await session(t, [APP, SHELL]);
  for (const path of Object.keys(PAGES).filter((p) => !(p in LEAVES))) {
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

test('bound: /signin hands the reader straight back to the quiz home', async (t) => {
  const s = await session(t, [APP, SHELL]);
  for (const [path, home] of Object.entries(LEAVES)) {
    const problems = [];
    const page = await browser.newPage();
    page.on('pageerror', (err) => problems.push(`uncaught: ${err.message}`));
    await page.route((url) => url.pathname.startsWith('/quiz/api/'), () => {});
    await page.goto(`${s.base}${path}`);
    await page.waitForURL((url) => url.pathname.replace(/\/$/, '') === home, { timeout: 10_000 });
    await page.close();
    assert.deepEqual(problems, [], path);
  }
});

/**
 * Records, once per frame from now on, what the masthead's site path paints: the row's
 * box, scroll and current app, and the trail line's text (null for no trail, 'missing'
 * for no row at all). `window.siteFrames()` returns the frames since the last call.
 */
function recordFrames(page) {
  return page.evaluate(() => {
    let frames = [];
    const sample = () => {
      const slot = document.querySelector('header.masthead site-slot[name="site-path"]');
      const row = slot?.querySelector('.sp-apps');
      if (!row) frames.push('missing');
      else {
        const r = row.getBoundingClientRect();
        frames.push(JSON.stringify({
          row: [r.left, r.top, r.width, r.height, row.scrollLeft, row.dataset.more ?? ''],
          current: row.querySelector('[aria-current] .sp-label')?.textContent,
          trail: slot.querySelector('.sp-trail')?.textContent ?? null,
          trailTop: slot.querySelector('.sp-trail')?.getBoundingClientRect().top ?? null,
        }));
      }
      requestAnimationFrame(sample);
    };
    requestAnimationFrame(sample);
    window.siteFrames = () => {
      const seen = [...new Set(frames)].map((f) => (f === 'missing' ? f : JSON.parse(f)));
      frames = [];
      return seen;
    };
  });
}

/**
 * Navigates client-side with `go`, waits for `pathname`, and returns the distinct frames
 * painted from just before the move until the trail settles on `trail`.
 */
async function navigate(page, go, pathname, trail) {
  await page.evaluate(() => window.siteFrames());
  await go();
  await page.waitForFunction((want) => location.pathname.replace(/\/$/, '') === want, pathname, { timeout: 10_000 });
  await page.waitForFunction((want) => (document.querySelector('header.masthead .sp-trail')?.textContent ?? null) === want, trail, { timeout: 10_000 });
  await page.waitForTimeout(300);
  return page.evaluate(() => window.siteFrames());
}

test('bound: client-side navigations keep the row as composed and redraw only the trail line, with no frame between', async (t) => {
  const s = await session(t, [APP, SHELL]);
  const problems = [];
  const { page } = await open(s.base, '/quiz/', problems, { navigableTo: ['/quiz/history', '/quiz/set', '/quiz/play', '/quiz/index'] });
  await page.waitForFunction(() => customElements.get('site-theme-picker') !== undefined, null, { timeout: 10_000 });
  const pageFetches = [];
  page.on('request', (r) => {
    const url = new URL(r.url());
    if (r.resourceType() === 'fetch' && !url.searchParams.has('_rsc') && !url.pathname.startsWith('/quiz/api/')) pageFetches.push(url.pathname);
  });
  const atHome = await readSitePath(page);
  await recordFrames(page);
  await page.waitForTimeout(200);
  const [home] = await page.evaluate(() => window.siteFrames());

  const toHistory = await navigate(page, () => page.click('header.masthead .who a[href="/quiz/history"]'), '/quiz/history', 'Quiz RoomHistory');
  const atHistory = await readSitePath(page);
  // Next's own client-side router (what a <Link> calls), since this page's links to a quiz need the API.
  const push = (href) => () => page.evaluate((h) => window.next.router.push(h), href);
  const toQuiz = await navigate(page, push('/set?id=x'), '/quiz/set', 'Quiz RoomQuiz');
  const atQuiz = await readSitePath(page);
  const toAttempt = await navigate(page, push('/play?attempt=y'), '/quiz/play', 'Quiz RoomAttempt');
  const atAttempt = await readSitePath(page);
  // Then back, step by step, to the quiz home. Back, not the wordmark: a client-side move to
  // the quiz home needs /quiz.txt, which the export does not write (it writes index.txt), so
  // following that link loads the page anew.
  const backToQuiz = await navigate(page, () => page.goBack(), '/quiz/set', 'Quiz RoomQuiz');
  const backToHistory = await navigate(page, () => page.goBack(), '/quiz/history', 'Quiz RoomHistory');
  const backHome = await navigate(page, () => page.goBack(), '/quiz', null);
  const back = await readSitePath(page);
  await page.close();

  assert.deepEqual(atHome, expectedSitePath(TAILS['index.html']), 'the quiz home as composed');
  assert.deepEqual(atHistory, expectedSitePath(TAILS['history.html']), 'History');
  assert.deepEqual(atQuiz, expectedSitePath(TAILS['set.html']), 'a quiz');
  assert.deepEqual(atAttempt, expectedSitePath(TAILS['play.html']), 'an attempt');
  assert.deepEqual(back, expectedSitePath(TAILS['index.html']), 'back home: the quiz is the current page again, with no trail');

  // Every frame painted on the way shows the same row in the same place, scrolled the
  // same; the trail line goes straight from the old page's to the new page's.
  const moves = {
    toHistory: [null, 'Quiz RoomHistory'], toQuiz: ['Quiz RoomHistory', 'Quiz RoomQuiz'], toAttempt: ['Quiz RoomQuiz', 'Quiz RoomAttempt'],
    backToQuiz: ['Quiz RoomAttempt', 'Quiz RoomQuiz'], backToHistory: ['Quiz RoomQuiz', 'Quiz RoomHistory'], backHome: ['Quiz RoomHistory', null],
  };
  const frames = { toHistory, toQuiz, toAttempt, backToQuiz, backToHistory, backHome };
  for (const [move, [from, to]] of Object.entries(moves)) {
    const seen = frames[move];
    assert.ok(!seen.includes('missing'), `${move}: the row is painted in every frame`);
    assert.deepEqual([...new Set(seen.map((f) => JSON.stringify([f.row, f.current])))], [JSON.stringify([home.row, 'Quiz Room'])],
      `${move}: the row never moves, rescrolls or changes`);
    for (const f of seen) assert.ok(f.trail === from || f.trail === to, `${move}: no trail in between (${f.trail})`);
    const trailTops = [...new Set(seen.filter((f) => f.trail !== null).map((f) => f.trailTop))];
    assert.ok(trailTops.length <= 1, `${move}: the trail line stays on one line under the row (${trailTops})`);
  }
  assert.deepEqual(pageFetches, [], 'no page was fetched for its site path');
  assert.deepEqual(problems, [], 'no console error');
});

test('bound: on a portrait phone the row is one line that scrolls sideways, the quiz in view and the edge faded; in landscape it sits inline', async (t) => {
  const s = await session(t, [APP, SHELL]);
  const problems = [];
  const portrait = (await open(s.base, '/quiz/history', problems, { viewport: { width: 390, height: 844 }, navigableTo: ['/quiz/play'] })).page;
  await portrait.waitForFunction(() => customElements.get('site-theme-picker') !== undefined, null, { timeout: 10_000 });
  await portrait.waitForFunction(() => document.querySelector('header.masthead .sp-apps')?.dataset.more, null, { timeout: 5_000 });
  const measure = () => portrait.evaluate(() => {
    const row = document.querySelector('header.masthead .sp-apps');
    const box = row.getBoundingClientRect();
    const quiz = row.querySelector('[aria-current]').getBoundingClientRect();
    const trail = document.querySelector('header.masthead .sp-trail')?.getBoundingClientRect();
    return {
      oneLine: new Set([...row.querySelectorAll('li')].map((li) => Math.round(li.getBoundingClientRect().top))).size === 1,
      scrolls: row.scrollWidth > row.clientWidth,
      quizInView: quiz.left >= box.left && quiz.right <= box.right,
      more: row.dataset.more,
      scrollLeft: row.scrollLeft,
      trailUnder: trail ? trail.top >= box.bottom : null,
      pageWide: document.documentElement.scrollWidth > window.innerWidth,
      sheet: document.querySelector('header.masthead dialog, header.masthead .sp-pill') !== null,
    };
  });
  const before = await measure();
  const sitePath = await readSitePath(portrait);
  await recordFrames(portrait);
  await portrait.waitForTimeout(200);
  const [settled] = await portrait.evaluate(() => window.siteFrames());
  // The attempt page shows who is signed in as soon as that loads, a moment after the move,
  // which renders the masthead again: the row must stay as it is through that too.
  await portrait.route((url) => url.pathname === '/quiz/api/me', async (route) => {
    await new Promise((r) => setTimeout(r, 150));
    await route.fulfill({ json: { email: 'reader@example.com', display_name: 'Reader', role: 'user' } });
  });
  const moving = await navigate(portrait, () => portrait.evaluate(() => window.next.router.push('/play?attempt=y')), '/quiz/play', 'Quiz RoomAttempt');
  await portrait.waitForFunction(() => document.querySelector('header.masthead .uname')?.textContent === 'Reader', null, { timeout: 5_000 });
  await portrait.waitForTimeout(300);
  moving.push(...await portrait.evaluate(() => window.siteFrames()));
  const afterNav = await measure();
  await portrait.close();

  assert.equal(before.oneLine, true, 'portrait: the row is one line');
  assert.equal(before.scrolls, true, 'portrait: the row scrolls sideways');
  assert.equal(before.quizInView, true, 'portrait: the quiz is scrolled into view');
  assert.ok(before.more, 'portrait: an edge with apps past it is faded');
  assert.equal(before.trailUnder, true, 'portrait: the trail is on its own line under the row');
  assert.equal(before.pageWide, false, 'portrait: the page never scrolls sideways');
  assert.equal(before.sheet, false, 'portrait: no sheet');
  assert.deepEqual(sitePath, expectedSitePath(TAILS['history.html']), 'portrait: the whole trail and 44 px row targets');
  assert.deepEqual({ ...afterNav, trailUnder: true }, { ...before, trailUnder: true }, 'portrait: after a client-side move the row is where it was');
  assert.ok(!moving.includes('missing'), 'portrait: the row is painted in every frame of the move');
  assert.deepEqual([...new Set(moving.map((f) => JSON.stringify(f.row)))], [JSON.stringify(settled.row)],
    'portrait: no frame of the move shows the row scrolled elsewhere or unfaded');

  const landscape = (await open(s.base, '/quiz/history', problems, { viewport: { width: 844, height: 390 } })).page;
  const inline = await landscape.evaluate(() => {
    const row = document.querySelector('header.masthead .sp-apps');
    return { fits: row.scrollWidth <= row.clientWidth, more: row.dataset.more ?? null };
  });
  const landscapePath = await readSitePath(landscape);
  await landscape.close();

  assert.deepEqual(inline, { fits: true, more: null }, 'landscape: the whole row sits inline');
  assert.deepEqual(landscapePath, expectedSitePath(TAILS['history.html']));
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
        sitePath: document.querySelector('header.masthead site-slot[name="site-path"]').innerHTML,
        slot: getComputedStyle(document.querySelector('header.masthead site-slot[name="site-path"]')).display,
      };
    });
    await page.close();

    assert.deepEqual(state, { theme: null, surface: '#EEF1F8', accent: '#3A4BD8', picker: false, sitePath: '', slot: 'block' }, path);
    assert.deepEqual(problems, [], path);
  }
});

test('unbound: a route whose page fetch failed is fetched again on the next visit; one that came back plain is not', async (t) => {
  const s = await session(t, [UNBOUND]);
  const problems = [];
  const { page } = await open(s.base, '/quiz/', problems, { navigableTo: ['/quiz/history', '/quiz/index'] });
  const pageFetches = [];
  let failNext = true;
  await page.route((url) => url.pathname === '/quiz/history' && !url.searchParams.has('_rsc'), (route) => {
    pageFetches.push(failNext ? 'failed' : 'ok');
    if (failNext) {
      failNext = false;
      return route.abort();
    }
    return route.continue();
  });
  const visitHistory = async () => {
    await page.click('header.masthead .who a[href="/quiz/history"]');
    await page.waitForURL('**/quiz/history');
    await page.waitForTimeout(500);
    await page.goBack();
    await page.waitForURL((url) => url.pathname === '/quiz/');
    await page.waitForTimeout(500);
  };
  await visitHistory();
  await visitHistory();
  await visitHistory();
  await page.close();

  assert.deepEqual(pageFetches, ['failed', 'ok'], 'retried after the failure, then not again once the page came back without a site path');
});
