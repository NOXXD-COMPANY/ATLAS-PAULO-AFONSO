import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  buildingTileUrl,
  countFootprints,
  countOverviewCells,
  DOT_MIN_ZOOM,
  dotRadiusExpression,
  fadeRamp,
  FOOTPRINT_MAX_ZOOM,
  FOOTPRINT_MIN_ZOOM,
  legendSource,
  navigableBounds,
  OVERVIEW_LEVELS,
  overviewColorExpression,
  overviewCountExpression,
  overviewUrl,
} from '../src/mapTiles.ts';

test('tile and overview URLs carry the data version so a reimport busts the browser cache', () => {
  assert.equal(
    buildingTileUrl('http://localhost:8000', '1792107942'),
    'http://localhost:8000/api/tiles/{z}/{x}/{y}.pbf?v=1792107942',
  );
  assert.equal(
    overviewUrl('http://localhost:8000', 'a b', 2),
    'http://localhost:8000/api/map/overview?level=2&v=a%20b',
  );
});

test('footprints never come from the zooms where one tile holds the whole city', () => {
  assert.ok(FOOTPRINT_MIN_ZOOM >= 14);
  assert.ok(FOOTPRINT_MAX_ZOOM >= FOOTPRINT_MIN_ZOOM);
});

test('grid levels hand over one zoom level at a time, ending at the building dots', () => {
  assert.equal(OVERVIEW_LEVELS[0].enter, null);
  OVERVIEW_LEVELS.forEach((level, i) => {
    assert.equal(level.level, i);
    if (i > 0) assert.equal(level.enter, OVERVIEW_LEVELS[i - 1].exit);
    if (level.enter !== null) assert.equal(level.exit - level.enter, 1);
  });
  assert.equal(OVERVIEW_LEVELS.at(-1).exit, DOT_MIN_ZOOM);
  assert.ok(DOT_MIN_ZOOM < FOOTPRINT_MIN_ZOOM);
});

test('a new layer is fully in before the previous one starts fading out', () => {
  const [, , , ...stops] = fadeRamp(12, 13, 0.8);
  assert.deepEqual(stops, [12, 0, 12.3, 0.8, 13.3, 0.8, 13.7, 0]);
  const incomingFull = fadeRamp(13, null, 1)[5];
  const outgoingStart = fadeRamp(null, 12, 1)[3];
  assert.ok(incomingFull - 13 <= outgoingStart - 12);
});

test('legend counts the layer that dominates the screen', () => {
  assert.equal(legendSource(10), 0);
  assert.equal(legendSource(11.2), 0);
  assert.equal(legendSource(11.6), 1);
  assert.equal(legendSource(12.4), 1);
  assert.equal(legendSource(12.6), 'dots');
  assert.equal(legendSource(14.4), 'dots');
  assert.equal(legendSource(14.5), 'footprints');
});

test('a dot has the area of its building, so at zoom 14 it matches the polygon', () => {
  const [, , , z0, , z1] = dotRadiusExpression();
  assert.equal(z0, DOT_MIN_ZOOM);
  assert.equal(z1, FOOTPRINT_MIN_ZOOM + 1);
  // 314 m² → raio de 10 m; no zoom 15 um pixel tem ~2,36 m.
  const radiusAt15 = 10 * 2 ** 15 / ((2 * Math.PI * 6378137 * Math.cos(9.4 * Math.PI / 180)) / 512);
  assert.ok(Math.abs(radiusAt15 - 4.24) < 0.05);
});

test('navigable bounds add a margin around the data', () => {
  assert.deepEqual(navigableBounds([0, 0, 4, 2], 0.25), [[-1, -0.5], [5, 2.5]]);
});

test('footprint legend counts each building once even when split across tiles', () => {
  const { counts, total } = countFootprints([
    { properties: { geometry_key: 'a', tipo: 'residencial' } },
    { properties: { geometry_key: 'a', tipo: 'residencial' } },
    { properties: { geometry_key: 'b', tipo: 'comercial' } },
    { properties: { id: 'c' } },
    // O mesmo prédio como ponto (sem geometry_key) e como polígono.
    { properties: { id: 'd', tipo: 'servico' } },
    { properties: { id: 'd', geometry_key: 'dd', tipo: 'servico' } },
  ]);
  assert.equal(total, 4);
  assert.deepEqual(counts, { residencial: 1, comercial: 1, desconhecido: 1, servico: 1 });
});

test('overview legend sums cells once and leaves out addresses when they are hidden', () => {
  const cells = [
    { properties: { id: '1:1', b_residencial: 3, p_residencial: 2, p_comercial: 1 } },
    { properties: { id: '1:1', b_residencial: 3, p_residencial: 2, p_comercial: 1 } },
    { properties: { id: '1:2', b_servico: 4 } },
  ];
  assert.deepEqual(countOverviewCells(cells, true), {
    counts: { residencial: 5, comercial: 1, servico: 4 },
    total: 10,
  });
  assert.deepEqual(countOverviewCells(cells, false), {
    counts: { residencial: 3, servico: 4 },
    total: 7,
  });
  assert.deepEqual(overviewCountExpression(false), ['get', 'n_b']);
});

test('with some uses hidden, grid cells count and color only the visible ones', () => {
  const colors = { residencial: 'blue', comercial: 'red', desconhecido: 'grey' };
  const count = overviewCountExpression(false, ['residencial', 'comercial']);
  assert.deepEqual(count, ['+', 0, ['coalesce', ['get', 'b_residencial'], 0], ['coalesce', ['get', 'b_comercial'], 0]]);
  const color = overviewColorExpression(false, ['residencial', 'comercial'], colors);
  assert.equal(color[0], 'let');
  assert.equal(color[3][0], 'case');
  assert.equal(color[3].at(-1), 'grey');
  assert.equal(overviewColorExpression(true, ['desconhecido'], colors), 'grey');
  // Com todos visíveis, usa o predominante calculado pelo servidor.
  const all = overviewColorExpression(true, ['residencial', 'comercial', 'servico', 'religioso', 'institucional', 'hospedagem', 'agropecuario', 'desconhecido'], colors);
  assert.deepEqual(all.slice(0, 2), ['match', ['get', 'tipo']]);
});
