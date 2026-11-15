// Run: node --test worker.test.mjs   (npm run test:worker)
import assert from 'node:assert/strict';
import { test } from 'node:test';

import worker from './worker.js';

/** An ASSETS stub that records the URL it was asked for and answers with `respond`. */
function assets(respond) {
  const seen = [];
  return {
    seen,
    fetch: async (req) => {
      seen.push(new URL(req.url));
      return respond(new URL(req.url));
    },
  };
}

const call = (env, url) => worker.fetch(new Request(url), env);

test('strips the /quiz prefix before asking ASSETS', async () => {
  const env = { ASSETS: assets(() => new Response('ok')) };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/play?x=1');
  assert.equal(await res.text(), 'ok');
  assert.equal(env.ASSETS.seen[0].pathname, '/play');
  assert.equal(env.ASSETS.seen[0].search, '?x=1');
});

test('/quiz and /quiz/ both map to the asset root', async () => {
  const env = { ASSETS: assets(() => new Response('ok')) };
  await call(env, 'https://akshayprabhakant.com/quiz');
  await call(env, 'https://akshayprabhakant.com/quiz/');
  assert.deepEqual(env.ASSETS.seen.map((u) => u.pathname), ['/', '/']);
});

test('/quiz?<query> is served in place like /quiz, with the query kept (no redirect to the sign-in-only /quiz/)', async () => {
  const env = { ASSETS: assets(() => new Response('ok')) };
  for (const url of ['https://akshayprabhakant.com/quiz?x=1', 'https://akshayprabhakant.com/quiz?']) {
    const res = await call(env, url);
    assert.equal(res.status, 200, url);
    assert.equal(await res.text(), 'ok');
  }
  assert.deepEqual(env.ASSETS.seen.map((u) => [u.pathname, u.search]), [['/', '?x=1'], ['/', '']]);
});

/**
 * The zone route `quiz*` also catches paths that are not the app's. Each must
 * reach the origin as the very same Request, and never ASSETS or site-shell.
 */
test('a path that merely starts with the letters quiz goes to the origin untouched', async (t) => {
  const forwarded = [];
  t.mock.method(globalThis, 'fetch', async (req) => {
    forwarded.push(req);
    return new Response('origin', { status: 404 });
  });
  const env = { ASSETS: assets(page), SHELL: shell() };
  const urls = [
    'https://akshayprabhakant.com/quizzes',
    'https://akshayprabhakant.com/quizfoo?x=1',
    'https://akshayprabhakant.com/quiz.html',
    'https://akshayprabhakant.com/quiz-x/y?x=1',
    'https://akshayprabhakant.com/quiz_site/x.js',
  ];
  for (const url of urls) {
    const req = new Request(url, { method: 'POST', body: 'b', headers: { 'x-t': '1' } });
    const res = await worker.fetch(req, env);
    assert.equal(res.status, 404, url);
    assert.equal(await res.text(), 'origin');
    assert.equal(forwarded.at(-1), req, `${url}: the same Request object`);
  }
  assert.equal(forwarded.length, urls.length);
  assert.deepEqual(env.ASSETS.seen, []);
  assert.deepEqual(env.SHELL.calls, { compose: [], fetch: [] });
});

test('the app\'s own paths never go to the origin', async (t) => {
  const origin = t.mock.method(globalThis, 'fetch', async () => new Response('origin'));
  const env = { ASSETS: assets(() => new Response('ok')) };
  for (const path of ['/quiz', '/quiz?x=1', '/quiz/', '/quiz/play?x=1']) {
    assert.equal(await (await call(env, `https://akshayprabhakant.com${path}`)).text(), 'ok', path);
  }
  assert.equal(origin.mock.callCount(), 0);
});

test('re-prefixes a relative redirect Location', async () => {
  const env = { ASSETS: assets(() => new Response(null, { status: 308, headers: { location: '/play' } })) };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/play/');
  assert.equal(res.status, 308);
  assert.equal(res.headers.get('location'), '/quiz/play');
});

