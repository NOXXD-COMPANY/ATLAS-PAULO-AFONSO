import type { Map } from 'maplibre-gl';

export const BUILDING_TILE_MAX_ZOOM = 17;

// A versão evita reutilizar tiles antigos com coordenadas incorretas.
export function buildingTileUrl(apiUrl: string, z: string | number, x: string | number, y: string | number) {
  return `${apiUrl}/api/tiles/${z}/${x}/${y}.pbf?v=4`;
}

/** Aquece só o anel vizinho, depois que a área visível terminou de carregar. */
export function prefetchNearbyTiles(map: Map, apiUrl: string) {
  let controller: AbortController | undefined;
  let previousTiles = '';

  const cancel = () => {
    controller?.abort();
    previousTiles = '';
  };
  const prefetch = () => {
    const visible = map.coveringTiles({ tileSize: 512, minzoom: 0, maxzoom: BUILDING_TILE_MAX_ZOOM });
    const key = visible.map(({ canonical: { z, x, y } }) => `${z}/${x}/${y}`).sort().join(',');
    if (key === previousTiles || !visible.length) return;
    cancel();
    previousTiles = key;
    controller = new AbortController();
    const { signal } = controller;
    const visibleKeys = new Set(key.split(','));
    const neighbors = new globalThis.Map<string, { z: number; x: number; y: number; distance: number }>();
    const center = map.getCenter();
    const latitude = center.lat * Math.PI / 180;
    for (const { canonical: { z, x, y } } of visible) {
      // Em zoom distante, um único vizinho pode conter a cidade inteira.
      // Nesse caso carregamos apenas o que realmente entra na tela.
      if (z < 14) continue;
      const scale = 2 ** z;
      const centerX = (center.lng + 180) / 360 * scale;
      const centerY = (1 - Math.asinh(Math.tan(latitude)) / Math.PI) / 2 * scale;
      for (let dx = -1; dx <= 1; dx++) {
        for (let dy = -1; dy <= 1; dy++) {
          const nx = x + dx;
          const ny = y + dy;
          const neighborKey = `${z}/${nx}/${ny}`;
          if (nx < 0 || ny < 0 || nx >= scale || ny >= scale || visibleKeys.has(neighborKey)) continue;
          neighbors.set(neighborKey, { z, x: nx, y: ny, distance: Math.hypot(nx + 0.5 - centerX, ny + 0.5 - centerY) });
        }
      }
    }
    // Limita rede e memória; esses blocos ficam no cache HTTP, sem desenhá-los.
    const queue = [...neighbors.values()].sort((a, b) => a.distance - b.distance).slice(0, 8);
    const worker = async () => {
      while (queue.length && !signal.aborted) {
        const tile = queue.shift()!;
        try {
          const response = await fetch(buildingTileUrl(apiUrl, tile.z, tile.x, tile.y), { signal });
          if (response.ok) await response.arrayBuffer();
        } catch {
          // Prefetch é opcional; pedidos visíveis têm seu próprio tratamento.
        }
      }
    };
    void Promise.all([worker(), worker()]);
  };

  map.on('movestart', cancel);
  map.on('idle', prefetch);
  return () => {
    cancel();
    map.off('movestart', cancel);
    map.off('idle', prefetch);
  };
}
