import assert from 'node:assert/strict';
import { test } from 'node:test';
import { cardFoot } from './cardFoot.ts';
import type { SetCard } from './types';

const card = (over: Partial<SetCard>): SetCard => ({
  id: 1,
  name: 'RAG · Basics',
  short_name: 'Basics',
  difficulty: null,
  style: 'standard',
  time_limit_minutes: 15,
  question_count: 3,
  last: null,
  open_attempt: null,
  ...over,
});

test('a partial last score is formatted, not printed raw', () => {
  const last = { attempt_id: 'a', status: 'submitted' as const, score: 2 / 3, max_score: 3 };
  assert.equal(cardFoot(card({ last }), 0), 'Last: 0.67 / 3');
});

test('whole scores stay whole', () => {
  const last = { attempt_id: 'a', status: 'expired' as const, score: 2, max_score: 4 };
  assert.equal(cardFoot(card({ last }), 0), 'Last: 2 / 4');
});

test('never attempted', () => {
  assert.equal(cardFoot(card({}), 0), 'Not attempted');
});

test('an open attempt shows resume and the time left', () => {
  assert.equal(cardFoot(card({ open_attempt: { attempt_id: 'a', deadline_at: 90_000 } }), 0), 'Resume · 01:30 left');
  assert.equal(cardFoot(card({ open_attempt: { attempt_id: 'a', deadline_at: null } }), 0), 'Resume');
});
