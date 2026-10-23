import assert from 'node:assert/strict';
import test from 'node:test';

import { letter } from './letters.ts';

test('letters', () =>
  assert.deepEqual(
    [0, 4, 25, 26, 27, 51, 52, 701, 702].map(letter),
    ['A', 'E', 'Z', 'AA', 'AB', 'AZ', 'BA', 'ZZ', 'AAA'],
  ));
