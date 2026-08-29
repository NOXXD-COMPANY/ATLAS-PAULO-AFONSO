/**
 * Atlas Urbano de Paulo Afonso — Configurações Gerais
 */

export const CONFIG = {
  // Configuração de Log
  LOG_LEVEL: 'INFO',

  // Caminhos dos dados processados
  DATA_PATHS: {
    BUILDINGS: '../data/processed/edificacoes_com_cnfe.geojson',
    POINTS: '../data/processed/cnfe_pontos.geojson',
    STATS: '../data/processed/estatisticas_bairros.json'
  },

  // Coordenadas iniciais (Paulo Afonso - BA)
  MAP_CENTER: [-9.4046, -38.2145],
  MAP_DEFAULT_ZOOM: 15,

  // Paleta de cores por espécie de endereço CNFE
  ESPECIE_COLORS: {
    '1': { fill: '#3b82f6', stroke: '#2563eb', label: 'Domicílio particular' },
    '2': { fill: '#a855f7', stroke: '#7c3aed', label: 'Domicílio coletivo' },
    '3': { fill: '#22c55e', stroke: '#16a34a', label: 'Estab. agropecuário' },
    '4': { fill: '#eab308', stroke: '#ca8a04', label: 'Estab. de ensino' },
    '5': { fill: '#ef4444', stroke: '#dc2626', label: 'Estab. de saúde' },
    '6': { fill: '#ec4899', stroke: '#db2777', label: 'Religioso / outros' },
    '7': { fill: '#f97316', stroke: '#ea580c', label: 'Em construção / reforma' },
    '8': { fill: '#94a3b8', stroke: '#64748b', label: 'Outro tipo' }
  },

  // Cores por fonte do Overture Maps
  SOURCE_COLORS: {
    google:    { fill: '#f59e0b', stroke: '#d97706', label: 'Google Open Buildings' },
    microsoft: { fill: '#3b82f6', stroke: '#2563eb', label: 'Microsoft ML Buildings' },
    other:     { fill: '#8b5cf6', stroke: '#7c3aed', label: 'Outro' }
  },

  // Estilo para edificação sem match (sem endereço CNEFE)
  // Grafite bem escuro com borda preta — bem visível e distinto das espécies coloridas.
  NO_MATCH_STYLE: {
    fill: '#4b5563',
    stroke: '#000000'
  }
};