test('re-prefixes an absolute same-origin Location and keeps its query', async () => {
  const env = {
    ASSETS: assets(
      () => new Response(null, { status: 301, headers: { location: 'https://akshayprabhakant.com/play?a=1' } }),
    ),
  };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/play/?a=1');
  assert.equal(res.status, 301);
  assert.equal(res.headers.get('location'), '/quiz/play?a=1');
});

test('leaves a redirect that is already inside /quiz alone', async () => {
  const env = { ASSETS: assets(() => new Response(null, { status: 307, headers: { location: '/quiz/play' } })) };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/play/');
  assert.equal(res.headers.get('location'), '/quiz/play');
});

test('leaves a cross-origin redirect alone', async () => {
  const env = {
    ASSETS: assets(() => new Response(null, { status: 302, headers: { location: 'https://example.org/play' } })),
  };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/x');
  assert.equal(res.headers.get('location'), 'https://example.org/play');
});

test('passes a non-redirect response through untouched', async () => {
  const original = new Response('<p>hi</p>', { status: 200, headers: { 'content-type': 'text/html' } });
  const env = { ASSETS: assets(() => original) };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/');
  assert.equal(res, original);
});

test('passes a 404 through untouched', async () => {
  const env = { ASSETS: assets(() => new Response('nope', { status: 404 })) };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/missing');
  assert.equal(res.status, 404);
  assert.equal(await res.text(), 'nope');
});

// ── site-shell: the SHELL binding, the hook and its fail-open paths ──────────
// Stand-in bindings only; the real compose() runs only in workerd, which
// shell-contract/contract.test.mjs covers.

const HTML = '<!DOCTYPE html><html><head><meta charSet="utf-8"/></head><body>page</body></html>';
const page = () =>
  new Response(HTML, {
    headers: { 'content-type': 'text/html', etag: '"page"', 'last-modified': 'Mon, 02 Nov 2026 00:00:00 GMT' },
  });

/** SHELL: compose() marks the page (reading its body, as the RPC transfer does); fetch() echoes the path. */
function shell({ fail } = {}) {
  const calls = { compose: [], fetch: [] };
  return {
    calls,
    compose: async (res, opts) => {
      calls.compose.push(opts);
      const body = await res.text();
      if (fail) throw new Error(fail);
      return new Response(body.replace('<meta charSet="utf-8"/>', '$&<script data-site-shell></script>'), {
        headers: { 'content-type': 'text/html', 'x-site-shell': `test; app=${opts.app}` },
      });
    },
    fetch: async (req) => {
      calls.fetch.push(new URL(req.url).pathname);
      return new Response('site.js', { headers: { 'content-type': 'text/javascript' } });
    },
  };
}

test('with SHELL bound, HTML pages are composed with the app name and the forwarded asset base', async () => {
  const env = { ASSETS: assets(page), SHELL: shell() };
  for (const url of ['https://akshayprabhakant.com/quiz', 'https://akshayprabhakant.com/quiz/play?set=x']) {
    const res = await call(env, url);
    assert.equal(res.status, 200);
    assert.equal(res.headers.get('x-site-shell'), 'test; app=quiz');
    assert.match(await res.text(), /<meta charSet="utf-8"\/><script data-site-shell><\/script>/);
  }
  assert.deepEqual(env.SHELL.calls.compose, [
    { app: 'quiz', assetBase: '/quiz/_site/' },
    { app: 'quiz', assetBase: '/quiz/_site/' },
  ]);
  assert.deepEqual(env.ASSETS.seen.map((u) => u.pathname), ['/', '/play'], 'one ASSETS fetch per page when compose succeeds');
});

test('unbound: no SHELL binding serves the page exactly as built', async () => {
  const env = { ASSETS: assets(page) };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/');
  assert.equal(res.status, 200);
  assert.equal(res.headers.get('x-site-shell'), null);
  assert.equal(await res.text(), HTML);
});

