import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatScore, percent } from './score.ts';

test('formatScore trims trailing zeros and caps at 2 decimals', () => {
  assert.equal(formatScore(4), '4');
  assert.equal(formatScore(2.5), '2.5');
  assert.equal(formatScore(1 / 3), '0.33');
  assert.equal(formatScore(2.499999), '2.5');
  assert.equal(formatScore(0), '0');
});

test('percent rounds and guards a zero maximum', () => {
  assert.equal(percent(2.5, 4), 63);
  assert.equal(percent(4, 4), 100);
  assert.equal(percent(0, 4), 0);
  assert.equal(percent(0, 0), 0);
});
