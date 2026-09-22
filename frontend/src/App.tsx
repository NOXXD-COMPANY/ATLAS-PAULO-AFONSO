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
import { TIPOS_ORDEM, corDoTipo } from './constants';

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

type GeoJsonFC = { type: 'FeatureCollection'; features: GeoJsonFeature[] };

const API_URL = 'http://127.0.0.1:8000';

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

function boundingBox(fc: GeoJsonFC | null): [[number, number], [number, number]] {
  let minLon = Infinity;
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: OSM_STYLE,
      center: [-38.223898, -9.402317],
      zoom: 14,
      maxPitch: 85,
    });
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
    async function load() {
      try {
        const res = await fetch(`${API_URL}/api/buildings`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const fc = (await res.json()) as GeoJsonFC;
        setData(fc);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  useEffect(() => {
    if (!data || !mapRef.current) return;
    const [[swLon, swLat], [neLon, neLat]] = boundingBox(data);
    mapRef.current.fitBounds(
      [
        [swLon, swLat],
        [neLon, neLat],
      ],
      { padding: 60, duration: 0 },
    );
  }, [data]);

  const selectedFeature = useMemo<GeoJsonFeature | null>(() => {
    if (!selectedId || !data) return null;
    return data.features.find(
      (f) => String(f.properties['id']) === selectedId,
    ) ?? null;
  }, [selectedId, data]);

  const layers = useMemo(() => {
    const buildings = new GeoJsonLayer({
      id: 'buildings',
      // `as any`: o tipo local é compatível com o esperado pelo deck.gl.
      data: (data ?? { type: 'FeatureCollection', features: [] }) as any,
      pickable: true,
      stroked: true,
      filled: true,
      extruded: true,
      wireframe: false,
      getElevation: (f: any) => (f.properties?.num_pavimentos ?? 0) * 3,
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
  }, [data, selectedFeature]);

  useEffect(() => {
    overlayRef.current?.setProps({ layers });
  }, [layers]);

  const legenda = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of data?.features ?? []) {
      const t = String(f.properties['tipo'] ?? 'desconhecido');
      counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    return TIPOS_ORDEM.map((t) => ({ tipo: t, n: counts.get(t) ?? 0 })).filter(
      (x) => x.n > 0,
    );
  }, [data]);

  const closePanel = useCallback(() => setSelectedId(null), []);

  const P = selectedFeature?.properties as BuildingProps | undefined;

  return (
    <>
      <div ref={mapContainer} className="map-container" />

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
          <h4>Uso da edificação</h4>
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
        </div>
      )}

      {!selectedFeature && !loading && (
        <div className="empty-hint">
          Clique em um prédio para ver os dados
        </div>
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