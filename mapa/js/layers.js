/**
 * Atlas Urbano de Paulo Afonso — Camadas GeoJSON, Estilização, Popups e Filtros de Debug
 */

import { CONFIG } from './config.js';

export class LayerManager {
  constructor(mapManager) {
    this.mapManager = mapManager;
    this.buildingsLayer = null;
    this.pointsLayer = null;
    this.rawPointsData = null;
    this.rawBuildingsData = null;

    // Estado visual e filtros de diagnóstico/debug
    this.state = {
      tolerance: '10m',          // '0m' | '5m' | '10m'
      buildingColorMode: 'cnfe',    // 'cnfe' | 'source'
      pointColorMode: 'status',     // 'status' | 'especie'
    };

    this.filters = {
      // Toggles mestres
      showBuildings: true,
      showPoints: true,

      // Filtros dos Pontos (CNEFE / IBGE)
      pointDistances: {
        exact: true,    // 0m (No telhado)
        buffer: true,   // <= 10m (Calçada/Testada)
        outside: true   // > 10m (Fora)
      },
      pointSpecies: {
        '1': true, '2': true, '3': true, '4': true,
        '5': true, '6': true, '7': true, '8': true
      },

      // Filtros das Edificações (Overture Maps)
      buildingMatch: {
        matched: true,    // Com endereço CNFE
        unmatched: true   // Sem endereço CNFE
      },
      buildingSources: {
        google: true,
        microsoft: true,
        other: true
      }
    };
  }

  setRawData(buildingsData, pointsData) {
    this.rawBuildingsData = buildingsData;
    this.rawPointsData = pointsData;
  }

  // ── Filtro e contagem de endereços por tolerância ──
  getFilteredAddresses(feature) {
    const addresses = feature.properties.cnfe_enderecos || [];
    return addresses.filter(a => {
      if (this.state.tolerance === '0m') return a.dist_m === 0;
      if (this.state.tolerance === '5m') return a.dist_m <= 5.0;
      return a.dist_m <= 10.0;
    });
  }

  // ── Verificação de Visibilidade da Edificação (Overture) ──
  isBuildingVisible(feature) {
    if (!this.filters.showBuildings) return false;

    // Filtro por match
    const hasCnfe = this.getFilteredAddresses(feature).length > 0;
    if (hasCnfe && !this.filters.buildingMatch.matched) return false;
    if (!hasCnfe && !this.filters.buildingMatch.unmatched) return false;

    // Filtro por fonte Overture
    const src = (feature.properties.sources && feature.properties.sources[0]) 
      ? feature.properties.sources[0].provider : 'other';
    if (src === 'google' && !this.filters.buildingSources.google) return false;
    if (src === 'microsoft' && !this.filters.buildingSources.microsoft) return false;

    return true;
  }

  // ── Estilo dos Polígonos de Edificações (Overture) ──
  getBuildingStyle(feature) {
    if (!this.isBuildingVisible(feature)) {
      return { fillOpacity: 0, opacity: 0, weight: 0 };
    }

    const filteredAddrs = this.getFilteredAddresses(feature);
    const count = filteredAddrs.length;
    const conf = (feature.properties.sources && feature.properties.sources[0]) 
      ? feature.properties.sources[0].confidence : null;

    let fillColor, strokeColor, fillOpacity;

    if (this.state.buildingColorMode === 'cnfe') {
      if (count > 0) {
        const especie = String(filteredAddrs[0].especie || '1');
        const pal = CONFIG.ESPECIE_COLORS[especie] || CONFIG.ESPECIE_COLORS['8'];
        fillColor = pal.fill;
        strokeColor = pal.stroke;
        fillOpacity = 0.6 + Math.min(count, 5) * 0.07;
      } else {
        fillColor = CONFIG.NO_MATCH_STYLE.fill;
        strokeColor = CONFIG.NO_MATCH_STYLE.stroke;
        fillOpacity = 0.15;
      }
    } else {
      const src = (feature.properties.sources && feature.properties.sources[0]) 
        ? feature.properties.sources[0].provider : 'other';
      const pal = CONFIG.SOURCE_COLORS[src] || CONFIG.SOURCE_COLORS.other;
      fillColor = pal.fill;
      strokeColor = pal.stroke;
      fillOpacity = conf != null ? 0.3 + conf * 0.5 : 0.6;
    }

    return {
      color: strokeColor,
      weight: 1,
      fillColor: fillColor,
      fillOpacity: fillOpacity,
      opacity: 0.85
    };
  }

