/**
 * Atlas Urbano de Paulo Afonso — Componentes de Interface do Usuário (UI) & Filtros na Legenda
 */

import { CONFIG } from './config.js';

export class UIManager {
  constructor(mapManager, layerManager) {
    this.mapManager = mapManager;
    this.layerManager = layerManager;

    this.initHeaderButtons();
    this.initControlPanel();
    this.initInteractiveLegend();
  }

  // ── Painel de Configuração Rápida / Hitbox ──
  initControlPanel() {
    const ctrl = L.control({ position: 'topright' });
    ctrl.onAdd = () => {
      const div = L.DomUtil.create('div', 'panel-control');
      div.innerHTML = `
        <div class="panel-title">Diagnóstico & Hitbox</div>
        
        <div class="control-group">
          <label style="font-weight:600;font-size:0.76rem;">Tolerância Hitbox (buffer em metros):</label>
          <input type="number" id="input-tolerance" class="control-select" value="10" min="0" max="100" step="0.5">
          <div style="font-size:0.72rem;color:#6b7280;margin-top:3px;">Digite qualquer distância (até 50m, que é a associação máxima dos dados), ex.: 0, 5, 10, 25m.</div>
        </div>

        <div class="control-group">
          <div class="panel-section-title">Colorir Pontos CNEFE</div>
          <label><input type="radio" name="opt-pt-color" value="status" checked> Status de Distância (0m / ≤buffer / &gt;buffer)</label>
          <label><input type="radio" name="opt-pt-color" value="especie"> Espécie de Uso</label>
        </div>

        <div class="control-group">
          <div class="panel-section-title">Colorir Territórios Overture</div>
          <label><input type="radio" name="opt-bld-color" value="cnfe" checked> Espécie CNEFE vinculada</label>
          <label><input type="radio" name="opt-bld-color" value="source"> Fonte (Google / Microsoft)</label>
        </div>
      `;
      L.DomEvent.disableClickPropagation(div);

      // Eventos
      const tolInput = div.querySelector('#input-tolerance');
      const applyTolerance = () => {
        const value = parseFloat(tolInput.value);
        if (isNaN(value) || value < 0) {
          tolInput.value = this.layerManager.state.tolerance;
          return;
        }
        this.layerManager.state.tolerance = value;
        this.updateHeaderStats();
        this.layerManager.refreshStyles();
      };
      tolInput.addEventListener('change', applyTolerance);
      tolInput.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') applyTolerance();
      });

      div.querySelectorAll('input[name="opt-pt-color"]').forEach(r => {
        r.addEventListener('change', (e) => {
          this.layerManager.state.pointColorMode = e.target.value;
          this.layerManager.refreshStyles();
        });
      });

      div.querySelectorAll('input[name="opt-bld-color"]').forEach(r => {
        r.addEventListener('change', (e) => {
          this.layerManager.state.buildingColorMode = e.target.value;
          this.layerManager.refreshStyles();
        });
      });

