import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatArea, titleCase } from '../src/format.ts';

test('CNEFE uppercase text becomes title case, keeping acronyms and roman numerals', () => {
  assert.equal(titleCase('RUA SAO LUCAS, 190 B'), 'Rua Sao Lucas, 190 B');
  assert.equal(titleCase('RUA MARECHAL FLORIANO PEIXOTO, 481 SMS 16'), 'Rua Marechal Floriano Peixoto, 481 SMS 16');
  assert.equal(titleCase('BTN 3'), 'BTN 3');
  assert.equal(titleCase('CONJUNTO HABITACIONAL II'), 'Conjunto Habitacional II');
  assert.equal(titleCase('ALTO DA BURRA'), 'Alto da Burra');
  assert.equal(titleCase('DE OLHO NA CASA'), 'De Olho na Casa');
  assert.equal(titleCase(null), '');
});

test('areas switch to hectares when large and hide empty values', () => {
  assert.equal(formatArea(111.4), '111 m²');
  assert.equal(formatArea(25000), '2,5 ha');
  assert.equal(formatArea(0), null);
  assert.equal(formatArea(null), null);
});
