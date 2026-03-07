"use client";

import React, { useMemo } from "react";
import { useAppContext } from "../../context/AppContext";
import styles from "./PixelInspector.module.css";
import { CommunityFeature } from "../../lib/types";

// Dynamic Radar constraints are now fetched directly from AppContext to scale to city maximums

const FRIENDLY_NAMES: Record<string, string> = {
  ndvi_mean: "🌿 Vegetation",
  albedo_mean: "☀️ Reflectivity",
  building_density_mean: "🏢 Buildings",
  height_mean: "🏗️ Height",
  road_density_mean: "🛣️ Roads",
  sand_mask_fraction: "🏜️ Sand",
  water_mask_full_fraction: "💧 Water",
  dist_to_coast_m: "🌊 Coast Dist",
  dist_to_coast_mean: "🌊 Coast Dist"
};

export default function PixelInspector() {
  const { 
    selectedPixel, setSelectedPixel, 
    pixelInspectorData, pixelInspectorLoading,
    selectedCommunity, computedCommunities,
    timeOfDay, globalFeatureRanges
  } = useAppContext();

  // Finding the selected community's data
  const communityFeature = useMemo(() => {
    if (!computedCommunities || !selectedCommunity) return null;
    return computedCommunities.features.find(
      (f: CommunityFeature) => f.properties.COMM_NUM.toString() === selectedCommunity
    );
  }, [computedCommunities, selectedCommunity]);

  if (!selectedPixel) return null;

  const handleBack = () => setSelectedPixel(null);

  // Loading state
  if (pixelInspectorLoading || !pixelInspectorData) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.headerRow}>
          <button className={styles.backButton} onClick={handleBack}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
            Back to Community
          </button>
        </div>
        <div className={styles.loaderContainer}>
          <div className={styles.spinner} />
          <span>Crunching SHAP attributions...</span>
        </div>
      </div>
    );
  }

  const { features, anomalies, shap_values, explanation, base_value } = pixelInspectorData;

  // -- Variables --
  const latStr = selectedPixel.lat.toFixed(5);
  const lngStr = selectedPixel.lng.toFixed(5);
  const currentAnom = anomalies[timeOfDay] || 0;
  const isHot = currentAnom > 0;
  
  // -- RADAR CHART LOGIC --
  const radarFeatures = Object.keys(shap_values);
  const numAxes = radarFeatures.length;
  const radarRadius = 100;
  const cx = 150, cy = 150;
  
  // Convert an angle index and radius ratio into a coordinate
  const getRadialPoint = (ratio: number, index: number, maxR: number = radarRadius) => {
    const angle = (Math.PI * 2 * index) / numAxes - Math.PI / 2;
    const r = ratio * maxR;
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle)
    };
  };

  // Convert a feature value into a radar chart coordinate. - with auto scaling
  const getPoint = (val: number, range: [number, number], index: number, maxR: number = radarRadius) => {
    let pct = (range[1] - range[0] === 0) ? 0 : (val - range[0]) / (range[1] - range[0]);
    pct = Math.max(0, Math.min(1, pct));
    return getRadialPoint(pct, index, maxR);
  };

  const radarPoints = radarFeatures.map((f, i) => {
    // Exact mapping for the SHAP 'dist_to_coast_mean' key to the physical 'dist_to_coast_m' key
    const featureName = f === 'dist_to_coast_mean' ? 'dist_to_coast_m' : f;
    const rawVal = features[featureName] !== undefined ? features[featureName] : 0;
    
    let range: [number, number] = [0, 1];
    
    if (globalFeatureRanges) {
        // Fallback catch for dist_to_coast mapping naming mismatch between SHAP and the geoJSON backend features 
        const lookupKey = f === 'dist_to_coast_m' ? 'dist_to_coast_mean' : f; 
        range = globalFeatureRanges[lookupKey] || [0, 1];
    }
    
    // Getting a point to plot based on the value and the range
    return getPoint(rawVal, range, i);
  });
  
  const radarPolygonStr = radarPoints.map(p => `${p.x},${p.y}`).join(" ");

  // -- WATERFALL CHART LOGIC --
  const sortedShap = Object.entries(shap_values)
    .sort((a, b) => Math.abs(b[1] as number) - Math.abs(a[1] as number));
  
  // Multiply the maximum SHAP by 1.5 to guarantee the text reading will never overflow out of its 50% grid block
  const maxAbsShap = Math.max(...sortedShap.map(s => Math.abs(s[1] as number)), 0.1) * 1.5;
  const getBarWidth = (val: number) => (Math.abs(val) / maxAbsShap) * 100; 

  // -- DIURNAL CHART LOGIC --
  const buildDiurnalChart = () => {
    if (!communityFeature) return null;
    const p = communityFeature.properties;
    // Data structure for the temperature anomaly for the community and the city
    const dData = [
      { comm: anomalies.morning || 0, city: p.anomaly_morning_mean || 0 },
      { comm: anomalies.afternoon || 0, city: p.anomaly_afternoon_mean || 0 },
      { comm: anomalies.night || 0, city: p.anomaly_night_mean || 0 }
    ];
    const allVals = dData.flatMap(d => [d.comm, d.city]);
    const minVal = Math.min(-1, ...allVals) - 0.5; // Add padding as well
    const maxVal = Math.max(1, ...allVals) + 0.5;
    const normY = (val: number) => 90 - ((val - minVal) / (maxVal - minVal) * 80);
    const xVals = [40, 160, 280]; 
    
    const commPath = `M ${xVals[0]} ${normY(dData[0].comm)} L ${xVals[1]} ${normY(dData[1].comm)} L ${xVals[2]} ${normY(dData[2].comm)}`;
    const cityPath = `M ${xVals[0]} ${normY(dData[0].city)} L ${xVals[1]} ${normY(dData[1].city)} L ${xVals[2]} ${normY(dData[2].city)}`;

    return (
      <svg width="100%" height="auto" viewBox="0 0 320 120" style={{marginTop: 8}}>
        <line x1="10" y1={normY(0)} x2="310" y2={normY(0)} stroke="var(--border-subtle)" strokeDasharray="4 4" />
        <path d={cityPath} fill="none" stroke="var(--text-secondary)" strokeWidth="2" strokeDasharray="6 6" />
        <path d={commPath} fill="none" stroke={isHot ? "var(--accent-hot)" : "var(--accent-cool)"} strokeWidth="3" />
        {dData.map((d, i) => {
          const isCurrent = (timeOfDay === 'morning' && i === 0) || (timeOfDay === 'afternoon' && i === 1) || (timeOfDay === 'night' && i === 2);
          return (
            <circle 
              key={i} 
              cx={xVals[i]} 
              cy={normY(d.comm)} 
              r={isCurrent ? 6 : 4} 
              fill={isCurrent ? (isHot ? "var(--accent-hot)" : "var(--accent-cool)") : "var(--bg-primary)"} 
              stroke={isHot ? "var(--accent-hot)" : "var(--accent-cool)"} 
              strokeWidth="2.5" 
            />
          );
        })}
        <text x={xVals[0]} y="112" fontSize="12" fill="var(--text-secondary)" textAnchor="middle">Morning</text>
        <text x={xVals[1]} y="112" fontSize="12" fill="var(--text-secondary)" textAnchor="middle">Afternoon</text>
        <text x={xVals[2]} y="112" fontSize="12" fill="var(--text-secondary)" textAnchor="middle">Night</text>
      </svg>
    );
  };

  // -- AI EXPLANATION PARSING --
  const rawParts = explanation.split("(Note:");
  const mainSentence = rawParts[0].trim();
  const noteText = rawParts.length > 1 ? "(Note: " + rawParts[1].trim() : "";

  return (
    <div className={styles.wrapper}>
      {/* Top Header Row */}
      <div className={styles.headerRow}>
        <button className={styles.backButton} onClick={handleBack}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>
          Back to Community
        </button>
        <div className={styles.coords}>{latStr}, {lngStr}</div>
      </div>

      <div className={styles.contentScroll}>
        
        {/* -- SECTION 1: VITALS -- */}
        <div className={styles.vitalsCard}>
          <div className={styles.vitalsTop}>
            <div className={styles.communityName}>{communityFeature?.properties.CNAME_E || "Unknown"}</div>
            <div className={`${styles.mainBadge} ${isHot ? styles.hotBadge : styles.coolBadge}`}>
              {currentAnom > 0 ? '+' : ''}{currentAnom.toFixed(2)}°C
            </div>
          </div>
          <div className={styles.anomalyPills}>
            {(['morning', 'afternoon', 'night'] as const).map(t => {
              const val = anomalies[t] || 0;
              const tHot = val > 0;
              return (
                <div key={t} className={`${styles.pill} ${timeOfDay === t ? styles.active : ''}`}>
                  <span style={{textTransform: 'capitalize'}}>{t}</span>
                  <span className={`${styles.pillValue} ${tHot ? styles.hotText : styles.coolText}`}>
                    {tHot ? '+' : ''}{val.toFixed(2)}°
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* -- SECTION 4: AI EXPLANATION -- */}
        <div className={styles.aiExplanation}>
          <div className={styles.aiIcon}>🧠</div>
          <div>
            <div className={styles.aiText}>{mainSentence}</div>
            {noteText && <div className={styles.aiNote}>{noteText}</div>}
          </div>
        </div>

        {/* -- SECTION 3: SHAP WATERFALL -- */}
        <div className={styles.widgetBox}>
          <div className={styles.widgetTitle}>AI Heat Drivers (SHAP)</div>
          <div className={styles.waterfallContainer}>
            {sortedShap.map(([feat, val]) => {
              const value = val as number;
              const wVal = getBarWidth(value) / 2; 
              const isHeating = value > 0;
              return (
                <div key={feat} className={styles.waterfallRow}>
                  <div className={styles.waterfallLabel} title={feat}>
                    {FRIENDLY_NAMES[feat] || feat}
                  </div>
                  <div className={styles.waterfallTrack}>
                    <div 
                      className={`${styles.waterfallBar} ${isHeating ? styles.heating : styles.cooling}`}
                      style={{
                        width: `${wVal}%`,
                        left: isHeating ? '50%' : `${50 - wVal}%`
                      }}
                    />
                    <div 
                      className={styles.waterfallValue}
                      style={{
                        left: isHeating ? `calc(50% + ${wVal}% + 6px)` : '',
                        right: !isHeating ? `calc(50% + ${wVal}% + 6px)` : '',
                        color: isHeating ? 'var(--accent-hot)' : 'var(--accent-cool)'
                      }}
                    >
                      {value > 0 ? '+' : ''}{value.toFixed(2)}°
                    </div>
                  </div>
                </div>
              )
            })}
            <div className={styles.waterfallSummary}>
              <span>Base: {base_value.toFixed(2)}°C</span>
              <span>Predicted: {currentAnom.toFixed(2)}°C</span>
            </div>
          </div>
        </div>

        {/* -- SECTION 2: RADAR CHART -- */}
        <div className={styles.widgetBox}>
          <div className={styles.widgetTitle}>Pixel Profile vs City Range</div>
          <div style={{fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.4, marginBottom: 4}}>
            Shows where this exact 30m² area sits between the absolute minimum (center) and maximum (outer ring) values found across all of Dubai.
          </div>
          <div className={styles.radarContainer}>
            <svg width="100%" height="auto" viewBox="-30 -30 360 360" style={{maxWidth: '280px', margin: '0 auto', display: 'block'}}>
              {/* Scale Rings */}
              {[0.25, 0.5, 0.75, 1.0].map((scale, idx) => {
                const topPt = getRadialPoint(scale, 0);
                return (
                  <g key={`web-${idx}`}>
                    <polygon 
                      points={radarFeatures.map((_, i) => `${getRadialPoint(scale, i).x},${getRadialPoint(scale, i).y}`).join(" ")}
                      fill="none"
                      stroke="var(--border-subtle)"
                      strokeWidth="1.5"
                    />
                    {/* Ring Labels */}
                    <text x={cx + 4} y={topPt.y + 2} fill="var(--text-secondary)" fontSize="9" dominantBaseline="middle">
                      {scale === 1.0 ? 'Max' : `${scale * 100}%`}
                    </text>
                  </g>
                );
              })}
              {/* Axes and Labels */}
              {radarFeatures.map((f, i) => {
                const pEdge = getRadialPoint(1.35, i);
                const pAxisEnd = getRadialPoint(1.0, i);
                return (
                  <g key={`axis-${i}`}>
                    <line x1={cx} y1={cy} x2={pAxisEnd.x} y2={pAxisEnd.y} stroke="var(--border-subtle)" strokeWidth="1" />
                    <text x={pEdge.x} y={pEdge.y} fill="var(--text-primary)" fontSize="11" fontWeight="500" textAnchor="middle" dominantBaseline="middle" style={{ textShadow: '0 1px 4px rgba(0,0,0,0.4)' }}>
                      {FRIENDLY_NAMES[f] ? FRIENDLY_NAMES[f] : f}
                    </text>
                  </g>
                );
              })}
              {/* The Data Polygon */}
              <polygon
                points={radarPolygonStr}
                fill={isHot ? "rgba(255, 107, 53, 0.25)" : "rgba(0, 188, 212, 0.25)"}
                stroke={isHot ? "var(--accent-hot)" : "var(--accent-cool)"}
                strokeWidth="2.5"
              />
              {/* The Data Nodes */}
              {radarPoints.map((p, i) => (
                <circle key={`pt-${i}`} cx={p.x} cy={p.y} r="3" fill="#fff" />
              ))}
            </svg>
          </div>
        </div>

        {/* -- SECTION 5: DIURNAL PROFILE -- */}
        <div className={styles.widgetBox}>
          <div className={styles.widgetTitle}>Pixel vs Community Trend</div>
          {buildDiurnalChart()}
        </div>

      </div>
    </div>
  );
}
