// Constantes de visualização: cores por tipo de uso da edificação.

export const TIPOS_ORDEM = [
  'residencial',
  'comercial',
  'servico',
  'religioso',
  'institucional',
  'hospedagem',
  'agropecuario',
  'misto',
  'desconhecido',
] as const;

export const TIPO_CORES: Record<string, [number, number, number, number]> = {
  residencial: [25, 118, 210, 210], // azul
  comercial: [230, 57, 70, 210], // vermelho
  servico: [255, 143, 0, 210], // laranja
  religioso: [126, 87, 194, 210], // roxo
  institucional: [0, 188, 212, 210], // ciano
  hospedagem: [76, 175, 80, 210], // verde
  agropecuario: [139, 195, 74, 210], // verde-claro
  misto: [255, 193, 7, 210], // amarelo
  desconhecido: [158, 158, 158, 190], // cinza neutro
};

export function corDoTipo(tipo: unknown): [number, number, number, number] {
  const t = typeof tipo === 'string' ? tipo : 'desconhecido';
  return TIPO_CORES[t] ?? TIPO_CORES.desconhecido;
}