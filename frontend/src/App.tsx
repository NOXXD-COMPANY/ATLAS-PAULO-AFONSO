import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import type { Map as MapLibreMap, MapLayerMouseEvent } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers';
import {
  API_URL,
  TIPOS_ORDEM,
  corDoTipo,
  fetchJson,
  FONTE_PONTO,
} from './constants';
import Report, { IconeFechar } from './Report';

interface PredioProps {
  tipo: string;
  fonte: string | null;
  num_pavimentos: number | null;
  /** Quantos endereços do CNEFE caem neste prédio. */
  n: number;
  /** Centro do prédio [lon, lat]: onde o endereço é desenhado. */
  ponto: [number, number];
}

type Predio = {
  type: 'Feature';
  id: string;
  geometry: { type: string; coordinates: any };
  properties: PredioProps;
};

interface Endereco {
  id: string;
  endereco: string | null;
  bairro: string | null;
  estabelecimento: string | null;
  tipo: string;
}

type Detalhe = {
  id: string;
  erro: boolean;
  area_m2?: number | null;
  enderecos?: Endereco[];
};

// Altura ilustrativa (m) quando o número de pavimentos é desconhecido.
// Prédios com `num_pavimentos` usam pavimentos × 3 m (dado real do Overture).
const ALTURA_PADRAO_M = 5;

// ~10 mil prédios por requisição: o mapa pinta aos poucos e cada página
// vira uma camada própria, que não é reprocessada quando chega a próxima.
const PAGE_SIZE = 10000;

// Mapa base vetorial gratuito, sem chave e sem limite de uso (OpenFreeMap).
const MAPA_BASE = 'https://tiles.openfreemap.org/styles/positron';

function elevacao(p: PredioProps): number {
  // Bolinhas (endereço sem prédio) ficam no plano: sem volume.
  if (p.fonte === FONTE_PONTO) return 0;
  return typeof p.num_pavimentos === 'number' && p.num_pavimentos > 0
    ? p.num_pavimentos * 3
    : ALTURA_PADRAO_M;
}

function corCss(tipo: string): string {
  return `rgb(${corDoTipo(tipo).slice(0, 3).join(',')})`;
}

