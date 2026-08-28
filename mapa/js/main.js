/**
 * Atlas Urbano de Paulo Afonso — Ponto de Entrada (Main Bootstrapper)
 */

import { CONFIG } from './config.js';
import { MapManager } from './map.js';
import { LayerManager } from './layers.js';
import { UIManager } from './ui.js';

async function bootstrap() {
  const loadingScreen = document.getElementById('loading-screen');
  const loadingText   = document.getElementById('loading-text');

  try {
    // 1. Inicializa o mapa base
    const mapManager = new MapManager('map');
    const layerManager = new LayerManager(mapManager);

    // 2. Carrega Edificações (Overture Maps)
    loadingText.textContent = 'Carregando 55k territórios de edificações (Overture Maps)…';
    const resBld = await fetch(CONFIG.DATA_PATHS.BUILDINGS);
    if (!resBld.ok) throw new Error('Falha ao baixar edificações GeoJSON');
    const buildingsData = await resBld.json();

    // 3. Carrega Pontos de Endereço (CNEFE / IBGE)
    loadingText.textContent = 'Carregando 62k pontos de endereços (CNEFE / IBGE)…';
    const resPts = await fetch(CONFIG.DATA_PATHS.POINTS);
    if (!resPts.ok) throw new Error('Falha ao baixar pontos CNEFE');
    const pointsData = await resPts.json();

    // 4. Registra dados brutos no LayerManager
    layerManager.setRawData(buildingsData, pointsData);

    const buildingsLayer = layerManager.createBuildingsLayer(buildingsData);
    buildingsLayer.addTo(mapManager.map);

    const pointsLayer = layerManager.createPointsLayer(pointsData);
    pointsLayer.addTo(mapManager.map);

    // 5. Inicializa Interface de Usuário com Filtros de Debug
    const uiManager = new UIManager(mapManager, layerManager);

    // 6. Configura controle mestre de camadas Leaflet
    mapManager.setupLayerControl({
      'Territórios de Edificações (Overture)': buildingsLayer,
      'Pontos de Endereço (CNEFE)': pointsLayer
    });

    // 7. Carrega Estatísticas dos Bairros
    try {
      const resStats = await fetch(CONFIG.DATA_PATHS.STATS);
      if (resStats.ok) {
        const statsData = await resStats.json();
        uiManager.populateStatsTable(statsData);
      }
    } catch (e) {
      console.warn('Estatísticas de bairros não carregadas:', e);
    }

    // 8. Atualiza cabeçalho de debug e encerra loading
    uiManager.updateHeaderStats(
      buildingsData.features.length,
      pointsData.features.length
    );

    loadingScreen.style.display = 'none';

  } catch (error) {
    loadingText.textContent = `Erro ao carregar dados: ${error.message}`;
    loadingText.style.color = '#ef4444';
    console.error(error);
  }
}

// Inicializa quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', bootstrap);