      return div;
    };
    ctrl.addTo(this.mapManager.map);
  }

  // ── Legenda com Filtros Interativos Integrados ──
  initInteractiveLegend() {
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = () => {
      const div = L.DomUtil.create('div', 'panel-legend');

      let especieCheckboxes = '';
      for (const [code, info] of Object.entries(CONFIG.ESPECIE_COLORS)) {
        especieCheckboxes += `
          <label class="legend-filter-item">
            <input type="checkbox" class="chk-pt-species" data-code="${code}" checked>
            <div class="legend-dot" style="background:${info.fill}"></div>
            <span>${info.label}</span>
          </label>
        `;
      }

      div.innerHTML = `
        <div class="panel-title">Legenda & Filtros de Exibição</div>
        
        <!-- SEÇÃO: PONTOS CNEFE -->
        <div class="legend-group">
          <label class="legend-master-label">
            <input type="checkbox" id="chk-master-points" checked>
            <strong>📍 Pontos de Endereço (CNEFE / IBGE)</strong>
          </label>
          
          <div class="legend-subgroup" id="group-points">
            <div class="panel-section-title">Distância ao Telhado</div>
            <label class="legend-filter-item">
              <input type="checkbox" id="chk-dist-exact" checked>
              <div class="legend-dot" style="background:#10b981"></div>
              <span>0m (No telhado / Exato)</span>
            </label>
            <label class="legend-filter-item">
              <input type="checkbox" id="chk-dist-buffer" checked>
              <div class="legend-dot" style="background:#f59e0b"></div>
              <span>Dentro do buffer <em id="lbl-buffer-dist"></em></span>
            </label>
            <label class="legend-filter-item">
              <input type="checkbox" id="chk-dist-outside" checked>
              <div class="legend-dot" style="background:#ef4444"></div>
              <span>Fora do buffer <em id="lbl-outside-dist"></em></span>
            </label>

            <div class="panel-section-title">Espécies de Uso (CNEFE)</div>
            ${especieCheckboxes}
          </div>
        </div>

        <hr style="border:0;border-top:1px solid #e5e7eb;margin:8px 0;">

        <!-- SEÇÃO: TERRITÓRIOS OVERTURE -->
        <div class="legend-group">
          <label class="legend-master-label">
            <input type="checkbox" id="chk-master-bld" checked>
            <strong>🏢 Territórios / Edificações (Overture)</strong>
          </label>
          
          <div class="legend-subgroup" id="group-buildings">
            <div class="panel-section-title">Vínculo com CNEFE</div>
            <label class="legend-filter-item">
              <input type="checkbox" id="chk-bld-matched" checked>
              <div class="legend-swatch" style="background:linear-gradient(90deg,#3b82f6,#a855f7,#22c55e,#ef4444)"></div>
              <span>Com endereço CNEFE (cor = espécie)</span>
            </label>
            <label class="legend-filter-item">
              <input type="checkbox" id="chk-bld-unmatched" checked>
              <div class="legend-swatch" style="background:${CONFIG.NO_MATCH_STYLE.fill};border:1px solid ${CONFIG.NO_MATCH_STYLE.stroke}"></div>
              <span>Sem endereço CNEFE</span>
            </label>

            <div class="panel-section-title">Fontes Overture</div>
            <label class="legend-filter-item">
              <input type="checkbox" id="chk-src-google" checked>
              <div class="legend-swatch" style="background:${CONFIG.SOURCE_COLORS.google.fill}"></div>
              <span>Google Open Buildings</span>
            </label>
            <label class="legend-filter-item">
              <input type="checkbox" id="chk-src-ms" checked>
              <div class="legend-swatch" style="background:${CONFIG.SOURCE_COLORS.microsoft.fill}"></div>
              <span>Microsoft ML Buildings</span>
            </label>
          </div>
        </div>
      `;

      L.DomEvent.disableClickPropagation(div);
      L.DomEvent.disableScrollPropagation(div);

      this.bindLegendFilterEvents(div);

      return div;
    };
    legend.addTo(this.mapManager.map);
  }

  // ── Vinculação dos Eventos de Filtro da Legenda ──
  bindLegendFilterEvents(container) {
    const lm = this.layerManager;

    // Master Points
    const chkMasterPoints = container.querySelector('#chk-master-points');
    const groupPoints = container.querySelector('#group-points');
    chkMasterPoints.addEventListener('change', (e) => {
      lm.filters.showPoints = e.target.checked;
      groupPoints.style.opacity = e.target.checked ? '1' : '0.4';
      lm.refreshStyles();
    });

    // Distance Filters
    container.querySelector('#chk-dist-exact').addEventListener('change', (e) => {
      lm.filters.pointDistances.exact = e.target.checked;
      lm.refreshStyles();
    });
    container.querySelector('#chk-dist-buffer').addEventListener('change', (e) => {
      lm.filters.pointDistances.buffer = e.target.checked;
      lm.refreshStyles();
    });
    container.querySelector('#chk-dist-outside').addEventListener('change', (e) => {
      lm.filters.pointDistances.outside = e.target.checked;
      lm.refreshStyles();
    });

    // Species Filters
    container.querySelectorAll('.chk-pt-species').forEach(chk => {
      chk.addEventListener('change', (e) => {
        const code = e.target.dataset.code;
        lm.filters.pointSpecies[code] = e.target.checked;
        lm.refreshStyles();
      });
    });

    // Master Buildings
    const chkMasterBld = container.querySelector('#chk-master-bld');
    const groupBuildings = container.querySelector('#group-buildings');
    chkMasterBld.addEventListener('change', (e) => {
      lm.filters.showBuildings = e.target.checked;
      groupBuildings.style.opacity = e.target.checked ? '1' : '0.4';
      lm.refreshStyles();
    });

    // Match Filters
    container.querySelector('#chk-bld-matched').addEventListener('change', (e) => {
      lm.filters.buildingMatch.matched = e.target.checked;
      lm.refreshStyles();
    });
    container.querySelector('#chk-bld-unmatched').addEventListener('change', (e) => {
      lm.filters.buildingMatch.unmatched = e.target.checked;
      lm.refreshStyles();
    });

    // Source Filters
    container.querySelector('#chk-src-google').addEventListener('change', (e) => {
      lm.filters.buildingSources.google = e.target.checked;
      lm.refreshStyles();
    });
    container.querySelector('#chk-src-ms').addEventListener('change', (e) => {
      lm.filters.buildingSources.microsoft = e.target.checked;
      lm.refreshStyles();
    });
  }

  // ── Atualização dos Indicadores no Cabeçalho ──
  updateHeaderStats(bldCount, ptCount) {
    const lm = this.layerManager;
    const blds = lm.rawBuildingsData;
    const pts = lm.rawPointsData;
    const tol = lm.state.tolerance;

    const totalBlds = blds && blds.features ? blds.features.length : 0;
    const totalPts  = pts && pts.features ? pts.features.length : 0;

    if (bldCount !== undefined || totalBlds) {
      document.getElementById('stat-bld-count').textContent = (bldCount !== undefined ? bldCount : totalBlds).toLocaleString('pt-BR');
    }
    if (ptCount !== undefined || totalPts) {
      document.getElementById('stat-pt-count').textContent = (ptCount !== undefined ? ptCount : totalPts).toLocaleString('pt-BR');
    }

    // Legenda dinâmica do buffer
    const bufLabel = document.getElementById('lbl-buffer-dist');
    const outLabel = document.getElementById('lbl-outside-dist');
    if (bufLabel) bufLabel.textContent = `(≤ ${tol}m)`;
    if (outLabel) outLabel.textContent = `(> ${tol}m)`;

    // ── Métricas de veracidade / funcionalidade ──
    // Edificações que têm ≥1 ponto de endereço vinculado dentro do buffer (menor distância)
    let matchedBlds = 0;
    if (totalBlds) {
      matchedBlds = blds.features.filter(f => lm.getFilteredAddresses(f).length > 0).length;
    }
    const bldMatchedPct = totalBlds > 0 ? (matchedBlds / totalBlds * 100).toFixed(1) : '—';

    const elBldMatched = document.getElementById('stat-bld-matched');
    const elBldPct = document.getElementById('stat-bld-matched-pct');
    if (elBldMatched) elBldMatched.textContent = `${matchedBlds.toLocaleString('pt-BR')} / ${totalBlds.toLocaleString('pt-BR')}`;
    if (elBldPct) elBldPct.textContent = `(${bldMatchedPct}%)`;

    // Pontos CNEFE que estão dentro de, ou a menos de `tol` de, um polígono
    let matchedPts = 0;
    if (totalPts) {
      matchedPts = pts.features.filter(f => f.properties.dist_to_building_m <= tol).length;
    }
    const ptMatchedPct = totalPts > 0 ? (matchedPts / totalPts * 100).toFixed(1) : '—';

    const elPtMatched = document.getElementById('stat-pt-matched');
    const elPtPct = document.getElementById('stat-pt-matched-pct');
    if (elPtMatched) elPtMatched.textContent = `${matchedPts.toLocaleString('pt-BR')} / ${totalPts.toLocaleString('pt-BR')}`;
    if (elPtPct) elPtPct.textContent = `(${ptMatchedPct}%)`;

    // Taxa de coincidência ponto↔polígono (média da cobertura nos dois sentidos) p/ buffer
    const matchEl = document.getElementById('stat-match-rate');
    if (matchEl) {
      matchEl.textContent = totalPts > 0
        ? `${ptMatchedPct}% (buffer ${tol}m)`
        : '—';
    }
  }

  // ── Modal de Estatísticas por Bairro ──
  initHeaderButtons() {
    const btnStats = document.getElementById('btn-open-stats');
    const modal = document.getElementById('modal-stats');
    const btnClose = document.getElementById('btn-close-stats');

    if (btnStats && modal && btnClose) {
      btnStats.addEventListener('click', () => { modal.style.display = 'flex'; });
      btnClose.addEventListener('click', () => { modal.style.display = 'none'; });
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.style.display = 'none';
      });
    }
  }

  populateStatsTable(statsData) {
    const tbody = document.getElementById('stats-tbody');
    if (!tbody || !Array.isArray(statsData)) return;

    let html = '';
    statsData.forEach(row => {
      html += `
        <tr>
          <td><strong>${row.bairro}</strong></td>
          <td>${row.edificacoes.toLocaleString('pt-BR')}</td>
          <td>${row.area_total_m2.toLocaleString('pt-BR')}</td>
          <td>${row.area_mediana_m2.toLocaleString('pt-BR')}</td>
          <td>${row.enderecos_cnfe.toLocaleString('pt-BR')}</td>
          <td>${row.domicilios.toLocaleString('pt-BR')}</td>
          <td>${row.saude.toLocaleString('pt-BR')}</td>
          <td>${row.ensino.toLocaleString('pt-BR')}</td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  }
}
