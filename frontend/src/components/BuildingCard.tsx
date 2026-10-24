import { corDoTipo, FONTE_PONTO, rotuloDoTipo, type Theme } from '../constants';
import { formatArea, formatNumber, titleCase } from '../format';
import { Icon } from './Icon';

export interface BuildingAddress {
  id: string;
  endereco: string | null;
  estabelecimento: string | null;
  tipo: string;
}

export interface BuildingProps {
  id: string;
  area_m2: number | null;
  tipo: string;
  endereco: string | null;
  bairro: string | null;
  estabelecimento: string | null;
  num_pavimentos: number | null;
  fonte: string | null;
  geometry_key?: string;
  enderecos?: BuildingAddress[];
}

interface Props {
  building: BuildingProps | null;
  previewTipo?: string;
  center: [number, number] | null;
  heightM: number;
  heightEstimated: boolean;
  theme?: Theme;
  onClose: () => void;
  onCenter: () => void;
  onSelectAddress: (id: string) => void;
  onCopy: (text: string, label: string) => void;
}

export function BuildingCard({ building, previewTipo, center, heightM, heightEstimated, theme = 'dark', ...actions }: Props) {
  const tipo = building?.tipo ?? previewTipo ?? 'desconhecido';
  const title = titleCase(building?.estabelecimento || building?.endereco) || (building ? 'Edificação sem endereço' : 'Carregando…');
  const subtitle = building?.estabelecimento ? titleCase(building.endereco) : null;
  const semPredio = building?.fonte === FONTE_PONTO;
  const outros = (building?.enderecos ?? []).filter((e) => e.id !== building?.id);
  const osmUrl = center
    ? `https://www.openstreetmap.org/?mlat=${center[1].toFixed(6)}&mlon=${center[0].toFixed(6)}#map=19/${center[1].toFixed(6)}/${center[0].toFixed(6)}`
    : null;

  return (
    <article className="building" aria-busy={!building}>
      <header className="card-head">
        <button type="button" className="icon-button" aria-label="Voltar" onClick={actions.onClose}>
          <Icon name="back" size={18} />
        </button>
        <span className="tipo-pill" style={{ ['--tipo' as string]: corDoTipo(tipo, theme) }}>
          <span className="swatch" />
          {rotuloDoTipo(tipo)}
        </span>
        <button type="button" className="icon-button" aria-label="Fechar" onClick={actions.onClose}>
          <Icon name="close" size={16} />
        </button>
      </header>

      <h2 className="building-title">{title}</h2>
      {subtitle && <p className="building-sub">{subtitle}</p>}
      <p className="building-sub muted">{building ? titleCase(building.bairro) || 'Bairro não informado' : ' '}</p>

      {building && (
        <>
          <dl className="facts">
            <div>
              <dt>Área</dt>
              <dd>{semPredio ? '—' : formatArea(building.area_m2) ?? '—'}</dd>
            </div>
            <div>
              <dt>Pavimentos</dt>
              <dd>{building.num_pavimentos ? formatNumber(building.num_pavimentos) : '—'}</dd>
            </div>
            <div>
              <dt>Altura {heightEstimated ? 'est.' : ''}</dt>
              <dd>{formatNumber(heightM)} m</dd>
            </div>
          </dl>

          <div className="actions">
            <button type="button" className="glass-button" onClick={actions.onCenter}>
              <Icon name="locate" size={16} /> Centralizar
            </button>
            {building.endereco && (
              <button type="button" className="glass-button" onClick={() => actions.onCopy(titleCase(building.endereco), 'Endereço copiado')}>
                <Icon name="copy" size={16} /> Copiar
              </button>
            )}
            {osmUrl && (
              <a className="glass-button" href={osmUrl} target="_blank" rel="noreferrer">
                <Icon name="external" size={16} /> OSM
              </a>
            )}
          </div>

          {outros.length > 0 && (
            <>
              <h3 className="section-label">Também neste prédio · {outros.length}</h3>
              <ul className="address-list">
                {outros.map((item) => (
                  <li key={item.id}>
                    <button type="button" className="result-row" onClick={() => actions.onSelectAddress(item.id)}>
                      <span className="swatch" style={{ background: corDoTipo(item.tipo, theme) }} />
                      <span className="result-text">
                        <strong>{titleCase(item.estabelecimento || item.endereco) || 'Sem endereço'}</strong>
                        <span className="muted">{[item.estabelecimento ? titleCase(item.endereco) : null, rotuloDoTipo(item.tipo)].filter(Boolean).join(' · ')}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          <footer className="provenance">
            <span>{semPredio ? 'Endereço sem footprint (CNEFE)' : `Footprint: ${building.fonte || 'não informado'}`}</span>
            <button type="button" className="link-button" onClick={() => actions.onCopy(building.id, 'ID copiado')}>ID {building.id}</button>
          </footer>
        </>
      )}
    </article>
  );
}
