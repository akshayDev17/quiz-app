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

test('does not strip a path that merely starts with the letters quiz', async () => {
  const env = { ASSETS: assets(() => new Response('ok')) };
  await call(env, 'https://akshayprabhakant.com/quizzes');
  assert.equal(env.ASSETS.seen[0].pathname, '/quizzes');
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
