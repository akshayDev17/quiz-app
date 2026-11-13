import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatScore, isMarked, MARKING_RULE, maxMarks, percent, scoreLine, writeIntroRules, WRITTEN_RULE } from './score.ts';

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

test('scoreLine reads Not marked, never 0 / 0, when nothing in the attempt is marked', () => {
  assert.equal(scoreLine(0, 0), 'Not marked');
});

test('scoreLine says how many written answers still await the evaluator', () => {
  assert.equal(scoreLine(12, 20, 1), '12 / 20 · 1 awaiting');
  assert.equal(scoreLine(12, 20, 0), '12 / 20');
});

test('the intro of an all-subjective set drops the choice-only copy and gives the written rule', () => {
  const rules = writeIntroRules(2, 2);
  assert.deepEqual(rules, { questions: '2 questions, each answered in writing.', marking: WRITTEN_RULE });
  const text = rules.questions + rules.marking;
  assert.doesNotMatch(text, /more than one correct answer|−2|\+2|−1/);
  assert.match(text, /out of 4/);
  assert.match(text, /never less/);
});

test('the intro of a mixed set gives the choice rule, then the written rule', () => {
  assert.deepEqual(writeIntroRules(4, 1), {
    questions: '4 questions. Some have more than one correct answer.',
    marking: `${MARKING_RULE} ${WRITTEN_RULE}`,
  });
});

test('the intro of a choice-only set reads the marking rule alone', () => {
  assert.deepEqual(writeIntroRules(1, 0), {
    questions: '1 question. Some have more than one correct answer.',
    marking: MARKING_RULE,
  });
});
