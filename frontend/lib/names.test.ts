import assert from 'node:assert/strict';
import test from 'node:test';

import { pluralize, subtopicGroupLabel } from './names.ts';

test('subtopicGroupLabel names the subtopic, or the whole course for the null group', () => {
  assert.equal(subtopicGroupLabel({ name: 'Linear algebra' }), 'Linear algebra');
  assert.equal(subtopicGroupLabel(null), 'Whole course');
});

test('pluralize', () => {
  assert.equal(pluralize(1, 'question'), '1 question');
  assert.equal(pluralize(2, 'question'), '2 questions');
  assert.equal(pluralize(0, 'question'), '0 questions');
});
