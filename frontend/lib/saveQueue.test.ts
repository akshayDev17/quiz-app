import assert from 'node:assert/strict';
import { afterEach, beforeEach, mock, test } from 'node:test';

import { ApiError } from './api.ts';
import { SaveQueue, submitAfterTimeout, TIMEOUT_SAVE_BUDGET_MS, UnsavedAnswers } from './saveQueue.ts';

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

/** Advances fake time in small steps, letting promise handlers run between them. */
async function advance(ms: number, step = 100) {
  for (let t = 0; t < ms; t += step) {
    mock.timers.tick(Math.min(step, ms - t));
    await drain();
  }
}

test('a stalled save times out after 5 s, is aborted, and is retried', async () => {
  const signals: AbortSignal[] = [];
  const save = (_qid: number, _ids: number[], signal: AbortSignal) => {
    signals.push(signal);
    return new Promise<void>(() => {}); // never settles
  };
  const q = new SaveQueue(save);
  q.set(1, [4]);
  mock.timers.tick(400);
  await drain();
  assert.equal(q.state(), 'saving');
  await advance(4900);
  assert.equal(q.state(), 'saving');
  await advance(100);
  assert.equal(q.state(), 'error');
  assert.equal(signals[0].aborted, true);
  await advance(1000); // retryable: backoff resend
  assert.equal(signals.length, 2);
});

test('flush never hangs on a stalled save', async () => {
  const save = () => new Promise<void>(() => {});
  const q = new SaveQueue(save);
  q.set(1, [4]);
  let outcome: unknown = 'pending';
  q.flush().then(() => (outcome = 'resolved'), (err) => (outcome = err));
  await advance(4900);
  assert.equal(outcome, 'pending');
  await advance(100); // flush's own send times out: it rejects rather than waiting forever
  assert.ok(outcome instanceof Error && /timed out/.test(outcome.message));
});

test('5xx at the buzzer, success within the budget: answer sent before submit', async () => {
  const { calls, save } = recorder(2, new ApiError(503, 'unavailable'));
  const q = new SaveQueue(save);
  q.set(1, [4]);
  const order: string[] = [];
  const done = submitAfterTimeout(q, async () => {
    order.push(`submit after ${calls.length} saves`);
    return 'a1';
  });
  await advance(3500); // fail now, fail at +1 s, succeed at +3 s
  const result = await done;
  assert.deepEqual(result, { attemptId: 'a1', unsaved: [] });
  assert.equal(calls.length, 3);
  assert.deepEqual(order, ['submit after 3 saves']);
  assert.equal(q.state(), 'saved');
});

test('persistent failure at the buzzer: submit proceeds within the budget, unsaved reported', async () => {
  const { save } = recorder(Infinity, new ApiError(502, 'bad gateway'));
  const q = new SaveQueue(save);
  q.set(1, [4]);
  q.set(2, [5]);
  let submitted = false;
  let result: unknown = null;
  submitAfterTimeout(q, async () => {
    submitted = true;
    return 'a1';
  }).then((r) => (result = r));
  await advance(TIMEOUT_SAVE_BUDGET_MS - 100);
  assert.equal(submitted, false); // still trying inside the budget
  await advance(200);
  assert.equal(submitted, true);
  assert.deepEqual(result, { attemptId: 'a1', unsaved: [1, 2] });
});

test('flush with a budget rejects with the unsaved questions', async () => {
  const { save } = recorder(Infinity);
  const q = new SaveQueue(save);
  q.set(7, [1]);
  const p = q.flush(3000);
  const check = assert.rejects(p, (err) => err instanceof UnsavedAnswers && err.questionIds.join() === '7');
  await advance(3000);
  await check;
});

test('an expired session at the buzzer is not swallowed', async () => {
  const { save } = recorder(Infinity, new ApiError(401, 'session expired'));
  const q = new SaveQueue(save);
  q.set(1, [4]);
  let submitted = false;
  const p = submitAfterTimeout(q, async () => {
    submitted = true;
    return 'a1';
  });
  const check = assert.rejects(p, /session expired/);
  await advance(500);
  await check;
  assert.equal(submitted, false);
});

test('flushKeepalive sends pending values at once, marked keepalive', async () => {
  const sent: [number, number[], boolean][] = [];
  const save = async (qid: number, ids: number[], _signal: AbortSignal, keepalive = false) => {
    sent.push([qid, ids, keepalive]);
  };
  const q = new SaveQueue(save);
  q.set(1, [4]);
  q.set(2, [5, 6]);
  q.flushKeepalive(); // no debounce wait
  assert.deepEqual(sent, [[1, [4], true], [2, [5, 6], true]]);
  await drain();
  assert.equal(q.state(), 'saved');
  mock.timers.tick(400);
  await drain();
  assert.equal(sent.length, 2); // the debounce timers were cancelled
});

test('a keepalive save is never aborted, yet the queue still times it out and retries', async () => {
  const calls: { signal: AbortSignal; keepalive: boolean }[] = [];
  const save = (_qid: number, _ids: number[], signal: AbortSignal, keepalive = false) => {
    calls.push({ signal, keepalive });
    return new Promise<void>(() => {}); // never settles
  };
  const q = new SaveQueue(save);
  q.set(1, [4]);
  q.flushKeepalive();
  await advance(5000);
  assert.equal(q.state(), 'error');
  assert.equal(calls[0].keepalive, true);
  assert.equal(calls[0].signal.aborted, false); // the request outlives the page; only the queue gives up
  await advance(1000); // backoff resend is an ordinary save
  assert.equal(calls.length, 2);
  assert.equal(calls[1].keepalive, false);
});

test('flushKeepalive leaves a save already in flight alone', async () => {
  const sent: boolean[] = [];
  const save = (_qid: number, _ids: number[], _signal: AbortSignal, keepalive = false) => {
    sent.push(keepalive);
    return new Promise<void>(() => {});
  };
  const q = new SaveQueue(save);
  q.set(1, [4]);
  mock.timers.tick(400);
  q.flushKeepalive();
  assert.deepEqual(sent, [false]);
});
