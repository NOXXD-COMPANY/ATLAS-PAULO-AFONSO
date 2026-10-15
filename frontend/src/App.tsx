import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type {
  Map as MapLibreMap,
  MapLayerMouseEvent,
  StyleSpecification,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { GeoJsonLayer } from '@deck.gl/layers';
import { TIPOS_ORDEM, corDoTipo, FONTE_PONTO } from './constants';
const Report = lazy(() => import('./Report'));

interface BuildingProps {
  id: string;
  area_m2: number | null;
  tipo: string;
  endereco: string | null;
  bairro: string | null;
  estabelecimento: string | null;
  num_pavimentos: number | null;
  fonte: string | null;
}

type GeoJsonFeature = {
  type: 'Feature';
  id?: string | number;
  geometry: { type: string; coordinates: any };
  properties: BuildingProps | Record<string, unknown>;
};

export type GeoJsonFC = { type: 'FeatureCollection'; features: GeoJsonFeature[] };

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

// Altura ilustrativa (m) quando o número de pavimentos é desconhecido.
// Prédios com `num_pavimentos` usam pavimentos × 3 m (dado real do Overture).
const ALTURA_PADRAO_M = 5;

const PAGE_SIZE = 1000;
const CENTRO = [-38.223898, -9.402317] as [number, number];
const ZOOM_INICIAL = 17.5;
const ZOOM_3D = 16.5;
const RAIO_3D_M = 450;

// Mapa base: OpenStreetMap (tiles públicos, sem chave de API).
const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
      maxzoom: 19,
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
};

async function fetchJson(url: string, attempts = 3): Promise<any> {
  let lastErr: unknown = null;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      lastErr = err;
      if (attempt < attempts) await new Promise((r) => setTimeout(r, 1500));
    }
  }
  throw lastErr;
}

type Bounds = { west: number; south: number; east: number; north: number };
function containsBounds(outer: Bounds, inner: Bounds) {
  return outer.west <= inner.west && outer.south <= inner.south &&
    outer.east >= inner.east && outer.north >= inner.north;
}

function geometryHash(type: string, coordinates: unknown): string {
  const value = `${type}:${JSON.stringify(coordinates)}`;
  let hash = 2166136261;
  for (let i = 0; i < value.length; i++) hash = Math.imul(hash ^ value.charCodeAt(i), 16777619);
  return String(hash >>> 0);
}

function sameCoordinates(a: any, b: any): boolean {
  if (a === b) return true;
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
  return a.every((value, index) => sameCoordinates(value, b[index]));
}

function geometryCenter(geometry: GeoJsonFeature['geometry']): [number, number] {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  const visit = (value: any) => {
    if (!Array.isArray(value)) return;
    if (typeof value[0] === 'number' && typeof value[1] === 'number') {
      minLon = Math.min(minLon, value[0]);
      maxLon = Math.max(maxLon, value[0]);
      minLat = Math.min(minLat, value[1]);
      maxLat = Math.max(maxLat, value[1]);
      return;
    }
    for (const child of value) visit(child);
  };
  visit(geometry.coordinates);
  return [(minLon + maxLon) / 2, (minLat + maxLat) / 2];
}

