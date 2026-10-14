export const TIPOS_ORDEM = [
  'residencial',
  'comercial',
  'servico',
  'religioso',
  'institucional',
  'hospedagem',
  'agropecuario',
  'desconhecido',
] as const;

export const TIPO_CORES: Record<string, [number, number, number, number]> = {
  residencial: [25, 118, 210, 210],
  comercial: [230, 57, 70, 210],
  servico: [255, 143, 0, 210],
  religioso: [126, 87, 194, 210],
  institucional: [0, 188, 212, 210],
  hospedagem: [76, 175, 80, 210],
  agropecuario: [139, 195, 74, 210],
  desconhecido: [158, 158, 158, 190],
};

export function corDoTipo(tipo: unknown): [number, number, number, number] {
  const t = typeof tipo === 'string' ? tipo : 'desconhecido';
  return TIPO_CORES[t] ?? TIPO_CORES.desconhecido;
}

export const FONTE_PONTO = 'QG/CNEFE';

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

/** GET JSON com novas tentativas (o backend pode estar subindo). */
export async function fetchJson(
  url: string,
  attempts: number,
  signal?: AbortSignal,
): Promise<any> {
  let lastErr: unknown = null;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const res = await fetch(url, { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      if (signal?.aborted) throw err;
      lastErr = err;
      if (attempt < attempts) await new Promise((r) => setTimeout(r, 2000));
    }
  }
  throw lastErr;
}