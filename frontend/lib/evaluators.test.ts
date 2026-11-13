import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dollars, evaluatorLabel, moved, presetFor, spentDollars } from './evaluators.ts';

test('an evaluator reads Provider · Model ($X.XX left)', () => {
  assert.equal(
    evaluatorLabel({ provider_label: 'Anthropic API', model: 'claude-haiku-5-5', remaining_usd: 4.9998 }),
    'Anthropic API · claude-haiku-5-5 ($4.99 left)',
  );
  assert.equal(evaluatorLabel({ provider_label: 'Amazon Bedrock', model: 'anthropic.claude-haiku-5-5', remaining_usd: 0 }),
    'Amazon Bedrock · anthropic.claude-haiku-5-5 ($0.00 left)');
});

test('what is left rounds down and what is spent rounds up, to the cent', () => {
  assert.equal(dollars(5), '$5.00');
  assert.equal(dollars(0.019), '$0.01');
  assert.equal(dollars(2.29), '$2.29');
  assert.equal(spentDollars(0.0002), '$0.01');
  assert.equal(spentDollars(0), '$0.00');
  assert.equal(spentDollars(1.2), '$1.20');
});

test('a preset is found by provider and exact model id', () => {
  const presets = [
    { provider: 'anthropic', model: 'claude-haiku-5-5', input_price_per_mtok: 0.1, output_price_per_mtok: 0.5, source: 's' },
    { provider: 'bedrock', model: 'anthropic.claude-haiku-5-5', input_price_per_mtok: 0.1, output_price_per_mtok: 0.5, source: 's' },
  ];
  assert.equal(presetFor(presets, 'anthropic', ' claude-haiku-5-5 ')?.provider, 'anthropic');
  assert.equal(presetFor(presets, 'bedrock', 'claude-haiku-5-5'), undefined);
});

test('an entry moves one place, and never off either end', () => {
  assert.deepEqual(moved([1, 2, 3], 1, -1), [2, 1, 3]);
  assert.deepEqual(moved([1, 2, 3], 1, 1), [1, 3, 2]);
  assert.deepEqual(moved([1, 2, 3], 0, -1), [1, 2, 3]);
  assert.deepEqual(moved([1, 2, 3], 2, 1), [1, 2, 3]);
});
