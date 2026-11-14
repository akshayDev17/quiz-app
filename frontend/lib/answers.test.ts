import assert from 'node:assert/strict';
import { test } from 'node:test';

import { blanks, countUnanswered, isAnswered, isTypingTarget, textCounter, textLimit } from './answers.ts';
import { MAX_TEXT_ANSWER } from './types.ts';

const choice = (id: number) => ({ id, kind: 'choice' as const });
const written = (id: number) => ({ id, kind: 'subjective' as const });

test('a choice question is answered once an option is ticked', () => {
  assert.equal(isAnswered(choice(1), {}, {}), false);
  assert.equal(isAnswered(choice(1), { 1: [] }, {}), false);
  assert.equal(isAnswered(choice(1), { 1: [4] }, {}), true);
  // text never answers a choice question
  assert.equal(isAnswered(choice(1), {}, { 1: 'words' }), false);
});

test('a subjective question is answered once its text is more than whitespace', () => {
  assert.equal(isAnswered(written(2), {}, {}), false);
  assert.equal(isAnswered(written(2), {}, { 2: '' }), false);
  assert.equal(isAnswered(written(2), {}, { 2: '  \n\t ' }), false);
  assert.equal(isAnswered(written(2), {}, { 2: ' x ' }), true);
  // ticks never answer a subjective question
  assert.equal(isAnswered(written(2), { 2: [1] }, {}), false);
});

test('a blank subjective question is never counted as unanswered', () => {
  const questions = [choice(10), written(11), choice(12), written(13), choice(14)];
  const got = blanks(questions, { 10: [1], 14: [] }, { 11: '   ', 13: 'An answer' });
  assert.deepEqual(got, { unanswered: ['Q3', 'Q5'], blankWritten: ['Q2'] });
});

test('nothing blank, nothing listed', () => {
  assert.deepEqual(blanks([choice(1), written(2)], { 1: [3] }, { 2: 'Done' }), { unanswered: [], blankWritten: [] });
});

test('the results header counts every blank question, written ones included', () => {
  const picked = (...selected: boolean[]) => ({ kind: 'choice' as const, options: selected.map((s) => ({ selected: s })) });
  const typed = (text_answer: string | null) => ({ kind: 'subjective' as const, text_answer });
  // the reproduced attempt: choice Q1, Q3, Q5 answered, written Q2 and Q4 left blank
  assert.equal(countUnanswered([picked(true, false), typed(null), picked(true, false), typed(null), picked(true)]), 2);
  assert.equal(countUnanswered([picked(false, false), typed(null), typed('An answer'), picked(false, true)]), 2);
  // whitespace is blank, as the server stores it
  assert.equal(countUnanswered([typed('  \n ')]), 1);
  assert.equal(countUnanswered([picked(true), typed('Done')]), 0);
  assert.equal(countUnanswered([]), 0);
});

test('shortcuts stand down where the solver types, not on an option checkbox', () => {
  assert.equal(isTypingTarget({ tagName: 'TEXTAREA' } as unknown as EventTarget), true);
  assert.equal(isTypingTarget({ tagName: 'SELECT' } as unknown as EventTarget), true);
  assert.equal(isTypingTarget({ tagName: 'INPUT', type: 'text' } as unknown as EventTarget), true);
  assert.equal(isTypingTarget({ tagName: 'INPUT', type: 'search' } as unknown as EventTarget), true);
  assert.equal(isTypingTarget({ tagName: 'DIV', isContentEditable: true } as unknown as EventTarget), true);

  assert.equal(isTypingTarget({ tagName: 'INPUT', type: 'checkbox' } as unknown as EventTarget), false);
  assert.equal(isTypingTarget({ tagName: 'INPUT', type: 'radio' } as unknown as EventTarget), false);
  assert.equal(isTypingTarget({ tagName: 'BUTTON' } as unknown as EventTarget), false);
  assert.equal(isTypingTarget({ tagName: 'BODY', isContentEditable: false } as unknown as EventTarget), false);
  assert.equal(isTypingTarget(null), false);
});

test('a written question is limited to what the server says, 10,000 when it says nothing', () => {
  assert.equal(textLimit({ max_text_length: 820 }), 820);
  assert.equal(textLimit({ max_text_length: 300 }), 300);
  assert.equal(textLimit({ max_text_length: null }), MAX_TEXT_ANSWER);
  assert.equal(textLimit({} as { max_text_length: number | null }), MAX_TEXT_ANSWER);
});

test('the counter always shows how much of the question\'s limit is used', () => {
  assert.deepEqual(textCounter(0, 820), { text: '0 / 820 characters', over: false });
  assert.deepEqual(textCounter(820, 820), { text: '820 / 820 characters', over: false });
  assert.deepEqual(textCounter(9_512, 10_000), { text: '9,512 / 10,000 characters', over: false });
});

test('an answer saved before its limit may be longer: kept, but a change must fit', () => {
  assert.deepEqual(textCounter(2_280, 820), { text: '2,280 / 820 characters · shorten it to save a change', over: true });
});