function boundingBox(pages: Predio[][]): [[number, number], [number, number]] {
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  for (const page of pages) {
    for (const f of page) {
      const [lon, lat] = f.properties.ponto;
      minLon = Math.min(minLon, lon);
      maxLon = Math.max(maxLon, lon);
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
    }
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
  const userMovedRef = useRef(false);

  const [pages, setPages] = useState<Predio[][]>([]);
  const [selected, setSelected] = useState<Predio | null>(null);
  const [detalhe, setDetalhe] = useState<Detalhe | null>(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ loaded: 0, total: 0 });
  const [error, setError] = useState<string | null>(null);
  const [showPontos, setShowPontos] = useState(true);
  const [modoPontos, setModoPontos] = useState<'todos' | 'no-selecionado'>(
    'todos',
  );
  const [showReport, setShowReport] = useState(false);

  useEffect(() => {
    if (!mapContainer.current) return;
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: MAPA_BASE,
      center: [-38.223898, -9.402317],
      zoom: 14,
      maxPitch: 85,
    });
    // Os prédios do mapa base (OSM) não batem com os nossos: escondidos
    // para não aparecer contorno duplicado ao lado de cada edificação.
    map.on('load', () => {
      for (const l of map.getStyle().layers ?? []) {
        if (l.id.includes('building')) {
          map.setLayoutProperty(l.id, 'visibility', 'none');
        }
      }
    });
    map.on('movestart', (e) => {
      if (e.originalEvent) userMovedRef.current = true;
    });
    // O 3D é 100% dos nossos dados (camadas deck.gl abaixo): cada volume
    // extrusado É um prédio, logo carrega sempre a cor do tipo e os endereços.
    const overlay = new MapboxOverlay({ layers: [] });
    map.addControl(overlay);
    overlayRef.current = overlay;
    mapRef.current = map;

    const onClick = (e: MapLayerMouseEvent) => {
      const info = overlay.pickObject({ x: e.point.x, y: e.point.y, radius: 4 });
      const obj = info?.object as Predio | undefined;
      // Cópia: clicar de novo no mesmo prédio refaz a busca (ex.: após erro).
      setSelected(obj ? { ...obj } : null);
      // Painel e relatório ocupam o mesmo canto: um fecha o outro.
      if (obj) setShowReport(false);
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
    const ctrl = new AbortController();

    async function load() {
      try {
        // Total para a barra de progresso; em_cobertura esconde as bolinhas
        // fora da área com prédios.
        const stats = await fetchJson(
          `${API_URL}/api/stats?em_cobertura=true`,
          5,
          ctrl.signal,
        );
        const total = typeof stats?.predios === 'number' ? stats.predios : 0;
        setProgress({ loaded: 0, total });

        for (let offset = 0; ; ) {
          const fc = await fetchJson(
            `${API_URL}/api/predios?em_cobertura=true&limit=${PAGE_SIZE}&offset=${offset}`,
            3,
            ctrl.signal,
          );
          const features = fc?.features as Predio[] | undefined;
          if (!Array.isArray(features)) {
            throw new Error('resposta inválida da API');
          }
          offset += features.length;
          if (features.length > 0) setPages((p) => [...p, features]);
          setProgress({ loaded: offset, total: Math.max(total, offset) });
          if (features.length < PAGE_SIZE) break;
        }
      } catch (err) {
        if (!ctrl.signal.aborted)
          setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
      } finally {
        if (!ctrl.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => ctrl.abort();
  }, []);

  // Enquadra tudo só no fim, e só se a pessoa ainda não mexeu no mapa.
  useEffect(() => {
    if (loading || pages.length === 0 || !mapRef.current) return;
    if (userMovedRef.current) return;
    mapRef.current.fitBounds(boundingBox(pages), { padding: 60, duration: 0 });
  }, [loading, pages]);

  // Detalhe sob demanda: os endereços só viajam quando o prédio é clicado.
  useEffect(() => {
    if (!selected) return;
    const ctrl = new AbortController();
    const id = selected.id;
    fetchJson(
      `${API_URL}/api/predios/${encodeURIComponent(id)}`,
      2,
      ctrl.signal,
    )
      .then((f) =>
        setDetalhe({
          id,
          erro: false,
          area_m2: f?.properties?.area_m2 ?? null,
          enderecos: f?.properties?.enderecos ?? [],
        }),
      )
      .catch(() => {
        if (!ctrl.signal.aborted) setDetalhe({ id, erro: true });
      });
    return () => ctrl.abort();
  }, [selected]);

  const visiblePages = useMemo<Predio[][]>(() => {
    // 'no-selecionado': isola o prédio clicado. Sem seleção, vazio.
    if (modoPontos === 'no-selecionado') return selected ? [[selected]] : [];
    if (!showPontos)
      return pages.map((p) => p.filter((f) => f.properties.fonte !== FONTE_PONTO));
    return pages;
  }, [pages, showPontos, modoPontos, selected]);

  const layers = useMemo(() => {
    const predios = visiblePages.map(
      (data, i) =>
        new GeoJsonLayer({
          id: `predios-${i}`,
          // `as any`: o tipo local é compatível com o esperado pelo deck.gl.
          data: data as any,
          pickable: true,
          filled: true,
          extruded: true,
          wireframe: false,
          getElevation: (f: any) => elevacao(f.properties),
          getFillColor: (f: any) => corDoTipo(f.properties.tipo),
        }),
    );

    // Endereço desenhado no centro do telhado. Raio em metros: some sozinho
    // com o zoom afastado, sem precisar acompanhar o zoom no React.
    const enderecos = visiblePages.map(
      (data, i) =>
        new ScatterplotLayer<Predio>({
          id: `enderecos-${i}`,
          data,
          pickable: true,
          getPosition: (f) => [...f.properties.ponto, elevacao(f.properties) + 0.3],
          getRadius: (f) => (f.properties.n > 0 ? 1.2 : 0),
          radiusUnits: 'meters',
          radiusMaxPixels: 5,
          stroked: true,
          getFillColor: [255, 255, 255, 235],
          getLineColor: [30, 30, 30, 200],
          lineWidthUnits: 'pixels',
          getLineWidth: 1,
        }),
    );

    const highlight = new GeoJsonLayer({
      id: 'selected-building',
      data: (selected ? [selected] : []) as any,
      pickable: false,
      stroked: true,
      filled: false,
      getLineColor: [20, 20, 20, 255],
      lineWidthMinPixels: 3,
      lineWidthMaxPixels: 5,
      // Contorno por cima do 3D: não some atrás do telhado.
      parameters: { depthCompare: 'always' },
    });

    return [...predios, ...enderecos, highlight];
  }, [visiblePages, selected]);

  useEffect(() => {
    overlayRef.current?.setProps({ layers });
  }, [layers]);

  const legenda = useMemo(() => {
    const counts = new Map<string, number>();
    for (const page of visiblePages) {
      for (const f of page) {
        const t = f.properties.tipo ?? 'desconhecido';
        counts.set(t, (counts.get(t) ?? 0) + 1);
      }
    }
    return TIPOS_ORDEM.map((t) => ({ tipo: t, n: counts.get(t) ?? 0 })).filter(
      (x) => x.n > 0,
    );
  }, [visiblePages]);

  const total = legenda.reduce((s, x) => s + x.n, 0);

  const closePanel = useCallback(() => setSelected(null), []);

  const P = selected?.properties;
  const D = detalhe && selected && detalhe.id === selected.id ? detalhe : null;
  const pct =
    progress.total > 0
      ? Math.min(1, progress.loaded / progress.total)
      : 0;

  return (
    <>
      <div ref={mapContainer} className="map-container" />

      <button
        className="report-button"
        onClick={() => {
          setSelected(null);
          setShowReport(true);
        }}
      >
        Relatório
      </button>

      {loading && !error && (
        <div className="loading" role="status">
          <span>
            Carregando prédios
            {progress.total > 0 &&
              ` · ${progress.loaded.toLocaleString('pt-BR')} de ${progress.total.toLocaleString('pt-BR')}`}
          </span>
          <div className="loading-bar" aria-hidden="true">
            <div style={{ transform: `scaleX(${pct})` }} />
          </div>
        </div>
      )}

      {error && (
        <div className="error-box" role="alert">
          Não foi possível carregar os prédios ({error}).
          <br />
          Confirme que o backend FastAPI está rodando em {API_URL} e recarregue
          a página.
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
              {modoPontos === 'no-selecionado' && !selected && (
                <span className="legend-note">
                  Clique em um prédio para isolar os endereços dele
                </span>
              )}
            </div>
          )}
          {legenda.map(({ tipo, n }) => (
            <div key={tipo} className="legend-item">
              <span
                className="legend-swatch"
                style={{ background: corCss(tipo) }}
              />
              <span>{tipo}</span>
              <span className="legend-count">{n.toLocaleString('pt-BR')}</span>
            </div>
          ))}
          <div className="legend-note">
            Prédios em 3D (altura ilustrativa de {ALTURA_PADRAO_M} m; real
            quando há pavimentos). O ponto branco marca o endereço, no centro
            do prédio.
          </div>
          <div className="legend-note">
            Só a área com prédios mapeados; endereços fora dela ocultos.
          </div>
        </div>
      )}

      {!selected && !loading && !error && (
        <div className="empty-hint">Clique em um prédio para ver os dados</div>
      )}

      {showReport && <Report onClose={() => setShowReport(false)} />}

      {P && (
        <div className="info-panel">
          <button className="close" onClick={closePanel} aria-label="Fechar">
            <IconeFechar />
          </button>
          <h2>Edificação</h2>
          <dl>
            <dt>Tipo</dt>
            <dd>
              <span className="tipo-badge" style={{ background: corCss(P.tipo) }}>
                {P.tipo}
              </span>
            </dd>
            <dt>Área</dt>
            <dd>
              {D?.area_m2 != null
                ? `${Math.round(D.area_m2).toLocaleString('pt-BR')} m²`
                : D
                  ? 'Não informado'
                  : '…'}
            </dd>
            <dt>Pavimentos</dt>
            <dd>{P.num_pavimentos ?? 'Não informado'}</dd>
            <dt>Fonte</dt>
            <dd>{P.fonte ?? 'Não informado'}</dd>
          </dl>

          <h3>
            {P.n === 1 ? '1 endereço' : `${P.n.toLocaleString('pt-BR')} endereços`}
          </h3>
          {P.n === 0 ? (
            <p className="panel-note">
              Nenhum endereço do CNEFE ligado a este prédio.
            </p>
          ) : !D ? (
            <p className="panel-note">Carregando endereços…</p>
          ) : D.erro ? (
            <p className="panel-note">
              Não foi possível carregar os endereços. Clique no prédio de novo.
            </p>
          ) : (
            <ul className="enderecos">
              {D.enderecos?.map((e) => (
                <li key={e.id}>
                  <span
                    className="legend-swatch"
                    style={{ background: corCss(e.tipo) }}
                    title={e.tipo}
                  />
                  <div>
                    <strong>{e.endereco ?? 'Sem logradouro'}</strong>
                    <span>
                      {[e.estabelecimento, e.bairro].filter(Boolean).join(' · ') ||
                        e.tipo}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </>
  );
}
