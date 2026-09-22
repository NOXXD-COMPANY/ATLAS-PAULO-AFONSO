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