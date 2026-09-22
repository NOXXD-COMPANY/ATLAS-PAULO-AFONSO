import { useMemo, useState } from 'react';
import { TIPOS_ORDEM } from './constants';
import type { GeoJsonFC } from './App';

function normalizarBairro(nome: string): string {
  return nome.replace(/\s+\d+\s*$/, '').trim() || nome;
}

function bairroDe(f: GeoJsonFC['features'][number]): string {
  const b = f.properties['bairro'];
  return typeof b === 'string' && b ? normalizarBairro(b) : 'Não informado';
}

export default function Report({
  data,
  onClose,
}: {
  data: GeoJsonFC;
  onClose: () => void;
}) {
  const [filtroTipo, setFiltroTipo] = useState('todos');
  const [filtroBairros, setFiltroBairros] = useState<string[]>([]);
  const [buscaBairro, setBuscaBairro] = useState('');

  const bairros = useMemo(() => {
    const nomes = new Set<string>();
    for (const f of data.features) nomes.add(bairroDe(f));
    return [...nomes].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  }, [data]);

  const bairrosFiltrados = useMemo(() => {
    const q = buscaBairro.trim().toLowerCase();
    if (!q) return bairros;
    return bairros.filter((b) => b.toLowerCase().includes(q));
  }, [bairros, buscaBairro]);

  const filtradas = useMemo(
    () =>
      data.features.filter((f) => {
        if (
          filtroTipo !== 'todos' &&
          String(f.properties['tipo'] ?? 'desconhecido') !== filtroTipo
        )
          return false;
        if (filtroBairros.length > 0 && !filtroBairros.includes(bairroDe(f)))
          return false;
        return true;
      }),
    [data, filtroTipo, filtroBairros],
  );

  const porTipo = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of filtradas) {
      const t = String(f.properties['tipo'] ?? 'desconhecido');
      counts.set(t, (counts.get(t) ?? 0) + 1);
    }
    return TIPOS_ORDEM.map((t) => ({ nome: t, n: counts.get(t) ?? 0 })).filter(
      (x) => x.n > 0,
    );
  }, [filtradas]);

  const porBairro = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of filtradas) {
      const b = bairroDe(f);
      counts.set(b, (counts.get(b) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([nome, n]) => ({ nome, n }))
      .sort((a, b) => b.n - a.n);
  }, [filtradas]);

  const resumoFiltros = `Tipo: ${filtroTipo === 'todos' ? 'todos' : filtroTipo}; Bairros: ${filtroBairros.length === 0 ? 'todos' : filtroBairros.join(', ')}`;

  return (
    <div className="info-panel report-panel">
      <button className="close" onClick={onClose} aria-label="Fechar">
        ×
      </button>
      <h2>Relatório</h2>

      <button className="export-btn" onClick={() => window.print()}>
        Exportar PDF
      </button>

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
        <strong>{filtradas.length.toLocaleString('pt-BR')}</strong>
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

    </div>
  );
}
