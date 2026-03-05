"use client";

import React, { useState, useEffect } from "react";
import styles from "./LayerPanel.module.css";
import mapboxgl from "mapbox-gl";

interface LayerConfig {
  id: string;
  name: string;
  backendId: string;
  cmap: string;
  min: number;
  max: number;
  nodata?: number;
  legendGradient: string;
}

const LAYERS: LayerConfig[] = [
  {
    id: "ndvi-overlay",
    name: "Vegetation (NDVI)",
    backendId: "ndvi_mean",
    cmap: "YlGn",
    min: 0,
    max: 0.6,
    nodata: -9999,
    legendGradient: "linear-gradient(to right, #ffffe5, #78c679, #004529)"
  },
  {
    id: "albedo-overlay",
    name: "Surface Reflectivity",
    backendId: "albedo_mean",
    cmap: "Greys",
    min: 0,
    max: 0.4,
    nodata: -9999,
    legendGradient: "linear-gradient(to right, #ffffff, #888888, #000000)"
  },
  {
    id: "building-density-overlay",
    name: "Building Density",
    backendId: "building_density_mean",
    cmap: "Purples",
    min: 0,
    max: 1.0,
    nodata: 0,
    legendGradient: "linear-gradient(to right, rgba(242,240,247,0), #9e9ac8, #3f007d)"
  },
  {
    id: "height-overlay",
    name: "Building Height",
    backendId: "height_mean",
    cmap: "YlOrRd",
    min: 0,
    max: 80,
    nodata: 0,
    legendGradient: "linear-gradient(to right, #ffffb2, #fd8d3c, #b10026)"
  },
  {
    id: "road-density-overlay",
    name: "Road Density",
    backendId: "road_density_mean",
    cmap: "Oranges",
    min: 0,
    max: 1.0,
    nodata: 0,
    legendGradient: "linear-gradient(to right, rgba(255,245,235,0), #fd8d3c, #7f2704)"
  },
  {
    id: "sand-overlay",
    name: "Sand Coverage",
    backendId: "sand_mask_fraction",
    cmap: "YlOrBr",
    min: 0,
    max: 1.0,
    nodata: 0,
    legendGradient: "linear-gradient(to right, rgba(255,255,212,0), #fe9929, #993404)"
  },
  {
    id: "water-overlay",
    name: "Water Coverage",
    backendId: "water_mask_full_fraction",
    cmap: "Blues",
    min: 0,
    max: 1.0,
    nodata: 0,
    legendGradient: "linear-gradient(to right, rgba(247,251,255,0), #6baed6, #08306b)"
  }
];

interface LayerPanelProps {
  map: mapboxgl.Map | null;
}

export default function LayerPanel({ map }: LayerPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  
  // Track active layer state. using a Map or object is easier.
  // Record<layerId, { active: boolean, opacity: number }>
  const [layerState, setLayerState] = useState<Record<string, { active: boolean; opacity: number }>>(() => {
    const initial: Record<string, { active: boolean; opacity: number }> = {};
    LAYERS.forEach(l => {
      initial[l.id] = { active: false, opacity: 0.6 };
    });
    return initial;
  });

  // Sync state to Mapbox
  useEffect(() => {
    if (!map) return;

    LAYERS.forEach(config => {
      const state = layerState[config.id];
      const layerExists = map.getLayer(config.id);
      const sourceId = `${config.id}-source`;
      const sourceExists = map.getSource(sourceId);

      if (state.active) {
        // If not added to map, add it
        if (!sourceExists) {
          map.addSource(sourceId, {
            type: "raster",
            tiles: [
              `http://localhost:8000/api/tiles/${config.backendId}/{z}/{x}/{y}.png?colormap=${config.cmap}&min_val=${config.min}&max_val=${config.max}&nodata=${config.nodata}`
            ],
            tileSize: 256
          });
        }
        
        if (!layerExists) {
          map.addLayer({
            id: config.id,
            type: "raster",
            source: sourceId,
            paint: {
              "raster-opacity": state.opacity,
              "raster-fade-duration": 300
            }
          }, "communities-fill"); // Render just below the community fill so its overlayed by the heatmap but over the basemap
        } else {
          // It exists, update its opacity
          map.setPaintProperty(config.id, "raster-opacity", state.opacity);
        }
      } else {
        // Active is false. If layer exists, remove it
        if (layerExists) {
          map.removeLayer(config.id);
        }
        if (sourceExists) {
          map.removeSource(sourceId);
        }
      }
    });
  }, [layerState, map]);

  const toggleLayer = (id: string) => {
    setLayerState(prev => ({
      ...prev,
      [id]: {
        ...prev[id],
        active: !prev[id].active
      }
    }));
  };

  const changeOpacity = (id: string, opacity: number) => {
    setLayerState(prev => ({
      ...prev,
      [id]: {
        ...prev[id],
        opacity
      }
    }));
  };

  return (
    <div className={styles.container}>
      {isOpen && (
        <div className={`glass-panel ${styles.popover}`}>
          <div className={styles.header}>
            <span className={styles.title}>Map Overlays</span>
            <button className={styles.closeBtn} onClick={() => setIsOpen(false)}>✕</button>
          </div>
          
          <div className={styles.layerList}>
            {LAYERS.map(layer => {
              const state = layerState[layer.id];
              return (
                <div key={layer.id} className={`${styles.layerRow} ${state.active ? styles.activeRow : ''}`}>
                  <div className={styles.rowTop}>
                    <label className={styles.toggleLabel}>
                      <input 
                        type="checkbox" 
                        className={styles.checkbox}
                        checked={state.active}
                        onChange={() => toggleLayer(layer.id)}
                      />
                      <span className={styles.layerName}>{layer.name}</span>
                    </label>
                    {state.active && (
                      <span className={styles.pctLabel}>{Math.round(state.opacity * 100)}%</span>
                    )}
                  </div>
                  
                  {state.active && (
                    <div className={styles.rowBottom}>
                      <input 
                        type="range" 
                        className={styles.slider}
                        min="0" max="1" step="0.05"
                        value={state.opacity}
                        onChange={(e) => changeOpacity(layer.id, parseFloat(e.target.value))}
                      />
                      <div className={styles.legendBar} style={{ background: layer.legendGradient }} />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!isOpen && (
        <button className={`glass-panel ${styles.floatingButton}`} onClick={() => setIsOpen(true)}>
          <span className={styles.icon}>🗺️</span> Layers
        </button>
      )}
    </div>
  );
}
