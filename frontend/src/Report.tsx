import { useEffect, useMemo, useState } from 'react';
import { API_URL, TIPOS_ORDEM, fetchJson } from './constants';

type Celula = { bairro: string; tipo: string; n: number };

function normalizarBairro(nome: string): string {
  return nome.replace(/\s+\d+\s*$/, '').trim() || nome;
}

export function IconeFechar() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path
        d="M2 2l10 10M12 2L2 12"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

function somar(celulas: Celula[], chave: 'tipo' | 'bairro') {
  const counts = new Map<string, number>();
  for (const c of celulas) counts.set(c[chave], (counts.get(c[chave]) ?? 0) + c.n);
  return counts;
}

export default function Report({ onClose }: { onClose: () => void }) {
  // Agregado no servidor (bairro × tipo): o relatório não precisa dos
  // prédios carregados no mapa e filtra na hora, sem nova requisição.
  const [celulas, setCelulas] = useState<Celula[] | null>(null);
  const [erro, setErro] = useState(false);
  const [filtroTipo, setFiltroTipo] = useState('todos');
  const [filtroBairros, setFiltroBairros] = useState<string[]>([]);
  const [buscaBairro, setBuscaBairro] = useState('');

  useEffect(() => {
    const ctrl = new AbortController();
    fetchJson(`${API_URL}/api/stats?em_cobertura=true`, 3, ctrl.signal)
      .then((s) => {
        const cel = Array.isArray(s?.by_bairro_tipo) ? (s.by_bairro_tipo as Celula[]) : [];
        setCelulas(cel.map((c) => ({ ...c, bairro: normalizarBairro(c.bairro) })));
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setErro(true);
      });
    return () => ctrl.abort();
  }, []);

  const bairros = useMemo(
    () =>
      [...new Set((celulas ?? []).map((c) => c.bairro))].sort((a, b) =>
        a.localeCompare(b, 'pt-BR'),
      ),
    [celulas],
  );

  const bairrosFiltrados = useMemo(() => {
    const q = buscaBairro.trim().toLowerCase();
    if (!q) return bairros;
    return bairros.filter((b) => b.toLowerCase().includes(q));
  }, [bairros, buscaBairro]);

  const filtradas = useMemo(
    () =>
      (celulas ?? []).filter(
        (c) =>
          (filtroTipo === 'todos' || c.tipo === filtroTipo) &&
          (filtroBairros.length === 0 || filtroBairros.includes(c.bairro)),
      ),
    [celulas, filtroTipo, filtroBairros],
  );

  const total = filtradas.reduce((s, c) => s + c.n, 0);

  const porTipo = useMemo(() => {
    const counts = somar(filtradas, 'tipo');
    return TIPOS_ORDEM.map((t) => ({ nome: t, n: counts.get(t) ?? 0 })).filter(
      (x) => x.n > 0,
    );
  }, [filtradas]);

  const porBairro = useMemo(
    () =>
      [...somar(filtradas, 'bairro').entries()]
        .map(([nome, n]) => ({ nome, n }))
        .sort((a, b) => b.n - a.n),
    [filtradas],
  );

  const resumoFiltros = `Tipo: ${filtroTipo === 'todos' ? 'todos' : filtroTipo}; Bairros: ${filtroBairros.length === 0 ? 'todos' : filtroBairros.join(', ')}`;

  return (
    <div className="info-panel report-panel">
      <button className="close" onClick={onClose} aria-label="Fechar">
        <IconeFechar />
      </button>
      <h2>Relatório</h2>

      <button
        className="export-btn"
        onClick={() => window.print()}
        disabled={!celulas}
      >
        Exportar PDF
      </button>

      {erro && (
        <p className="panel-note" role="alert">
          Não foi possível carregar o relatório. Confirme que o backend está
          rodando em {API_URL} e abra o relatório de novo.
        </p>
      )}
      {!celulas && !erro && <p className="panel-note">Carregando relatório…</p>}

      {celulas && (
        <>
          <section className="report-section report-filtros">
            <h3>Filtros</h3>
            <label>
              Tipo
              <select
                value={filtroTipo}
                onChange={(e) => setFiltroTipo(e.target.value)}
              >
                <option value="todos">Todos</option>
                {TIPOS_ORDEM.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>
                Bairros
                {filtroBairros.length > 0 && (
                  <button className="limpar" onClick={() => setFiltroBairros([])}>
                    limpar
                  </button>
                )}
              </span>
              <input
                type="search"
                placeholder="Buscar bairro…"
                value={buscaBairro}
                onChange={(e) => setBuscaBairro(e.target.value)}
              />
              <select
                multiple
                size={10}
                value={filtroBairros}
                onChange={(e) =>
                  setFiltroBairros(
                    [...e.target.selectedOptions].map((o) => o.value),
                  )
                }
              >
                {bairrosFiltrados.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
          </section>

          <p className="print-filtros">{resumoFiltros}</p>

          <section className="report-section total-card">
            <span>Edificações</span>
            <strong>{total.toLocaleString('pt-BR')}</strong>
          </section>

          <section className="report-section">
            <h3>Por tipo</h3>
            <table>
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Quantidade</th>
                </tr>
              </thead>
              <tbody>
                {porTipo.map(({ nome, n }) => (
                  <tr key={nome}>
                    <td>{nome}</td>
                    <td>{n.toLocaleString('pt-BR')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="report-section">
            <h3>Por bairro</h3>
            <table>
              <thead>
                <tr>
                  <th>Bairro</th>
                  <th>Quantidade</th>
                </tr>
              </thead>
              <tbody>
                {porBairro.map(({ nome, n }) => (
                  <tr key={nome}>
                    <td>{nome}</td>
                    <td>{n.toLocaleString('pt-BR')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