test('fail open: compose() rejecting (site-shell missing, unreachable or throwing) re-fetches the page as built', async (t) => {
  const errors = t.mock.method(console, 'error', () => {});
  for (const fail of ['Worker "site-shell" not found.', 'fault: compose threw']) {
    const env = { ASSETS: assets(page), SHELL: shell({ fail }) };
    const res = await call(env, 'https://akshayprabhakant.com/quiz/history');
    assert.equal(res.status, 200);
    assert.equal(res.headers.get('x-site-shell'), null);
    assert.equal(await res.text(), HTML, 'the page as built, not a 500 from the spent body');
    assert.equal(res.headers.get('etag'), null, 'no validator to revalidate the uncomposed page against');
    assert.equal(res.headers.get('last-modified'), null);
    assert.deepEqual(env.ASSETS.seen.map((u) => u.pathname), ['/history', '/history'], 'the same page fetched again');
  }
  assert.equal(errors.mock.callCount(), 2);
  assert.match(String(errors.mock.calls[0].arguments[0]), /site-shell: compose failed/);
});

test('with SHELL bound, non-HTML, non-200 and redirects never reach compose(); redirects are still re-prefixed', async () => {
  const responses = {
    '/_next/static/css/app.css': () => new Response('a{}', { headers: { 'content-type': 'text/css', etag: 'W/"1"' } }),
    '/icon.svg': () => new Response('<svg/>', { headers: { 'content-type': 'image/svg+xml' } }),
    '/missing': () => new Response('nope', { status: 404, headers: { 'content-type': 'text/html' } }),
    '/play/': () => new Response(null, { status: 308, headers: { location: '/play' } }),
    '/cached': () => new Response(null, { status: 304, headers: { 'content-type': 'text/html' } }),
  };
  const env = { ASSETS: assets((u) => responses[u.pathname]()), SHELL: shell() };
  for (const path of Object.keys(responses)) {
    const res = await call(env, `https://akshayprabhakant.com/quiz${path}`);
    assert.equal(res.headers.get('x-site-shell'), null, path);
  }
  assert.equal(env.SHELL.calls.compose.length, 0);
  const css = await call(env, 'https://akshayprabhakant.com/quiz/_next/static/css/app.css');
  assert.equal(css.headers.get('etag'), 'W/"1"', 'validators kept');
  const redirect = await call(env, 'https://akshayprabhakant.com/quiz/play/');
  assert.equal(redirect.headers.get('location'), '/quiz/play');
});

test('/quiz/_site/* forwards to site-shell with the prefix stripped', async () => {
  const env = { ASSETS: assets(page), SHELL: shell() };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/_site/1132669f0ee1/site.js');
  assert.equal(await res.text(), 'site.js');
  assert.deepEqual(env.SHELL.calls.fetch, ['/_site/1132669f0ee1/site.js']);
  assert.deepEqual(env.ASSETS.seen, []);
});

test('/_site/* forwards to site-shell as is (only under wrangler dev; the zone routes it to site-shell)', async () => {
  const env = { ASSETS: assets(page), SHELL: shell() };
  const res = await call(env, 'http://127.0.0.1:8787/_site/1132669f0ee1/site.js');
  assert.equal(await res.text(), 'site.js');
  assert.deepEqual(env.SHELL.calls.fetch, ['/_site/1132669f0ee1/site.js']);
  assert.deepEqual(env.ASSETS.seen, []);
});

test('/quiz/_site/* without SHELL falls through to ASSETS as before', async () => {
  const env = { ASSETS: assets(() => new Response('Not Found', { status: 404 })) };
  const res = await call(env, 'https://akshayprabhakant.com/quiz/_site/1132669f0ee1/site.js');
  assert.equal(res.status, 404);
  assert.deepEqual(env.ASSETS.seen.map((u) => u.pathname), ['/_site/1132669f0ee1/site.js']);
});
