// Every exported page, composed by the real site-shell (harness.mjs), loaded in
// headless Chrome: React must hydrate it with no hydration warning or error and
// nothing logged as a console error. The quiz API is not part of this session,
// so its calls are held open and the page hydrates into its loading state. So
// are Next's RSC prefetches (`?_rsc=`), which fetch later navigations, not
// this page.
//
//   SITE_THEMES_DIR=/path/to/site-themes npm run test:hydration
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { chromium } from 'playwright-core';
import { APP, PAGES, SHELL, session } from './harness.mjs';

let browser;
before(async () => {
  browser = await chromium.launch({ channel: 'chrome' });
});
after(() => browser?.close());

test('bound to site-shell: every composed page hydrates with no console error', async (t) => {
  const s = await session(t, [APP, SHELL]);
  for (const path of Object.keys(PAGES)) {
    const page = await browser.newPage();
    const problems = [];
    page.on('pageerror', (err) => problems.push(`uncaught: ${err.message}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error' || /hydrat/i.test(msg.text())) problems.push(`console.${msg.type()}: ${msg.text()} (${msg.location().url})`);
    });
    await page.route((url) => url.pathname.startsWith('/quiz/api/') || url.searchParams.has('_rsc'), () => {});

    const res = await page.goto(`${s.base}${path}`, { waitUntil: 'load' });
    assert.match(res.headers()['x-site-shell'] ?? '', /; app=quiz$/, `${path} was composed`);
    await page.waitForFunction(() => Object.keys(document.body).some((k) => k.startsWith('__reactFiber$')));
    await page.waitForTimeout(500);
    await page.close();

    assert.deepEqual(problems, [], path);
  }
});
