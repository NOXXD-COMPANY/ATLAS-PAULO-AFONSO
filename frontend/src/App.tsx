import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { Map as MapLibreMap, MapLayerMouseEvent, StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { corDoTipo, FONTE_PONTO, TIPOS_ORDEM } from './constants';
import { BUILDING_TILE_MAX_ZOOM, buildingTileUrl, prefetchNearbyTiles } from './mapTiles';
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
  geometry_key?: string;
}

type GeoJsonFeature = {
  type: 'Feature';
  id?: string | number;
  geometry: { type: string; coordinates: any };
  properties: BuildingProps | Record<string, unknown>;
};

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';
const ALTURA_PADRAO_M = 15;
const CENTRO = [-38.223898, -9.402317] as [number, number];
const ZOOM_INICIAL = 17.5;

const TIPO_CORES_MAP: Record<string, string> = {
  residencial: 'rgb(25,118,210)',
  comercial: 'rgb(230,57,70)',
  servico: 'rgb(255,143,0)',
  religioso: 'rgb(126,87,194)',
  institucional: 'rgb(0,188,212)',
  hospedagem: 'rgb(76,175,80)',
  agropecuario: 'rgb(139,195,74)',
  desconhecido: 'rgb(158,158,158)',
};

const tipoColorExpression: any = [
  'match', ['get', 'tipo'],
  ...TIPOS_ORDEM.flatMap((tipo) => [tipo, TIPO_CORES_MAP[tipo]]),
  TIPO_CORES_MAP.desconhecido,
];

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
    buildings: {
      type: 'vector',
      tiles: [buildingTileUrl(API_URL, '{z}', '{x}', '{y}')],
      minzoom: 0,
      maxzoom: BUILDING_TILE_MAX_ZOOM,
    },
    selected: {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    },
  },
  layers: [
    { id: 'osm', type: 'raster', source: 'osm' },
    {
      id: 'buildings-fill', type: 'fill', source: 'buildings', 'source-layer': 'buildings',
      paint: { 'fill-color': tipoColorExpression, 'fill-opacity': 0.82 },
    },
    {
      id: 'buildings-outline', type: 'line', source: 'buildings', 'source-layer': 'buildings',
      paint: { 'line-color': 'rgba(45,45,45,0.65)', 'line-width': 0.7 },
    },
    {
      id: 'addresses-points', type: 'circle', source: 'buildings', 'source-layer': 'buildings',
      filter: ['==', ['geometry-type'], 'Point'],
      paint: { 'circle-color': tipoColorExpression, 'circle-radius': 4, 'circle-stroke-color': '#333', 'circle-stroke-width': 0.7 },
    },
    {
      id: 'selected-building-3d', type: 'fill-extrusion', source: 'selected',
      paint: {
        'fill-extrusion-color': tipoColorExpression,
        'fill-extrusion-height': ['number', ['get', 'altura_3d_m'], ALTURA_PADRAO_M],
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.95,
        'fill-extrusion-vertical-gradient': true,
      },
    },
  ],
};

