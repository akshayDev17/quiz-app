import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { ApiError, AUTH_RETRY_DELAY_MS, getMe, getTopics, isSessionExpired, saveAnswer } from './api.ts';

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

/** Answers each fetch with the next scripted response, recording every call's init. */
function scriptFetch(...responses: (() => Response)[]): RequestInit[] {
  const inits: RequestInit[] = [];
  globalThis.fetch = (async (_url: unknown, init?: RequestInit) => {
    inits.push(init ?? {});
    const next = responses.shift();
    if (!next) throw new Error('unexpected extra fetch');
    return next();
  }) as typeof fetch;
  return inits;
}

const status = (code: number, body?: unknown) => () =>
  new Response(body === undefined ? null : JSON.stringify(body), { status: code });

test('one transient 401 is retried after a pause and the retry wins', async () => {
  const inits = scriptFetch(status(401, { error: 'sign-in required' }), status(200, { topics: [] }));
  const started = Date.now();
  assert.deepEqual(await getTopics(), { topics: [] });
  assert.equal(inits.length, 2);
  assert.ok(Date.now() - started >= AUTH_RETRY_DELAY_MS - 20, 'the retry waits first');
});

test('two 401s in a row are a session expiry, with exactly one retry', async () => {
  const inits = scriptFetch(status(401), status(401));
  await assert.rejects(getMe(), (err) => isSessionExpired(err));
  assert.equal(inits.length, 2);
});

test('the retry resends the same method and body', async () => {
  const inits = scriptFetch(status(401), status(204));
  await saveAnswer('a1', 3, [7]);
  assert.equal(inits.length, 2);
  assert.equal(inits[1].method, 'PUT');
  assert.equal(inits[1].body, JSON.stringify({ option_ids: [7] }));
});

test('an Access redirect (expired session) is not retried', async () => {
  const opaque = () => {
    const res = new Response(null, { status: 200 });
    Object.defineProperty(res, 'type', { value: 'opaqueredirect' });
    return res;
  };
  const inits = scriptFetch(opaque);
  await assert.rejects(getMe(), (err) => isSessionExpired(err));
  assert.equal(inits.length, 1);
});

test('other failures are not retried', async () => {
  const inits = scriptFetch(status(500, { error: 'boom' }));
  await assert.rejects(getTopics(), (err) => err instanceof ApiError && err.status === 500);
  assert.equal(inits.length, 1);
});