function distanciaMetros(a: [number, number], b: [number, number]): number {
  const lat = ((a[1] + b[1]) / 2) * (Math.PI / 180);
  const x = (a[0] - b[0]) * 111320 * Math.cos(lat);
  const y = (a[1] - b[1]) * 110540;
  return Math.hypot(x, y);
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  const [data, setData] = useState<GeoJsonFC>({ type: 'FeatureCollection', features: [] });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadedCount, setLoadedCount] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<{ id: string; feature: GeoJsonFeature } | null>(null);
  const [showPontos, setShowPontos] = useState(true);
  const [modoPontos, setModoPontos] = useState<'todos' | 'no-selecionado'>(
    'todos',
  );
  const [showReport, setShowReport] = useState(false);
  const [camera, setCamera] = useState({ center: CENTRO, zoom: ZOOM_INICIAL });
  const featuresById = useRef(new Map<string, GeoJsonFeature>());
  const geometryKeyById = useRef(new Map<string, string>());
  const geometryCenterByKey = useRef(new Map<string, [number, number]>());
  const geometryGroups = useRef(new Map<string, { key: string; geometry: GeoJsonFeature['geometry']; center: [number, number] }[]>());
  const nextGeometryKey = useRef(0);
  const loadedRegions = useRef<Bounds[]>([]);
  const loadingRegion = useRef(false);
  const pendingRegion = useRef(false);
  const firstRegionLoaded = useRef(false);

  useEffect(() => {
    if (!mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: OSM_STYLE,
      center: CENTRO,
      zoom: ZOOM_INICIAL,
      maxPitch: 85,
    });
    // O 3D é 100% dos nossos dados (camada deck.gl abaixo): cada volume
    // extrusado É a feature (polígono ou bolinha), logo carrega sempre o
    // endereço e a cor do tipo. Sem camada 3D externa.
    const overlay = new MapboxOverlay({
      layers: [],
    });
    map.addControl(overlay);
    overlayRef.current = overlay;
    mapRef.current = map;

    const onClick = (e: MapLayerMouseEvent) => {
      const info = overlay.pickObject({ x: e.point.x, y: e.point.y });
      const feature = info?.object as GeoJsonFeature | undefined;
      const id = feature?.id ?? (feature?.properties as BuildingProps | undefined)?.id;
      setSelectedId(id == null ? null : String(id));
    };
    map.on('click', onClick);
    const syncCamera = () => {
      const center = map.getCenter();
      setCamera({ center: [center.lng, center.lat], zoom: map.getZoom() });
    };
    map.on('moveend', syncCamera);
    map.on('load', syncCamera);

    return () => {
      map.off('click', onClick);
      map.off('moveend', syncCamera);
      map.off('load', syncCamera);
      map.remove();
      overlayRef.current = null;
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const map = mapRef.current;
    if (!map) return;

    const loadVisibleRegion = async () => {
      if (loadingRegion.current) {
        pendingRegion.current = true;
        return;
      }
      const bounds = map.getBounds();
      const region: Bounds = {
        west: Math.max(-180, bounds.getWest()),
        south: Math.max(-90, bounds.getSouth()),
        east: Math.min(180, bounds.getEast()),
        north: Math.min(90, bounds.getNorth()),
      };
      if (loadedRegions.current.some((loaded) => containsBounds(loaded, region))) return;

      loadingRegion.current = true;
      setLoadingMore(true);
      setError(null);
      const wasFirstRegion = !firstRegionLoaded.current;
      const pageSize = map.getZoom() < 13 ? 5000 : PAGE_SIZE;
      try {
        let afterId: string | null = null;
        for (;;) {
          const params = new URLSearchParams({
            bbox: `${region.west},${region.south},${region.east},${region.north}`,
            em_cobertura: 'true', light: 'true', limit: String(pageSize),
          });
          if (afterId) params.set('after_id', afterId);
          const fc = await fetchJson(`${API_URL}/api/buildings?${params}`, firstRegionLoaded.current ? 3 : 5) as GeoJsonFC;
          if (!fc || !Array.isArray(fc.features)) throw new Error('resposta inválida da API');
          if (cancelled) return;

          const added: GeoJsonFeature[] = [];
          for (const feature of fc.features) {
            const id = String(feature.id ?? feature.properties['id'] ?? '');
            if (!id) continue;
            afterId = id;
            if (featuresById.current.has(id)) continue;
            feature.id = id;
            featuresById.current.set(id, feature);
            const hash = geometryHash(feature.geometry.type, feature.geometry.coordinates);
            const candidates = geometryGroups.current.get(hash) ?? [];
            let group = candidates.find((candidate) => candidate.geometry.type === feature.geometry.type && sameCoordinates(candidate.geometry.coordinates, feature.geometry.coordinates));
            if (!group) {
              group = {
                key: `g${nextGeometryKey.current++}`,
                geometry: feature.geometry,
                center: geometryCenter(feature.geometry),
              };
              candidates.push(group);
              geometryGroups.current.set(hash, candidates);
              geometryCenterByKey.current.set(group.key, group.center);
            } else {
              feature.geometry = group.geometry;
            }
            geometryKeyById.current.set(id, group.key);
            added.push(feature);
          }
          if (added.length) {
            setData((current) => ({ type: 'FeatureCollection', features: current.features.concat(added) }));
            setLoadedCount(featuresById.current.size);
          }
          if (fc.features.length < pageSize) break;
        }
        loadedRegions.current.push(region);
        firstRegionLoaded.current = true;
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
      } finally {
        loadingRegion.current = false;
        setLoadingMore(false);
        if (!cancelled && wasFirstRegion) setLoading(false);
        if (!cancelled && pendingRegion.current) {
          pendingRegion.current = false;
          void loadVisibleRegion();
        }
      }
    };

    map.on('load', loadVisibleRegion);
    map.on('moveend', loadVisibleRegion);
    if (map.loaded()) void loadVisibleRegion();
    return () => {
      cancelled = true;
      map.off('load', loadVisibleRegion);
      map.off('moveend', loadVisibleRegion);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!selectedId) return;
    fetchJson(`${API_URL}/api/buildings/${encodeURIComponent(selectedId)}`)
      .then((feature: GeoJsonFeature) => { if (!cancelled) setSelectedDetail({ id: selectedId, feature }); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : 'Erro ao carregar detalhes'); });
    return () => { cancelled = true; };
  }, [selectedId]);

  const selectedFeature: GeoJsonFeature | null = (() => {
    if (!selectedId) return null;
    return (selectedDetail?.id === selectedId ? selectedDetail.feature : null) ?? featuresById.current.get(selectedId) ?? null;
  })();

  const selectedGeomKey = selectedFeature
    ? geometryKeyById.current.get(String(selectedFeature.id ?? selectedId)) ?? null
    : null;

  const visibleData = useMemo<GeoJsonFC | null>(() => {
    if (!data) return null;
    if (modoPontos === 'todos') {
      if (showPontos) return data;
      return {
        type: 'FeatureCollection',
        features: data.features.filter(
          (f) => f.properties['fonte'] !== FONTE_PONTO,
        ),
      };
    }
    // 'no-selecionado': isola o prédio clicado e seus endereços
    // (as linhas que repetem a mesma geometria). Sem seleção, vazio.
    if (selectedGeomKey == null)
      return { type: 'FeatureCollection', features: [] };
    return {
      type: 'FeatureCollection',
      features: data.features.filter((f) => geometryKeyById.current.get(String(f.id)) === selectedGeomKey),
    };
  }, [data, showPontos, modoPontos, selectedGeomKey]);

  const mapData = useMemo<GeoJsonFC | null>(() => {
    if (!visibleData) return null;
    const seen = new Set<string>();
    return {
      type: 'FeatureCollection',
      features: visibleData.features.filter((feature) => {
        if (feature.properties['fonte'] === FONTE_PONTO) return true;
        const key = geometryKeyById.current.get(String(feature.id));
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      }),
    };
  }, [visibleData]);

  const layers = useMemo(() => {
    const buildings = new GeoJsonLayer({
      id: 'buildings',
      // `as any`: o tipo local é compatível com o esperado pelo deck.gl.
      data: (mapData ?? { type: 'FeatureCollection', features: [] }) as any,
      pickable: true,
      stroked: true,
      filled: true,
      extruded: true,
      wireframe: false,
      getElevation: (f: any) => {
        // Bolinhas (endereço sem prédio) ficam no plano: sem volume.
        if (f.properties?.fonte === FONTE_PONTO) return 0;
        if (camera.zoom < ZOOM_3D) return 0;
        const geometryKey = geometryKeyById.current.get(String(f.id));
        const center = geometryKey ? geometryCenterByKey.current.get(geometryKey) : null;
        if (!center || distanciaMetros(center, camera.center) > RAIO_3D_M) return 0;
        const pav = f.properties?.num_pavimentos;
        return typeof pav === 'number' && pav > 0
          ? pav * 3
          : ALTURA_PADRAO_M;
      },
      getFillColor: (f: any) => corDoTipo(f.properties?.tipo),
      getLineColor: [45, 45, 45, 140],
      lineWidthMinPixels: 0.5,
    });

    const highlight = new GeoJsonLayer({
      id: 'selected-building',
      data: (selectedFeature ? [selectedFeature] : []) as any,
      pickable: false,
      stroked: true,
      filled: false,
      getLineColor: [20, 20, 20, 255],
      lineWidthMinPixels: 3,
      lineWidthMaxPixels: 5,
    });

    return [buildings, highlight];
  }, [mapData, selectedFeature, camera]);

  useEffect(() => {
    overlayRef.current?.setProps({ layers });
  }, [layers]);

  const legenda = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of visibleData?.features ?? []) {
      const t = String(f.properties['tipo'] ?? 'desconhecido');
      counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    return TIPOS_ORDEM.map((t) => ({ tipo: t, n: counts.get(t) ?? 0 })).filter(
      (x) => x.n > 0,
    );
  }, [visibleData]);

  const total = visibleData?.features.length ?? 0;

  const closePanel = useCallback(() => setSelectedId(null), []);

  const P = selectedFeature?.properties as BuildingProps | undefined;

  return (
    <>
      <div ref={mapContainer} className="map-container" />

      {!loading && visibleData && (
        <button
          className="report-button"
          onClick={() => setShowReport(true)}
        >
          Relatório
        </button>
      )}

      {loading && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%,-50%)',
            background: 'rgba(255,255,255,0.9)',
            padding: '12px 20px',
            borderRadius: 8,
            zIndex: 20,
            boxShadow: '0 1px 6px rgba(0,0,0,0.25)',
          }}
        >
          Carregando prédios da área visível…
        </div>
      )}

      {error && (
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            background: 'rgba(255,235,235,0.95)',
            color: '#b71c1c',
            padding: 10,
            borderRadius: 8,
            zIndex: 20,
          }}
        >
          Erro ao carregar: {error}
          <br />
          Confirme que o backend FastAPI está em {API_URL}.
        </div>
      )}

      {loadingMore && !loading && (
        <div style={{ position: 'absolute', top: 12, left: 12, background: 'rgba(255,255,255,0.9)', padding: '8px 12px', borderRadius: 8, zIndex: 10 }}>
          Carregando área do mapa… {loadedCount.toLocaleString('pt-BR')} features carregadas
        </div>
      )}

      {legenda.length > 0 && (
        <div className="legend">
          <h4>Uso da edificação ({total.toLocaleString('pt-BR')} registros carregados)</h4>
          <label className="legend-toggle">
            <input
              type="checkbox"
              checked={showPontos}
              onChange={(e) => setShowPontos(e.target.checked)}
            />
            Endereços sem prédio
          </label>
          {showPontos && (
            <div className="legend-sub">
              <label className="legend-toggle">
                <input
                  type="radio"
                  name="modo-pontos"
                  checked={modoPontos === 'todos'}
                  onChange={() => setModoPontos('todos')}
                />
                Tudo visível
              </label>
              <label
                className="legend-toggle"
                title="Isola o prédio clicado e os endereços dele"
              >
                <input
                  type="radio"
                  name="modo-pontos"
                  checked={modoPontos === 'no-selecionado'}
                  onChange={() => setModoPontos('no-selecionado')}
                />
                Só o prédio selecionado
              </label>
              {modoPontos === 'no-selecionado' && !selectedFeature && (
                <span style={{ color: '#888', fontSize: 12 }}>
                  Clique em um prédio para isolar os endereços dele
                </span>
              )}
            </div>
          )}
          {legenda.map(({ tipo, n }) => (
            <div key={tipo} className="legend-item">
              <span
                className="legend-swatch"
                style={{
                  background: `rgb(${corDoTipo(tipo).slice(0, 3).join(',')})`,
                }}
              />
              <span>{tipo}</span>
              <span style={{ marginLeft: 'auto', color: '#888' }}>{n}</span>
            </div>
          ))}
          <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>
            3D só acima do zoom {ZOOM_3D} e até {RAIO_3D_M} m do centro da câmera;
            restante fica em 2D. Altura estimada: {ALTURA_PADRAO_M} m.
          </div>
          <div style={{ color: '#888', fontSize: 12 }}>
            Dados carregam conforme a área visível; use zoom out para ver mais.
          </div>
        </div>
      )}

      {!selectedFeature && !loading && (
        <div className="empty-hint">
          Clique em um prédio para ver os dados
        </div>
      )}

      {showReport && (
        <Suspense fallback={<div className="info-panel">Carregando relatório…</div>}>
          <Report onClose={() => setShowReport(false)} />
        </Suspense>
      )}

      {P && (
        <div className="info-panel">
          <button className="close" onClick={closePanel} aria-label="Fechar">
            ×
          </button>
          <h2>Edificação</h2>
          <dl>
            <dt>Endereço</dt>
            <dd>{P.endereco ?? 'Não informado'}</dd>
            <dt>Bairro</dt>
            <dd>{P.bairro ?? 'Não informado'}</dd>
            <dt>Estabelecimento</dt>
            <dd>{P.estabelecimento ?? 'Não informado'}</dd>
            <dt>Tipo</dt>
            <dd>
              <span
                className="tipo-badge"
                style={{
                  background: `rgb(${corDoTipo(P.tipo).slice(0, 3).join(',')})`,
                }}
              >
                {P.tipo}
              </span>
            </dd>
            <dt>Área</dt>
            <dd>
              {P.area_m2 != null
                ? `${Math.round(P.area_m2).toLocaleString('pt-BR')} m²`
                : 'Não informado'}
            </dd>
            <dt>Pavimentos</dt>
            <dd>{P.num_pavimentos ?? 'Não informado'}</dd>
            <dt>Fonte</dt>
            <dd>{P.fonte ?? 'Não informado'}</dd>
          </dl>
        </div>
      )}
    </>
  );
}