async function fetchJson(url: string, signal?: AbortSignal): Promise<any> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<{ id: string; feature: GeoJsonFeature } | null>(null);
  const [selectedPreview, setSelectedPreview] = useState<{ id: string; feature: GeoJsonFeature } | null>(null);
  const [showPontos, setShowPontos] = useState(true);
  const [modoPontos, setModoPontos] = useState<'todos' | 'no-selecionado'>('todos');
  const [showReport, setShowReport] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: OSM_STYLE,
      center: CENTRO,
      zoom: ZOOM_INICIAL,
      pitch: 55,
      maxPitch: 85,
      maxTileCacheSize: 24,
      maxTileCacheZoomLevels: 1,
      cancelPendingTileRequestsWhileZooming: true,
      renderWorldCopies: false,
    });
    mapRef.current = map;

    const onClick = (event: MapLayerMouseEvent) => {
      const features = map.queryRenderedFeatures(event.point, {
        layers: ['selected-building-3d', 'buildings-fill', 'addresses-points'],
      });
      const clickedFeature = features.find((feature) =>
        (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon')
          && feature.properties?.fonte !== FONTE_PONTO)
        ?? features[0];
      const id = clickedFeature?.properties?.id;
      setSelectedPreview(id == null ? null : {
        id: String(id),
        feature: {
          type: 'Feature',
          geometry: clickedFeature.geometry,
          properties: clickedFeature.properties,
        },
      });
      setSelectedId(id == null ? null : String(id));
    };
    const onLoad = () => setMapReady(true);
    const onError = (event: maplibregl.ErrorEvent) => {
      const sourceId = (event as maplibregl.ErrorEvent & { sourceId?: string }).sourceId;
      setError(`Falha no mapa${sourceId ? ` (${sourceId})` : ''}: ${event.error.message}`);
    };
    map.on('click', onClick);
    // `load` espera todos os tiles visíveis; o estilo já está pronto antes.
    // Precisamos liberar a fonte de seleção sem esperar toda a rede de tiles.
    map.on('style.load', onLoad);
    map.on('error', onError);
    const stopPrefetch = prefetchNearbyTiles(map, API_URL);

    return () => {
      map.off('click', onClick);
      map.off('style.load', onLoad);
      map.off('error', onError);
      stopPrefetch();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    fetchJson(`${API_URL}/api/buildings/${encodeURIComponent(selectedId)}`, controller.signal)
      .then((feature: GeoJsonFeature) => {
        if (!controller.signal.aborted) setSelectedDetail({ id: selectedId, feature });
      })
      .catch((err) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Erro ao carregar detalhes');
      });
    return () => controller.abort();
  }, [selectedId]);

  const selectedFeature = selectedDetail?.id === selectedId ? selectedDetail.feature : null;
  const selectedProps = selectedFeature?.properties as BuildingProps | undefined;
  const selected3dFeature = selectedFeature
    ?? (selectedPreview?.id === selectedId ? selectedPreview.feature : null);
  const selectedGeometryKey = selected3dFeature?.properties?.geometry_key ?? '';

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const sameGeometryFilter = selectedGeometryKey
      ? ['==', ['get', 'geometry_key'], selectedGeometryKey]
      : ['==', ['get', 'id'], '__none__'];
    const pointFilters: any[] = [['==', ['geometry-type'], 'Point']];
    if (!showPontos) pointFilters.push(['!=', ['get', 'fonte'], FONTE_PONTO]);
    if (modoPontos === 'no-selecionado') pointFilters.push(sameGeometryFilter);
    const pointFilter = pointFilters.length === 1 ? pointFilters[0] : ['all', ...pointFilters];
    // O modo de endereços nunca deve esconder os prédios 2D da vizinhança.
    const polygonFilter = !showPontos
      ? ['!=', ['get', 'fonte'], FONTE_PONTO]
      : modoPontos === 'no-selecionado'
        ? ['any', ['!=', ['get', 'fonte'], FONTE_PONTO], sameGeometryFilter]
        : null;
    if (map.getLayer('addresses-points')) map.setFilter('addresses-points', pointFilter as any);
    for (const layer of ['buildings-fill', 'buildings-outline']) {
      if (map.getLayer(layer)) {
        map.setFilter(layer, polygonFilter as any);
      }
    }
  }, [mapReady, showPontos, modoPontos, selectedGeometryKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const updateVisibleCounts = () => {
      const features = map.queryRenderedFeatures({ layers: ['buildings-fill', 'addresses-points'] });
      const seen = new Set<string>();
      const nextCounts: Record<string, number> = {};
      for (const feature of features) {
        const properties = feature.properties ?? {};
        const key = String(properties.geometry_key ?? properties.id ?? feature.id ?? '');
        if (!key || seen.has(key)) continue;
        seen.add(key);
        const tipo = String(properties.tipo ?? 'desconhecido');
        nextCounts[tipo] = (nextCounts[tipo] ?? 0) + 1;
      }
      setTotal(seen.size);
      setCounts(nextCounts);
    };
    map.on('idle', updateVisibleCounts);
    map.on('moveend', updateVisibleCounts);
    updateVisibleCounts();
    return () => {
      map.off('idle', updateVisibleCounts);
      map.off('moveend', updateVisibleCounts);
    };
  }, [mapReady, showPontos, modoPontos, selectedGeometryKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    const source = map.getSource('selected') as maplibregl.GeoJSONSource | undefined;
    const floors = Number(selected3dFeature?.properties?.num_pavimentos);
    const height = Number.isFinite(floors) && floors > 0
      ? floors * 3
      : ALTURA_PADRAO_M;
    const isBuilding = selected3dFeature
      && ['Polygon', 'MultiPolygon'].includes(selected3dFeature.geometry.type)
      && selected3dFeature.properties?.fonte !== FONTE_PONTO;
    source?.setData({
      type: 'FeatureCollection',
      features: isBuilding
        ? [{
            ...selected3dFeature,
            properties: { ...selected3dFeature.properties, altura_3d_m: height },
          } as any]
        : [],
    });
  }, [mapReady, selected3dFeature]);

  const legenda = useMemo(() => TIPOS_ORDEM
    .map((tipo) => ({ tipo, n: counts[tipo] ?? 0 }))
    .filter(({ n }) => n > 0), [counts]);

  const closePanel = useCallback(() => setSelectedId(null), []);
  const P = selectedProps;

  return (
    <>
      <div ref={mapContainer} className="map-container" />

      {mapReady && (
        <button className="report-button" onClick={() => setShowReport(true)}>Relatório</button>
      )}

      {error && (
        <div style={{ position: 'absolute', top: 12, left: 12, background: 'rgba(255,235,235,0.95)', color: '#b71c1c', padding: 10, borderRadius: 8, zIndex: 20 }}>
          Erro ao carregar: {error}<br />Confirme que o backend FastAPI está em {API_URL}.
        </div>
      )}

      {mapReady && (
        <div className="legend">
          <h4>Uso da edificação ({total.toLocaleString('pt-BR')} footprints visíveis)</h4>
          <label className="legend-toggle">
            <input type="checkbox" checked={showPontos} onChange={(event) => setShowPontos(event.target.checked)} />
            Endereços sem prédio
          </label>
          {showPontos && (
            <div className="legend-sub">
              <label className="legend-toggle">
                <input type="radio" name="modo-pontos" checked={modoPontos === 'todos'} onChange={() => setModoPontos('todos')} />
                Tudo visível
              </label>
              <label className="legend-toggle" title="Mostra só os endereços do prédio clicado, mantendo os prédios ao redor">
                <input type="radio" name="modo-pontos" checked={modoPontos === 'no-selecionado'} onChange={() => setModoPontos('no-selecionado')} />
                Só endereços do prédio selecionado
              </label>
              {modoPontos === 'no-selecionado' && !selectedFeature && (
                <span style={{ color: '#888', fontSize: 12 }}>Clique em um prédio para isolar os endereços dele</span>
              )}
            </div>
          )}
          {legenda.map(({ tipo, n }) => (
            <div key={tipo} className="legend-item">
              <span className="legend-swatch" style={{ background: `rgb(${corDoTipo(tipo).slice(0, 3).join(',')})` }} />
              <span>{tipo}</span>
              <span style={{ marginLeft: 'auto', color: '#888' }}>{n}</span>
            </div>
          ))}
          <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>
            Todos os prédios ficam em 2D; somente o prédio selecionado é carregado em 3D. Altura estimada: {ALTURA_PADRAO_M} m.
          </div>
          <div style={{ color: '#888', fontSize: 12 }}>
            Blocos visíveis carregam primeiro. Blocos vizinhos ficam prontos para a navegação; os distantes saem da renderização.
          </div>
        </div>
      )}

      {!P && mapReady && <div className="empty-hint">{selectedId ? 'Carregando dados da edificação…' : 'Clique em um prédio para ver os dados e carregá-lo em 3D'}</div>}

      {showReport && (
        <Suspense fallback={<div className="info-panel">Carregando relatório…</div>}>
          <Report onClose={() => setShowReport(false)} />
        </Suspense>
      )}

      {P && (
        <div className="info-panel">
          <button className="close" onClick={closePanel} aria-label="Fechar">×</button>
          <h2>Edificação</h2>
          <dl>
            <dt>Endereço</dt><dd>{P.endereco ?? 'Não informado'}</dd>
            <dt>Bairro</dt><dd>{P.bairro ?? 'Não informado'}</dd>
            <dt>Estabelecimento</dt><dd>{P.estabelecimento ?? 'Não informado'}</dd>
            <dt>Tipo</dt>
            <dd><span className="tipo-badge" style={{ background: `rgb(${corDoTipo(P.tipo).slice(0, 3).join(',')})` }}>{P.tipo}</span></dd>
            <dt>Área</dt><dd>{P.area_m2 != null ? `${Math.round(P.area_m2).toLocaleString('pt-BR')} m²` : 'Não informado'}</dd>
            <dt>Pavimentos</dt><dd>{P.num_pavimentos ?? 'Não informado'}</dd>
          </dl>
        </div>
      )}
    </>
  );
}
