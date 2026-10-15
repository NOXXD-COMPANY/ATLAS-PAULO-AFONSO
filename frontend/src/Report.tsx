import { useEffect, useMemo, useState } from 'react';
import { TIPOS_ORDEM } from './constants';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';
type Stats = { total: number; by_tipo: Record<string, number>; by_bairro: Record<string, number> };

function normalizarBairro(nome: string): string {
  return nome.replace(/\s+\d+\s*$/, '').trim() || nome;
}

async function fetchStats(params: URLSearchParams, signal?: AbortSignal): Promise<Stats> {
  const response = await fetch(`${API_URL}/api/stats?${params}`, { signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

export default function Report({ onClose }: { onClose: () => void }) {
  const [filtroTipo, setFiltroTipo] = useState('todos');
  const [filtroBairros, setFiltroBairros] = useState<string[]>([]);
  const [buscaBairro, setBuscaBairro] = useState('');
  const [base, setBase] = useState<Stats | null>(null);
  const [stats, setStats] = useState<{ key: string; value: Stats } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const bairros = useMemo(() => {
    const counts = new Map<string, number>();
    for (const [raw, count] of Object.entries(base?.by_bairro ?? {})) {
      const label = normalizarBairro(raw);
      counts.set(label, (counts.get(label) ?? 0) + count);
    }
    return [...counts.keys()].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  }, [base]);

  const bairrosFiltrados = useMemo(() => {
    const q = buscaBairro.trim().toLowerCase();
    return q ? bairros.filter((b) => b.toLowerCase().includes(q)) : bairros;
  }, [bairros, buscaBairro]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({ em_cobertura: 'true' });
    fetchStats(params, controller.signal)
      .then((result) => { setBase(result); })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Erro ao carregar relatório');
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!base) return;
    const controller = new AbortController();
    const isDefault = filtroTipo === 'todos' && filtroBairros.length === 0;
    if (isDefault) return () => controller.abort();

    const key = `${filtroTipo}|${[...filtroBairros].sort().join('|')}`;
    const params = new URLSearchParams({ em_cobertura: 'true' });
    if (filtroTipo !== 'todos') params.set('tipo', filtroTipo);
    if (filtroBairros.length) {
      const rawNames = Object.keys(base.by_bairro).filter((raw) => filtroBairros.includes(normalizarBairro(raw)));
      rawNames.forEach((bairro) => params.append('bairro', bairro));
    }
    fetchStats(params, controller.signal)
      .then((result) => {
        setError(null);
        setStats({ key, value: result });
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        setError(err instanceof Error ? err.message : 'Erro ao carregar relatório');
      });
    return () => controller.abort();
  }, [base, filtroTipo, filtroBairros]);

  const isDefault = filtroTipo === 'todos' && filtroBairros.length === 0;
  const statsKey = `${filtroTipo}|${[...filtroBairros].sort().join('|')}`;
  const visibleStats = isDefault ? base : stats?.key === statsKey ? stats.value : null;
  const porTipo = TIPOS_ORDEM
    .map((nome) => ({ nome, n: visibleStats?.by_tipo?.[nome] ?? 0 }))
    .filter((item) => item.n > 0);
  const porBairro = Object.entries(visibleStats?.by_bairro ?? {})
    .reduce((result, [raw, n]) => {
      const nome = normalizarBairro(raw);
      const current = result.get(nome) ?? 0;
      result.set(nome, current + n);
      return result;
    }, new Map<string, number>());
  const resumoFiltros = `Tipo: ${filtroTipo === 'todos' ? 'todos' : filtroTipo}; Bairros: ${filtroBairros.length === 0 ? 'todos' : filtroBairros.join(', ')}`;

  return (
    <div className="info-panel report-panel">
      <button className="close" onClick={onClose} aria-label="Fechar">×</button>
      <h2>Relatório</h2>
      <button className="export-btn" onClick={() => window.print()}>Exportar PDF</button>
      <section className="report-section report-filtros">
        <h3>Filtros</h3>
        <label>
          Tipo
          <select value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
            <option value="todos">Todos</option>
            {TIPOS_ORDEM.map((tipo) => <option key={tipo} value={tipo}>{tipo}</option>)}
          </select>
        </label>
        <label>
          <span>
            Bairros
            {filtroBairros.length > 0 && <button className="limpar" onClick={() => setFiltroBairros([])}>limpar</button>}
          </span>
          <input type="search" placeholder="Buscar bairro…" value={buscaBairro} onChange={(e) => setBuscaBairro(e.target.value)} />
          <select multiple size={10} value={filtroBairros} onChange={(e) => setFiltroBairros([...e.target.selectedOptions].map((o) => o.value))}>
            {bairrosFiltrados.map((bairro) => <option key={bairro} value={bairro}>{bairro}</option>)}
          </select>
        </label>
      </section>
      <p className="print-filtros">{resumoFiltros}</p>
      {error && <p role="alert">Erro ao carregar: {error}</p>}
      <section className="report-section total-card">
        <span>Edificações</span>
        <strong>{(visibleStats?.total ?? 0).toLocaleString('pt-BR')}</strong>
      </section>
      <section className="report-section">
        <h3>Por tipo</h3>
        <table><thead><tr><th>Tipo</th><th>Quantidade</th></tr></thead>
          <tbody>{porTipo.map(({ nome, n }) => <tr key={nome}><td>{nome}</td><td>{n.toLocaleString('pt-BR')}</td></tr>)}</tbody>
        </table>
      </section>
      <section className="report-section">
        <h3>Por bairro</h3>
        <table><thead><tr><th>Bairro</th><th>Quantidade</th></tr></thead>
          <tbody>{[...porBairro.entries()].sort((a, b) => b[1] - a[1]).map(([nome, n]) => <tr key={nome}><td>{nome}</td><td>{n.toLocaleString('pt-BR')}</td></tr>)}</tbody>
        </table>
      </section>
    </div>
  );
}
