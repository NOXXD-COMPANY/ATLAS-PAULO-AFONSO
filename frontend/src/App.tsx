import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import Report from './Report';

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

// Carga paginada: ~5 mil features por requisição em vez de um único JSON
// de ~200 MB, para o mapa ir pintando aos poucos sem travar o navegador.
const PAGE_SIZE = 5000;

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

function boundingBox(fc: GeoJsonFC | null): [[number, number], [number, number]] { let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  const visit = (coords: number[][]) => {
    for (const [lon, lat] of coords) {
      minLon = Math.min(minLon, lon);
      maxLon = Math.max(maxLon, lon);
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
    }
  };
  for (const f of fc?.features ?? []) {
    const g = f.geometry as { type: string; coordinates: any[] };
    if (g.type === 'Polygon') visit(g.coordinates[0]);
    else if (g.type === 'MultiPolygon') for (const p of g.coordinates) visit(p[0]);
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  const [data, setData] = useState<GeoJsonFC | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const [showPontos, setShowPontos] = useState(true);
  const [modoPontos, setModoPontos] = useState<'todos' | 'no-selecionado'>(
    'todos',
  );
  const [showReport, setShowReport] = useState(false);
  const didFitRef = useRef(false);

  useEffect(() => {
    if (!mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: OSM_STYLE,
      center: [-38.223898, -9.402317],
      zoom: 14,
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
      const props = info?.object?.properties as BuildingProps | undefined;
      setSelectedId(props?.id ?? null);
    };
    map.on('click', onClick);

    return () => {
      map.off('click', onClick);
      map.remove();
      overlayRef.current = null;
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchJson(url: string, attempts: number): Promise<any> {
      let lastErr: unknown = null;
      for (let attempt = 1; attempt <= attempts; attempt++) {
        try {
          const res = await fetch(url);
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return await res.json();
        } catch (err) {
          lastErr = err;
          if (attempt < attempts)
            await new Promise((r) => setTimeout(r, 2000));
        }
      }
      throw lastErr;
    }

    async function load() {
      try {
        // Total para a barra de progresso (o backend pode estar subindo).
        // em_cobertura: esconde as bolinhas fora da área com prédios.
        const stats = await fetchJson(
          `${API_URL}/api/stats?em_cobertura=true`,
          5,
        );
        const total =
          typeof stats?.total === 'number' && stats.total > 0
            ? stats.total
            : 0;
        if (!cancelled && total > 0) setProgress({ loaded: 0, total });

        // Páginas acumuladas: o mapa pinta cada lote sem congelar a tela.
        const all: GeoJsonFeature[] = [];
        let offset = 0;
        for (;;) {
          const fc = (await fetchJson(
            `${API_URL}/api/buildings?em_cobertura=true&limit=${PAGE_SIZE}&offset=${offset}`,
            3,
          )) as GeoJsonFC;
          if (!fc || !Array.isArray(fc.features)) {
            throw new Error('resposta inválida da API');
          }
          all.push(...fc.features);
          offset += fc.features.length;
          if (cancelled) return;
          setProgress({ loaded: offset, total: Math.max(total, offset) });
          setData({ type: 'FeatureCollection', features: [...all] });
          if (fc.features.length < PAGE_SIZE) break;
        }
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!data || !mapRef.current || didFitRef.current) return;
    const [[swLon, swLat], [neLon, neLat]] = boundingBox(data);
    mapRef.current.fitBounds(
      [
        [swLon, swLat],
        [neLon, neLat],
      ],
      { padding: 60, duration: 0 },
    );
    didFitRef.current = true;
  }, [data]);

  const selectedFeature = useMemo<GeoJsonFeature | null>(() => {
    if (!selectedId || !data) return null;
    // Baseado nos dados completos para o painel não sumir com os filtros.
    return data.features.find(
      (f) => String(f.properties['id']) === selectedId,
    ) ?? null;
  }, [selectedId, data]);

  // Chave canônica da geometria: linhas que compartilham o polígono
  // (1 telhado × N endereços) têm a mesma chave.
  const geomKeys = useMemo(
    () =>
      data?.features.map((f) => JSON.stringify(f.geometry.coordinates)) ??
      [],
    [data],
  );
  const selectedGeomKey = selectedFeature
    ? JSON.stringify(selectedFeature.geometry.coordinates)
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
      features: data.features.filter((_, i) => geomKeys[i] === selectedGeomKey),
    };
  }, [data, showPontos, modoPontos, geomKeys, selectedGeomKey]);

  const layers = useMemo(() => {
    const buildings = new GeoJsonLayer({
      id: 'buildings',
      // `as any`: o tipo local é compatível com o esperado pelo deck.gl.
      data: (visibleData ?? { type: 'FeatureCollection', features: [] }) as any,
      pickable: true,
      stroked: true,
      filled: true,
      extruded: true,
      wireframe: false,
      getElevation: (f: any) => {
        // Bolinhas (endereço sem prédio) ficam no plano: sem volume.
        if (f.properties?.fonte === FONTE_PONTO) return 0;
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
  }, [visibleData, selectedFeature]);

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
          Carregando prédios…
          {progress.total > 0 && (
            <>
              <br />
              {progress.loaded.toLocaleString('pt-BR')} de{' '}
              {progress.total.toLocaleString('pt-BR')} (
              {Math.round((progress.loaded / progress.total) * 100)}%)
            </>
          )}
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

      {legenda.length > 0 && (
        <div className="legend">
          <h4>Uso da edificação ({total.toLocaleString('pt-BR')})</h4>
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
            Prédios em 3D (altura ilustrativa de {ALTURA_PADRAO_M} m; real
            quando há pavimentos); bolinhas ficam no plano.
          </div>
          <div style={{ color: '#888', fontSize: 12 }}>
            Só a área com prédios mapeados; endereços fora dela ocultos.
          </div>
        </div>
      )}

      {!selectedFeature && !loading && (
        <div className="empty-hint">
          Clique em um prédio para ver os dados
        </div>
      )}

      {showReport && visibleData && (
        <Report data={visibleData} onClose={() => setShowReport(false)} />
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