import type { Theme } from '../constants';
import { formatNumber } from '../format';
import type { MapMeta } from '../mapTiles';
import {
  corDaConfianca,
  ROOFTOP_CONFIDENCES,
  rotuloDaConfianca,
  type RooftopConfidence,
  type RooftopOptions,
} from '../rooftop';

interface Props {
  value: RooftopOptions;
  onChange: (value: RooftopOptions) => void;
  meta: MapMeta | null;
  theme?: Theme;
  showEnableToggle?: boolean;
  enabled?: boolean;
  onEnabledChange?: (value: boolean) => void;
}

export function RooftopControls({
  value,
  onChange,
  meta,
  theme = 'dark',
  showEnableToggle = false,
  enabled = true,
  onEnabledChange,
}: Props) {
  const alta = meta?.high_count ?? 0;
  const media = meta?.medium_count ?? 0;
  const baixa = meta?.low_count ?? 0;
  const total = meta?.address_count ?? 0;
  const counts: Record<RooftopConfidence, number> = {
    alta,
    media,
    baixa,
    nenhuma: Math.max(0, total - alta - media - baixa),
  };
  const max = Math.max(1, ...ROOFTOP_CONFIDENCES.map((key) => counts[key]));

  const toggleConfianca = (key: RooftopConfidence) => {
    const next = new Set(value.confiancas);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onChange({ ...value, confiancas: next });
  };

  return (
    <div className="option-card rooftop-options">
      {showEnableToggle && (
        <label className="switch-row">
          <span>
            <strong>Camada CNEFE rooftop</strong>
            <span className="muted">Pontos calculados localmente, sem API externa</span>
          </span>
          <input
            type="checkbox"
            role="switch"
            className="switch"
            checked={enabled}
            onChange={(event) => onEnabledChange?.(event.target.checked)}
          />
        </label>
      )}

      {(!showEnableToggle || enabled) && (
        <>
          <div className="section-head">
            <h2 className="section-label">Confiança dos pontos</h2>
            {value.confiancas.size !== ROOFTOP_CONFIDENCES.length && (
              <button
                type="button"
                className="link-button"
                onClick={() => onChange({ ...value, confiancas: new Set(ROOFTOP_CONFIDENCES) })}
              >
                Todas
              </button>
            )}
          </div>
          <ul className="tipo-list" aria-label="Filtrar pontos rooftop por confiança">
            {ROOFTOP_CONFIDENCES.map((key) => {
              const visible = value.confiancas.has(key);
              return (
                <li key={key}>
                  <button
                    type="button"
                    className={`tipo-row${visible ? '' : ' off'}`}
                    aria-pressed={visible}
                    onClick={() => toggleConfianca(key)}
                  >
                    <span className="swatch" style={{ background: corDaConfianca(key, theme) }} />
                    <span className="tipo-name">{rotuloDaConfianca(key)}</span>
                    <span className="tipo-count">{visible ? formatNumber(counts[key]) : 'oculto'}</span>
                    <span className="tipo-bar" aria-hidden="true">
                      <span style={{ width: visible ? `${(counts[key] / max) * 100}%` : 0, background: corDaConfianca(key, theme) }} />
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          <label className="switch-row">
            <span>
              <strong>Pontos de endereço</strong>
              <span className="muted">Um ponto por endereço, dentro do prédio</span>
            </span>
            <input
              type="checkbox"
              role="switch"
              className="switch"
              checked={value.showPoints}
              onChange={(event) => onChange({ ...value, showPoints: event.target.checked })}
            />
          </label>
          <label className="switch-row">
            <span>
              <strong>Polígonos dos prédios</strong>
              <span className="muted">Contorno do prédio com o resumo dos endereços</span>
            </span>
            <input
              type="checkbox"
              role="switch"
              className="switch"
              checked={value.showPolygons}
              onChange={(event) => onChange({ ...value, showPolygons: event.target.checked })}
            />
          </label>
          <label className="switch-row">
            <span>
              <strong>Somente alterados</strong>
              <span className="muted">Endereços que mudaram de prédio ou de ponto</span>
            </span>
            <input
              type="checkbox"
              role="switch"
              className="switch"
              checked={value.onlyChanged}
              onChange={(event) => onChange({ ...value, onlyChanged: event.target.checked })}
            />
          </label>

          {meta?.missing && (
            <p className="muted small">Nenhum GeoJSON de pontos encontrado. Rode cnefe_rooftop.py com --web-geojson.</p>
          )}
          {value.showPolygons && meta?.polygon_missing && (
            <p className="muted small">Nenhum GeoJSON de polígonos encontrado. Rode cnefe_rooftop.py com --web-poligonos.</p>
          )}
          {meta && (
            <p className="muted small">
              {formatNumber(total)} pontos em {formatNumber(meta.building_count ?? 0)} prédios
              {meta.polygon_count != null ? ` · ${formatNumber(meta.polygon_count)} polígonos` : ''}.
            </p>
          )}
        </>
      )}
    </div>
  );
}
