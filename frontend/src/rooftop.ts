import type { Theme } from './constants';

export type RooftopConfidence = 'alta' | 'media' | 'baixa' | 'nenhuma';

export const ROOFTOP_CONFIDENCES: RooftopConfidence[] = ['alta', 'media', 'baixa', 'nenhuma'];

export interface RooftopOptions {
  showPoints: boolean;
  showPolygons: boolean;
  confiancas: ReadonlySet<RooftopConfidence>;
  onlyChanged: boolean;
}

export interface RooftopSelection {
  kind: 'point' | 'polygon';
  id: string;
  properties: Record<string, unknown>;
}

export function defaultRooftopOptions(): RooftopOptions {
  return {
    showPoints: true,
    showPolygons: true,
    confiancas: new Set(ROOFTOP_CONFIDENCES),
    onlyChanged: false,
  };
}

export function corDaConfianca(confianca: unknown, theme: Theme = 'dark'): string {
  const light = theme === 'light';
  switch (confianca) {
    case 'alta': return light ? '#15803d' : '#22c55e';
    case 'media': return light ? '#a16207' : '#eab308';
    case 'baixa': return light ? '#b91c1c' : '#ef4444';
    default: return light ? '#475569' : '#94a3b8';
  }
}

export function rotuloDaConfianca(confianca: unknown): string {
  switch (confianca) {
    case 'alta': return 'Alta';
    case 'media': return 'Média';
    case 'baixa': return 'Baixa';
    default: return 'Sem prédio';
  }
}
