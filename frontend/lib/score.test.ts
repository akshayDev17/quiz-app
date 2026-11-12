import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatScore, isMarked, maxMarks, percent, scoreLine } from './score.ts';

test('formatScore trims trailing zeros and caps at 2 decimals', () => {
  assert.equal(formatScore(4), '4');
  assert.equal(formatScore(2.5), '2.5');
  assert.equal(formatScore(1 / 3), '0.33');
  assert.equal(formatScore(2.499999), '2.5');
  assert.equal(formatScore(0), '0');
});

test('formatScore writes a negative score with a true minus sign', () => {
  assert.equal(formatScore(-3), '−3');
  assert.equal(formatScore(-0.5), '−0.5');
  assert.equal(formatScore(-0.001), '0'); // rounds to zero: no "−0"
});

test('maxMarks is +2 per correct option', () => {
  assert.equal(maxMarks(1), 2);
  assert.equal(maxMarks(3), 6);
});

test('percent rounds a marked attempt to a whole percent', () => {
  assert.equal(percent(2.5, 4), 63);
  assert.equal(percent(4, 4), 100);
  assert.equal(percent(0, 4), 0);
  assert.equal(percent(-3, 12), -25);
  assert.equal(percent(-12, 12), -100);
});

test('an attempt is marked only when its set has something to score', () => {
  assert.equal(isMarked(4), true);
  assert.equal(isMarked(2), true);
  assert.equal(isMarked(0), false); // every question subjective
});

test('scoreLine reads score / max_score for a marked attempt, below zero too', () => {
  assert.equal(scoreLine(9.5, 12), '9.5 / 12');
  assert.equal(scoreLine(-13.5, 24), '−13.5 / 24');
  assert.equal(scoreLine(0, 4), '0 / 4');
});

test('scoreLine reads Not marked, never 0 / 0, when nothing in the set is marked', () => {
  assert.equal(scoreLine(0, 0), 'Not marked');
});
