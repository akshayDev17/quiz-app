import assert from 'node:assert/strict';
import test from 'node:test';

import { clockOffset, formatClock, remainingSeconds, timerTone } from './countdown.ts';

test('remaining recomputed from deadline — sleep/throttle safe', () => {
  const off = clockOffset(1_000_000, 999_000); // client 1 s behind
  assert.equal(remainingSeconds(1_060_000, off, 999_000), 60);
  assert.equal(remainingSeconds(1_060_000, off, 999_000 + 45 * 60_000), 0); // woke long after: 0, not negative
});

test('tones', () =>
  assert.deepEqual(
    [301, 300, 299, 60, 59, 0].map(timerTone),
    ['normal', 'normal', 'amber', 'amber', 'red', 'red'],
  ));

test('format', () =>
  assert.deepEqual([0, 59, 900, 3600].map(formatClock), ['00:00', '00:59', '15:00', '1:00:00']));
