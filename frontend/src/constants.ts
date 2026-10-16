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

export type Tipo = (typeof TIPOS_ORDEM)[number];

export const TIPO_LABEL: Record<string, string> = {
  residencial: 'Residencial',
  comercial: 'Comercial',
  servico: 'Serviço',
  religioso: 'Religioso',
  institucional: 'Institucional',
  hospedagem: 'Hospedagem',
  agropecuario: 'Agropecuário',
  desconhecido: 'Não identificado',
};

// Cores de sistema do modo escuro da Apple: saturadas o bastante para ler
// sobre o mapa escuro e distintas entre si.
export const TIPO_CORES: Record<string, string> = {
  residencial: '#0A84FF',
  comercial: '#FF453A',
  servico: '#FF9F0A',
  religioso: '#BF5AF2',
  institucional: '#64D2FF',
  hospedagem: '#30D158',
  agropecuario: '#FFD60A',
  desconhecido: '#8E8E93',
};

export function corDoTipo(tipo: unknown): string {
  return (typeof tipo === 'string' && TIPO_CORES[tipo]) || TIPO_CORES.desconhecido;
}

export function rotuloDoTipo(tipo: unknown): string {
  return (typeof tipo === 'string' && TIPO_LABEL[tipo]) || TIPO_LABEL.desconhecido;
}

export const FONTE_PONTO = 'QG/CNEFE';

export const ALTURA_PAVIMENTO_M = 3;

// Sem número de pavimentos (a maioria), cada uso recebe uma altura típica:
// casas térreas baixas, templos e prédios públicos mais altos. Com todos os
// prédios em 3D, uma altura única viraria um paredão uniforme.
export const ALTURA_PADRAO_POR_TIPO: Record<string, number> = {
  residencial: 4,
  comercial: 5,
  servico: 5,
  religioso: 9,
  institucional: 7,
  hospedagem: 7,
  agropecuario: 5,
  desconhecido: 4,
};

/** Altura em metros e se ela é estimada (sem número de pavimentos). */
export function alturaDoPredio(tipo: unknown, pavimentos: unknown): { metros: number; estimada: boolean } {
  const n = Number(pavimentos);
  if (Number.isFinite(n) && n > 0) return { metros: n * ALTURA_PAVIMENTO_M, estimada: false };
  const padrao = (typeof tipo === 'string' && ALTURA_PADRAO_POR_TIPO[tipo]) || ALTURA_PADRAO_POR_TIPO.desconhecido;
  return { metros: padrao, estimada: true };
}
