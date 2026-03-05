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
  // Sidebar open/close state
  const [isOpen, setIsOpen] = useState(false);
  
  // Track active layer state - along with initialization function (running only once)
  const [layerState, setLayerState] = useState<Record<string, { active: boolean; opacity: number }>>(() => {
    // Loops through all the layers and sets the default state
    const initial: Record<string, { active: boolean; opacity: number }> = {};
    LAYERS.forEach(l => {
      initial[l.id] = { active: false, opacity: 0.6 };
    });
    return initial;
  });

  // Track map style reloads so we know when to re-inject custom layers
  const [styleLoadedTracker, setStyleLoadedTracker] = useState(0);

  useEffect(() => {
    if (!map) return;
    const onStyleLoad = () => {
      // Small timeout ensures parent MapView's layers are initialized first
      setTimeout(() => setStyleLoadedTracker(prev => prev + 1), 10);
    };
    // listener that triggers when the map is loaded do the increment
    map.on("style.load", onStyleLoad);
    return () => {
      map.off("style.load", onStyleLoad);
    };
  }, [map]);

  // Sync state to Mapbox
  useEffect(() => {
    if (!map) return;


    LAYERS.forEach(config => {
      // Seperating sources (data) and layers (visualizations)
      const state = layerState[config.id];  // Output: { active: true, opacity: 0.6 }
      const layerExists = map.getLayer(config.id); 
      const sourceId = `${config.id}-source`; // Output: "ndvi-overlay-source"
      const sourceExists = map.getSource(sourceId);

      // When user turned the overlay on
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
          const beforeId = map.getLayer("communities-fill") ? "communities-fill" : undefined;
          
          map.addLayer({
            id: config.id,
            type: "raster",
            source: sourceId,
            paint: {
              "raster-opacity": state.opacity,
              "raster-fade-duration": 300
            }
          }, beforeId); // Render just below the community fill so its overlayed by the heatmap but over the basemap
        } else {
          // It exists, update its opacity - cus the user would have changed it.
          map.setPaintProperty(config.id, "raster-opacity", state.opacity);
        }
      } else {
        // Active is false (user has unticked the box). If layer exists, remove it
        if (layerExists) {
          map.removeLayer(config.id);
        }
        if (sourceExists) {
          map.removeSource(sourceId);
        }
      }
    });
  }, [layerState, map, styleLoadedTracker]);

  // When user clicks the checkbox the active flag is turned on and off in the layerstate
  const toggleLayer = (id: string) => {
    setLayerState(prev => ({
      ...prev, // Copies all the existing previous layers { active: true, opacity: 0.6 }
      [id]: { // update the specific layer that was clicked
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
        opacity // shorthand notation for opacity: opacity
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
