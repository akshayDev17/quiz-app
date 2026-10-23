import assert from 'node:assert/strict';
import { afterEach, beforeEach, mock, test } from 'node:test';

import { ApiError } from './api.ts';
import { SaveQueue } from './saveQueue.ts';

type Call = [number, number[]];

/** A save that records its calls and fails the first `failures` of them. */
function recorder(failures = 0, error: unknown = new Error('offline')) {
  const calls: Call[] = [];
  let left = failures;
  const save = async (qid: number, ids: number[]) => {
    calls.push([qid, ids]);
    if (left > 0) {
      left -= 1;
      throw error;
    }
  };
  return { calls, save };
}

/** Lets settled promises run their handlers. */
const drain = () => new Promise<void>((r) => setImmediate(r));

beforeEach(() => mock.timers.enable({ apis: ['setTimeout'] }));
afterEach(() => mock.timers.reset());

test('debounces per question, last value wins', async () => {
  const { calls, save } = recorder();
  const q = new SaveQueue(save);
  q.set(1, [1]);
  mock.timers.tick(200);
  q.set(1, [1, 2]);
  q.set(2, [7]);
  mock.timers.tick(399);
  assert.deepEqual(calls, []);
  assert.equal(q.state(), 'saving');
  mock.timers.tick(1);
  await drain();
  assert.deepEqual(calls, [[1, [1, 2]], [2, [7]]]);
  assert.equal(q.state(), 'saved');
});

test('flush sends pending immediately and awaits it', async () => {
  const calls: Call[] = [];
  let release!: () => void;
  const save = (qid: number, ids: number[]) => {
    calls.push([qid, ids]);
    return new Promise<void>((r) => (release = r));
  };
  const q = new SaveQueue(save);
  q.set(3, [9]);
  let done = false;
  const flushed = q.flush().then(() => (done = true));
  assert.deepEqual(calls, [[3, [9]]]); // no 400 ms wait
  await drain();
  assert.equal(done, false); // still waiting on the in-flight save
  release();
  await flushed;
  assert.equal(q.state(), 'saved');
  mock.timers.tick(1000);
  await drain();
  assert.equal(calls.length, 1); // the cancelled debounce never fires a second save
});

test('failed save stays pending, state error, retried', async () => {
  const { calls, save } = recorder(2);
  const q = new SaveQueue(save);
  const seen: string[] = [];
  q.onChange(() => seen.push(q.state()));
  q.set(1, [4]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'error');
  mock.timers.tick(999);
  await drain();
  assert.equal(calls.length, 1);
  mock.timers.tick(1); // first retry after 1 s, fails again
  await drain();
  assert.equal(calls.length, 2);
  assert.equal(q.state(), 'error');
  mock.timers.tick(1999);
  await drain();
  assert.equal(calls.length, 2);
  mock.timers.tick(1); // second retry after 2 s, succeeds
  await drain();
  assert.equal(calls.length, 3);
  assert.equal(q.state(), 'saved');
  assert.deepEqual(calls[2], [1, [4]]);
  assert.ok(seen.includes('error') && seen.at(-1) === 'saved');
});

test('backoff doubles and caps at 8 s', async () => {
  const { calls, save } = recorder(10);
  const q = new SaveQueue(save);
  q.set(1, [1]);
  mock.timers.tick(400);
  await drain();
  const gaps: number[] = [];
  for (const gap of [1000, 2000, 4000, 8000, 8000]) {
    const before = calls.length;
    mock.timers.tick(gap - 1);
    await drain();
    assert.equal(calls.length, before, `no retry before ${gap} ms`);
    mock.timers.tick(1);
    await drain();
    assert.equal(calls.length, before + 1, `retry at ${gap} ms`);
    gaps.push(gap);
  }
  assert.deepEqual(gaps, [1000, 2000, 4000, 8000, 8000]);
});

test('a newer set supersedes a pending retry', async () => {
  const { calls, save } = recorder(1);
  const q = new SaveQueue(save);
  q.set(1, [1]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'error');
  q.set(1, [2]);
  mock.timers.tick(400); // debounce of the new value, before the 1 s retry
  await drain();
  assert.deepEqual(calls, [[1, [1]], [1, [2]]]);
  assert.equal(q.state(), 'saved');
  mock.timers.tick(10_000);
  await drain();
  assert.equal(calls.length, 2); // the old retry was cancelled
});

test('flush after failure retries before resolving', async () => {
  const { calls, save } = recorder(1);
  const q = new SaveQueue(save);
  q.set(1, [4]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'error');
  await q.flush(); // retries now, without waiting out the backoff
  assert.deepEqual(calls, [[1, [4]], [1, [4]]]);
  assert.equal(q.state(), 'saved');
});

test('flush rejects when the immediate retry fails too', async () => {
  const { calls, save } = recorder(Infinity);
  const q = new SaveQueue(save);
  q.set(1, [4]);
  mock.timers.tick(400);
  await drain();
  await assert.rejects(q.flush(), /offline/);
  assert.equal(calls.length, 2);
  assert.equal(q.state(), 'error');
});

test('an expired session stops retrying and is reported', async () => {
  const { calls, save } = recorder(Infinity, new ApiError(401, 'session expired'));
  const q = new SaveQueue(save);
  q.set(1, [4]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'error');
  assert.ok(q.lastError instanceof ApiError && q.lastError.status === 401);
  mock.timers.tick(60_000);
  await drain();
  assert.equal(calls.length, 1); // no backoff retries
  await assert.rejects(q.flush(), /session expired/);
  assert.equal(calls.length, 1); // flush does not hammer an expired session either
});

test('flush with nothing pending resolves at once', async () => {
  const { calls, save } = recorder();
  const q = new SaveQueue(save);
  await q.flush();
  assert.equal(q.state(), 'idle');
  assert.deepEqual(calls, []);
});

for (const status of [409, 404, 422]) {
  test(`${status} is terminal: not retried, entry dropped, state error`, async () => {
    const { calls, save } = recorder(Infinity, new ApiError(status, `http ${status}`));
    const q = new SaveQueue(save);
    q.set(1, [4]);
    mock.timers.tick(400);
    await drain();
    assert.equal(q.state(), 'error');
    assert.ok(q.lastError instanceof ApiError && q.lastError.status === status);
    mock.timers.tick(60_000);
    await drain();
    assert.equal(calls.length, 1);
  });
}

test('5xx is retried with backoff', async () => {
  const { calls, save } = recorder(1, new ApiError(503, 'unavailable'));
  const q = new SaveQueue(save);
  q.set(1, [4]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'error');
  mock.timers.tick(1000);
  await drain();
  assert.equal(calls.length, 2);
  assert.equal(q.state(), 'saved');
});

test('flush with a terminal failure settles without sending it again', async () => {
  const { calls, save } = recorder(1, new ApiError(409, 'attempt finished'));
  const q = new SaveQueue(save);
  q.set(1, [4]);
  q.set(2, [5]);
  await q.flush(); // q1 fails terminally (dropped), q2 saves; flush resolves
  assert.deepEqual(calls, [[1, [4]], [2, [5]]]);
  assert.equal(q.state(), 'error');
  await q.flush(); // nothing left to send
  assert.equal(calls.length, 2);
});

test('a new answer clears that question\'s terminal failure', async () => {
  const { save } = recorder(1, new ApiError(422, 'option is not in this question'));
  const q = new SaveQueue(save);
  q.set(1, [99]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'error');
  q.set(1, [4]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'saved');
});
