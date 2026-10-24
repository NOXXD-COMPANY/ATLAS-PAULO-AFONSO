import assert from 'node:assert/strict';
import { test } from 'node:test';
import { alturaDoPredio } from '../src/constants.ts';

test('height comes from floors when known, otherwise a typical height for the use', () => {
  assert.deepEqual(alturaDoPredio('comercial', 4), { metros: 12, estimada: false });
  assert.deepEqual(alturaDoPredio('residencial', 0), { metros: 4, estimada: true });
  assert.deepEqual(alturaDoPredio('religioso', null), { metros: 9, estimada: true });
  assert.deepEqual(alturaDoPredio('tipo-novo', undefined), { metros: 4, estimada: true });
});