  // ── Popup da Edificação (Overture) ──
  bindBuildingPopup(feature, layer) {
    layer.on('click', () => {
      const props = feature.properties || {};
      const src = (props.sources && props.sources[0]) || {};
      const conf = src.confidence != null ? `${(src.confidence * 100).toFixed(1)}%` : '—';
      const provider = src.provider === 'google' ? 'Google Open Buildings'
                     : src.provider === 'microsoft' ? 'Microsoft ML Buildings'
                     : src.provider || '—';
      const areaM2 = props.area_m2 ? `${props.area_m2.toLocaleString('pt-BR')} m²` : '—';
      const filtered = this.getFilteredAddresses(feature);

      let badge = filtered.length > 0
        ? `<span class="popup-badge badge-exact">${filtered.length} endereço(s) CNEFE vinculado(s)</span>`
        : `<span class="popup-badge badge-none">Sem endereço CNEFE na tolerância (${this.state.tolerance})</span>`;

      let html = `
        <div class="popup-title">Território / Edificação (Overture Maps)</div>
        ${badge}
        <div class="popup-row"><span class="popup-label">Fonte Overture</span><span class="popup-value">${provider}</span></div>
        <div class="popup-row"><span class="popup-label">Confiança IA</span><span class="popup-value">${conf}</span></div>
        <div class="popup-row"><span class="popup-label">Área Telhado</span><span class="popup-value"><strong>${areaM2}</strong> (SIRGAS2000)</span></div>
        <div class="popup-row"><span class="popup-label">Bairro / Local</span><span class="popup-value">${props.cnfe_localidade || '—'}</span></div>
      `;

      if (filtered.length > 0) {
        html += `<div style="margin-top:8px;font-weight:600;font-size:0.78rem;">Endereços CNEFE colididos:</div>`;
        const max = Math.min(filtered.length, 6);
        for (let i = 0; i < max; i++) {
          const item = filtered[i];
          const distLabel = item.dist_m === 0 ? '0m (exato)' : `${item.dist_m}m`;
          html += `
            <div class="popup-card">
              <div class="addr">${item.endereco || '—'} · <span style="color:#2563eb;">${distLabel}</span></div>
              ${item.complemento ? `<div class="desc">${item.complemento}</div>` : ''}
              <div class="desc">${item.localidade || ''} · CEP ${item.cep || '—'}</div>
              ${item.estabelecimento ? `<div class="desc">${item.estabelecimento}</div>` : ''}
              <span class="tag-especie">${item.especie_desc || 'Outro'}</span>
            </div>
          `;
        }
        if (filtered.length > max) {
          html += `<div style="font-size:0.72rem;color:#6b7280;margin-top:4px;">+ ${filtered.length - max} endereço(s) adicional(is)</div>`;
        }
      }

      layer.bindPopup(html, { maxWidth: 320 }).openPopup();
    });
  }

  // ── Verificação de Visibilidade do Ponto (CNEFE) ──
  isPointVisible(feature) {
    if (!this.filters.showPoints) return false;

    const dist = feature.properties.dist_to_building_m;
    if (dist === 0 && !this.filters.pointDistances.exact) return false;
    if (dist > 0 && dist <= 10.0 && !this.filters.pointDistances.buffer) return false;
    if (dist > 10.0 && !this.filters.pointDistances.outside) return false;

    const especie = String(feature.properties.COD_ESPECIE || '8');
    if (this.filters.pointSpecies[especie] === false) return false;

    return true;
  }

