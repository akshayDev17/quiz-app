import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { saveAnswer } from './api.ts';

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function captureFetch(): RequestInit[] {
  const inits: RequestInit[] = [];
  globalThis.fetch = (async (_url: unknown, init?: RequestInit) => {
    inits.push(init ?? {});
    return new Response(null, { status: 204 });
  }) as typeof fetch;
  return inits;
}

test('saveAnswer passes keepalive through to fetch', async () => {
  const inits = captureFetch();
  await saveAnswer('a1', 3, [7], undefined, true);
  assert.equal(inits[0].keepalive, true);
  assert.equal(inits[0].method, 'PUT');
  assert.equal(inits[0].body, JSON.stringify({ option_ids: [7] }));
});

test('an ordinary save is not keepalive and carries its abort signal', async () => {
  const inits = captureFetch();
  const controller = new AbortController();
  await saveAnswer('a1', 3, [7], controller.signal);
  assert.ok(!inits[0].keepalive);
  assert.equal(inits[0].signal, controller.signal);
});
