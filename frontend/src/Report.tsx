import { useMemo, useState } from 'react';
import { TIPOS_ORDEM } from './constants';
import type { GeoJsonFC } from './App';

export default function Report({
  data,
  onClose,
}: {
  data: GeoJsonFC;
  onClose: () => void;
}) {
  const [filtroTipo, setFiltroTipo] = useState('todos');
  const [filtroBairro, setFiltroBairro] = useState('todos');

  const bairros = useMemo(() => {
    const nomes = new Set<string>();
    for (const f of data.features) {
      const b = f.properties['bairro'];
      if (typeof b === 'string' && b) nomes.add(b);
    }
    return [...nomes].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  }, [data]);

  const filtradas = useMemo(
    () =>
      data.features.filter((f) => {
        const p = f.properties;
        if (
          filtroTipo !== 'todos' &&
          String(p['tipo'] ?? 'desconhecido') !== filtroTipo
        )
          return false;
        if (filtroBairro !== 'todos' && p['bairro'] !== filtroBairro)
          return false;
        return true;
      }),
    [data, filtroTipo, filtroBairro],
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
      const b = String(f.properties['bairro'] ?? 'Não informado');
      counts.set(b, (counts.get(b) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([nome, n]) => ({ nome, n }))
      .sort((a, b) => b.n - a.n);
  }, [filtradas]);

  return (
    <div className="info-panel report-panel">
      <button className="close" onClick={onClose} aria-label="Fechar">
        ×
      </button>
      <h2>Relatório</h2>

      <label className="filtro">
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

      <label className="filtro">
        Bairro
        <select
          value={filtroBairro}
          onChange={(e) => setFiltroBairro(e.target.value)}
        >
          <option value="todos">Todos</option>
          {bairros.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </label>

      <p className="total">
        Edificações: {filtradas.length.toLocaleString('pt-BR')}
      </p>

      <h3>Por tipo</h3>
      <table>
        <tbody>
          {porTipo.map(({ nome, n }) => (
            <tr key={nome}>
              <td>{nome}</td>
              <td>{n.toLocaleString('pt-BR')}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Por bairro</h3>
      <table>
        <tbody>
          {porBairro.map(({ nome, n }) => (
            <tr key={nome}>
              <td>{nome}</td>
              <td>{n.toLocaleString('pt-BR')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
