/**
 * Atlas Urbano de Paulo Afonso — Inicialização do Mapa e Camadas Base
 */

import { CONFIG } from './config.js';

export class MapManager {
  constructor(containerId = 'map') {
    this.containerId = containerId;
    this.canvasRenderer = L.canvas({ padding: 0.5 });
    this.map = null;
    this.baseLayers = {};
    this.overlayLayers = {};
    this.layerControl = null;

    this.initMap();
    this.initBaseLayers();
  }

  initMap() {
    this.map = L.map(this.containerId, {
      center: CONFIG.MAP_CENTER,
      zoom: CONFIG.MAP_DEFAULT_ZOOM,
      preferCanvas: true,
      zoomControl: true
    });

    L.control.scale({ metric: true, imperial: false }).addTo(this.map);
  }

  initBaseLayers() {
    const googleHybrid = L.tileLayer(
      'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        attribution: '&copy; Google'
      }
    ).addTo(this.map);

    const googleSatellite = L.tileLayer(
      'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        attribution: '&copy; Google'
      }
    );

    const esriSatellite = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: '&copy; Esri, Maxar'
      }
    );

    const osmStandard = L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
      }
    );

    this.baseLayers = {
      'Google Satélite + Rótulos': googleHybrid,
      'Google Satélite': googleSatellite,
      'Esri Satélite': esriSatellite,
      'OpenStreetMap': osmStandard
    };
  }

  setupLayerControl(overlays) {
    this.overlayLayers = overlays;
    this.layerControl = L.control.layers(this.baseLayers, this.overlayLayers, {
      collapsed: false
    }).addTo(this.map);
  }
}
