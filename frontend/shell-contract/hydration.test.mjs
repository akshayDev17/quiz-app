// Every exported page loaded in headless Chrome. Composed by the real
// site-shell (harness.mjs): React must hydrate it with no hydration warning or
// error and nothing logged as a console error, and site-shell's site.js must
// define <site-theme-picker>, which the app no longer bundles. Unbound: the
// page falls back to Classic Light from globals.css. The quiz API is not part
// of this session, so its calls are held open and the page hydrates into its
// loading state. So are Next's RSC prefetches (`?_rsc=`), which fetch later
// navigations, not this page.
//
//   SITE_THEMES_DIR=/path/to/site-themes npm run test:hydration
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright-core';
import { APP, PAGES, SHELL, UNBOUND, session } from './harness.mjs';

let browser;
before(async () => {
  browser = await chromium.launch({ channel: 'chrome' });
});
after(() => browser?.close());

/** Opens `path` with the API and prefetches held open; resolves once React has hydrated. */
async function open(base, path, problems) {
  const page = await browser.newPage();
  page.on('pageerror', (err) => problems.push(`uncaught: ${err.message}`));
  page.on('console', (msg) => {
    if (msg.type() === 'error' || /hydrat/i.test(msg.text())) problems.push(`console.${msg.type()}: ${msg.text()} (${msg.location().url})`);
  });
  await page.route((url) => url.pathname.startsWith('/quiz/api/') || url.searchParams.has('_rsc'), () => {});
  const res = await page.goto(`${base}${path}`, { waitUntil: 'load' });
  await page.waitForFunction(() => Object.keys(document.body).some((k) => k.startsWith('__reactFiber$')));
  return { page, res };
}

test('bound to site-shell: every composed page hydrates with no console error and defines <site-theme-picker>', async (t) => {
  const s = await session(t, [APP, SHELL]);
  for (const path of Object.keys(PAGES)) {
    const problems = [];
    const { page, res } = await open(s.base, path, problems);
    assert.match(res.headers()['x-site-shell'] ?? '', /; app=quiz$/, `${path} was composed`);
    await page.waitForFunction(() => customElements.get('site-theme-picker') !== undefined, null, { timeout: 10_000 });
    await page.waitForTimeout(500);
    const pickers = await page.evaluate(() => [...document.querySelectorAll('site-theme-picker')].map((el) => el.matches(':defined') && el.shadowRoot !== null));
    await page.close();

    assert.ok(pickers.every(Boolean), `${path}: every <site-theme-picker> is upgraded`);
    assert.deepEqual(problems, [], path);
  }
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
      };
    });
    await page.close();

    assert.deepEqual(state, { theme: null, surface: '#EEF1F8', accent: '#3A4BD8', picker: false }, path);
    assert.deepEqual(problems, [], path);
  }
});
