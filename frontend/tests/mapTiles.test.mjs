import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers/promises';
import { test } from 'node:test';
import { prefetchNearbyTiles } from '../src/mapTiles.ts';

function fakeMap() {
  const listeners = new Map();
  return {
    coveringTiles: () => [{ canonical: { z: 17, x: 51619, y: 68974 } }],
    getCenter: () => ({ lng: -38.223898, lat: -9.402317 }),
    on(event, listener) { listeners.set(event, listener); },
    off(event) { listeners.delete(event); },
    emit(event) { listeners.get(event)?.(); },
  };
}

test('prefetch waits for visible tiles, fetches only eight adjacent blocks and avoids repeats', async (t) => {
  const requests = [];
  t.mock.method(globalThis, 'fetch', async (url) => {
    requests.push(url);
    return { ok: true, arrayBuffer: async () => new ArrayBuffer(0) };
  });
  const map = fakeMap();
  const stop = prefetchNearbyTiles(map, 'http://localhost:8000');
  assert.equal(requests.length, 0);
  map.emit('idle');
  await setImmediate();
  assert.equal(requests.length, 8);
  assert.equal(new Set(requests).size, 8);
  for (const url of requests) {
    const [, x, y] = url.match(/\/17\/(\d+)\/(\d+)\.pbf/);
    assert.ok(Math.abs(Number(x) - 51619) <= 1);
    assert.ok(Math.abs(Number(y) - 68974) <= 1);
    assert.notEqual(`${x}/${y}`, '51619/68974');
  }
  map.emit('idle');
  await setImmediate();
  assert.equal(requests.length, 8);
  stop();
});

test('prefetch limits concurrency to two and aborts when navigation starts', async (t) => {
  const signals = [];
  t.mock.method(globalThis, 'fetch', (_url, { signal }) => {
    signals.push(signal);
    return new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true });
    });
  });
  const map = fakeMap();
  const stop = prefetchNearbyTiles(map, 'http://localhost:8000');
  map.emit('idle');
  assert.equal(signals.length, 2);
  map.emit('movestart');
  await setImmediate();
  assert.ok(signals.every((signal) => signal.aborted));
  assert.equal(signals.length, 2);
  map.emit('idle');
  assert.equal(signals.length, 4);
  stop();
  assert.ok(signals.every((signal) => signal.aborted));
  map.emit('idle');
  assert.equal(signals.length, 4);
});

test('zooming out does not prefetch large offscreen city blocks', async (t) => {
  const fetch = t.mock.method(globalThis, 'fetch', async () => ({ ok: true }));
  const map = fakeMap();
  map.coveringTiles = () => [{ canonical: { z: 9, x: 201, y: 269 } }];
  const stop = prefetchNearbyTiles(map, 'http://localhost:8000');
  map.emit('idle');
  await setImmediate();
  assert.equal(fetch.mock.callCount(), 0);
  stop();
});