  // ── Estilo dos Marcadores de Ponto (CNEFE) ──
  getPointMarkerOptions(feature) {
    const dist = feature.properties.dist_to_building_m;
    const especie = String(feature.properties.COD_ESPECIE || '1');
    let fillColor, strokeColor;

    if (this.state.pointColorMode === 'status') {
      if (dist === 0) {
        fillColor = '#10b981'; // 0m verde
        strokeColor = '#047857';
      } else if (dist <= 10.0) {
        fillColor = '#f59e0b'; // <=10m âmbar
        strokeColor = '#d97706';
      } else {
        fillColor = '#ef4444'; // >10m vermelho
        strokeColor = '#b91c1c';
      }
    } else {
      const pal = CONFIG.ESPECIE_COLORS[especie] || CONFIG.ESPECIE_COLORS['8'];
      fillColor = pal.fill;
      strokeColor = pal.stroke;
    }

    return {
      renderer: this.mapManager.canvasRenderer,
      radius: dist <= 10 ? 4 : 3,
      fillColor: fillColor,
      color: strokeColor,
      weight: 1,
      opacity: 0.9,
      fillOpacity: dist <= 10 ? 0.9 : 0.6
    };
  }

  // ── Popup do Ponto CNEFE ──
  bindPointPopup(feature, layer) {
    layer.on('click', () => {
      const props = feature.properties || {};
      const dist = props.dist_to_building_m;

      let badge = '';
      if (dist === 0) {
        badge = `<span class="popup-badge badge-exact">✓ No Telhado Overture (0m)</span>`;
      } else if (dist <= 10.0) {
        badge = `<span class="popup-badge badge-buffer">⚡ Testada / Lote (${dist}m)</span>`;
      } else {
        badge = `<span class="popup-badge badge-none">✗ Fora do Telhado (>10m)</span>`;
      }

      const html = `
        <div class="popup-title">Ponto de Endereço (CNEFE / IBGE)</div>
        ${badge}
        <div class="popup-row"><span class="popup-label">Distância ao Telhado</span><span class="popup-value"><strong>${dist === 0 ? '0 m' : dist + ' m'}</strong></span></div>
        <div class="popup-row"><span class="popup-label">Logradouro</span><span class="popup-value">${props.LOGRAD_NUM || '—'}</span></div>
        ${props.COMPLEMENTO ? `<div class="popup-row"><span class="popup-label">Complemento</span><span class="popup-value">${props.COMPLEMENTO}</span></div>` : ''}
        <div class="popup-row"><span class="popup-label">Bairro</span><span class="popup-value">${props.DSC_LOCALIDADE || '—'}</span></div>
        <div class="popup-row"><span class="popup-label">CEP</span><span class="popup-value">${props.CEP || '—'}</span></div>
        ${props.DSC_ESTABELECIMENTO ? `<div class="popup-row"><span class="popup-label">Estabelecimento</span><span class="popup-value">${props.DSC_ESTABELECIMENTO}</span></div>` : ''}
        <div class="popup-row"><span class="popup-label">Setor Censitário</span><span class="popup-value">${props.COD_SETOR || '—'}</span></div>
        <div style="margin-top:6px;"><span class="tag-especie">${props.especie_desc || 'Outro'}</span></div>
      `;

      layer.bindPopup(html, { maxWidth: 300 }).openPopup();
    });
  }

  // ── Criação das Camadas GeoJSON ──
  createBuildingsLayer(geojsonData) {
    this.rawBuildingsData = geojsonData;
    this.buildingsLayer = L.geoJSON(geojsonData, {
      style: (feature) => this.getBuildingStyle(feature),
      onEachFeature: (feature, layer) => this.bindBuildingPopup(feature, layer),
      renderer: this.mapManager.canvasRenderer
    });
    return this.buildingsLayer;
  }

  createPointsLayer(geojsonData) {
    this.rawPointsData = geojsonData;
    this.pointsLayer = L.geoJSON(geojsonData, {
      filter: (feature) => this.isPointVisible(feature),
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, this.getPointMarkerOptions(feature));
      },
      onEachFeature: (feature, layer) => this.bindPointPopup(feature, layer)
    });
    return this.pointsLayer;
  }

  // ── Atualização visual de estilos e filtros ──
  refreshStyles() {
    if (this.buildingsLayer) {
      this.buildingsLayer.setStyle((feature) => this.getBuildingStyle(feature));
    }
    if (this.pointsLayer && this.rawPointsData) {
      this.pointsLayer.clearLayers();
      const filtered = {
        type: 'FeatureCollection',
        features: this.rawPointsData.features.filter(f => this.isPointVisible(f))
      };
      this.pointsLayer.addData(filtered);
    }
  }
}
