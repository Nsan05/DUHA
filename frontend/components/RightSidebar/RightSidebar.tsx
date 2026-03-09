"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useAppContext } from "../../context/AppContext";
import styles from "./RightSidebar.module.css";
import { CommunityFeature } from "../../lib/types";
import PixelInspector from "../PixelInspector/PixelInspector";
import InterventionPanel from "../InterventionPanel/InterventionPanel";

export default function RightSidebar() {
  const { selectedCommunity, setSelectedCommunity, computedCommunities, timeOfDay, selectedPixel } = useAppContext();
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'inspector' | 'intervention'>('inspector');

  // The community to display: exclusively the selected one
  const activeCommId = selectedCommunity;

  // Re-open sidebar automatically if a new community or pixel is selected
  useEffect(() => {
    if (activeCommId || selectedPixel) {
      setIsOpen(true);
    } else {
      setIsOpen(false);
    }
  }, [activeCommId, selectedPixel]);

  if (!computedCommunities) return null;

  // Find the community feature that matches the selected community
  const feature = computedCommunities.features.find(
    (f: CommunityFeature) => f.properties.COMM_NUM.toString() === activeCommId
  );

  // Return is displayed when the componenet is used
  return (
    // two possible states for the sidebar: open or closed
    <div className={`${styles.sidebarWrapper} ${isOpen ? styles.open : styles.closed}`}>
      {/* Toggle Tab */}
      <button 
        className={`glass-panel ${styles.toggleButton}`}
        onClick={() => setIsOpen(!isOpen)}
        title={isOpen ? "Close Sidebar" : "Open Sidebar"}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          {isOpen ? (
            <path d="M9 18l6-6-6-6" /> // Chevron Right
          ) : (
            <path d="M15 18l-6-6 6-6" /> // Chevron Left
          )}
        </svg>
      </button>

      {/* Main Panel */}
      {/* If a pixel is selected, show the pixel inspector, otherwise show the community dashboard */}
      <div className={`glass-panel ${styles.sidebarPanel}`}>
        {selectedPixel ? (
          <div className={styles.pixelViewContainer}>
            <div className={styles.tabBar}>
              <button 
                className={`${styles.tabButton} ${activeTab === 'inspector' ? styles.activeTab : ''}`}
                onClick={() => setActiveTab('inspector')}
              >
                Analytics
              </button>
              <button 
                className={`${styles.tabButton} ${activeTab === 'intervention' ? styles.activeTab : ''}`}
                onClick={() => setActiveTab('intervention')}
              >
                Interventions
              </button>
            </div>
            <div className={styles.scrollContainer}>
              {activeTab === 'inspector' ? <PixelInspector /> : <InterventionPanel />}
            </div>
          </div>
        ) : feature ? (
          <SidebarContent 
            feature={feature} 
            timeOfDay={timeOfDay} 
            computedCommunities={computedCommunities}
            onClose={() => setSelectedCommunity(null)}
          />
        ) : (
          <div className={styles.emptyState}>
            <p>Select a community to view details.</p>
          </div>
        )}
      </div>
    </div>
  );
}

// Renders Dashboard Widgets
function SidebarContent({ feature, timeOfDay, computedCommunities, onClose }: { feature: CommunityFeature, timeOfDay: string, computedCommunities: any, onClose: () => void }) {
  const props = feature.properties;

  // 1. Calculate Rank, Averages, and Dynamic Max Anomaly
  const { rank, cityAverages, maxAnomaly } = useMemo(() => {
    const features = computedCommunities.features;
    let r = 1;
    let m = 0, a = 0, n = 0; // morning, afternoon, night
    let maxAnom = 0;
    
    for (const f of features) {
      // Rank computation
      // props.hvi is the hvi of the current community
      // f.properties.hvi is the hvi of the community being compared
      if ((f.properties.hvi || 0) > (props.hvi || 0)) r++;
      
      // Averages accumulation
      m += f.properties.anomaly_morning_mean || 0;
      a += f.properties.anomaly_afternoon_mean || 0;
      n += f.properties.anomaly_night_mean || 0;

      // Find absolute max anomaly for the current time of day to scale the gauge
      let val = 0;
      if (timeOfDay === "morning") val = f.properties.anomaly_morning_mean || 0;
      else if (timeOfDay === "afternoon") val = f.properties.anomaly_afternoon_mean || 0;
      else val = f.properties.anomaly_night_mean || 0;
      
      const absVal = Math.abs(val);
      if (absVal > maxAnom) maxAnom = absVal;
    }
    
    return {
      rank: r,
      cityAverages: {
        morning: m / features.length,
        afternoon: a / features.length,
        night: n / features.length
      },
      // Ensure we don't divide by zero if maxAnom is somehow 0
      maxAnomaly: Math.max(0.1, maxAnom) 
    };
  }, [computedCommunities, props.hvi, timeOfDay]);

  // 2. Process Current Data
  let anomalyValue = 0;
  let extPct = 0;
  if (timeOfDay === "morning") { 
    anomalyValue = props.anomaly_morning_mean; extPct = props.anomaly_morning_extreme_pct; 
  } else if (timeOfDay === "afternoon") { 
    anomalyValue = props.anomaly_afternoon_mean; extPct = props.anomaly_afternoon_extreme_pct; 
  } else { 
    anomalyValue = props.anomaly_night_mean; extPct = props.anomaly_night_extreme_pct; 
  }

  // Determine HVI color class
  let hviClass = styles.hviLow;
  let hviSVGColor = "var(--accent-green)";
  if (props.hvi! >= 75) { hviClass = styles.hviHigh; hviSVGColor = "var(--accent-hot)"; }
  else if (props.hvi! >= 40) { hviClass = styles.hviMed; hviSVGColor = "var(--accent-amber)"; }

  // 3. Gauge Math
  const isHot = anomalyValue > 0;
  const pct = Math.min(Math.abs(anomalyValue) / maxAnomaly, 1) * 50; 
  const barStyle = {
    width: `${pct}%`,
    left: isHot ? '50%' : `${50 - pct}%`,
    backgroundColor: isHot ? 'var(--accent-hot)' : 'var(--accent-cool)'
  };

  // 4. Donut Chart Math
  const b = props.building_density_mean || 0;
  const g = props.green_fraction || 0;
  const s = props.sand_fraction_mean || 0;
  const w = props.water_fraction_mean || 0;
  const other = Math.max(0, 1 - (g + s + w + b));
  
  const compData = [
    { label: 'Built', val: b * 100, color: "var(--text-secondary)" },
    { label: 'Green', val: g * 100, color: "var(--accent-green)" },
    { label: 'Sand', val: s * 100, color: "#e6c229" },
    { label: 'Water', val: w * 100, color: "var(--accent-cool)" },
    { label: 'Other', val: other * 100, color: "var(--border-subtle)" }
  ];

  let currentOffset = 0;
  const donutSlices = compData.map((d, i) => {
    if (d.val <= 0) return null;
    const strokeDasharray = `${d.val} ${100 - d.val}`;
    const strokeDashoffset = -currentOffset;
    currentOffset += d.val;
    return (
      <circle
        key={i}
        cx="21" cy="21" r="15.91549430"
        fill="transparent"
        stroke={d.color}
        strokeWidth="6"
        strokeDasharray={strokeDasharray}
        strokeDashoffset={strokeDashoffset}
      />
    );
  });

  // 5. Diurnal Chart Math
  // Cityaverage computed in the usememo 
  const diurnalData = [
    { comm: props.anomaly_morning_mean || 0, city: cityAverages.morning },
    { comm: props.anomaly_afternoon_mean || 0, city: cityAverages.afternoon },
    { comm: props.anomaly_night_mean || 0, city: cityAverages.night }
  ];
  const allVals = diurnalData.flatMap(d => [d.comm, d.city]);
  const minVal = Math.min(-1, ...allVals) - 0.5;
  const maxVal = Math.max(1, ...allVals) + 0.5;

  const normY = (val: number) => {
    // Map value to Y coordinates between 10 (top) and 90 (bottom) within a 120px tall viewBox
    return 90 - ((val - minVal) / (maxVal - minVal) * 80); 
  };
  const xVals = [40, 175, 310]; 

  const commPath = `M ${xVals[0]} ${normY(diurnalData[0].comm)} L ${xVals[1]} ${normY(diurnalData[1].comm)} L ${xVals[2]} ${normY(diurnalData[2].comm)}`;
  const cityPath = `M ${xVals[0]} ${normY(diurnalData[0].city)} L ${xVals[1]} ${normY(diurnalData[1].city)} L ${xVals[2]} ${normY(diurnalData[2].city)}`;

  return (
    <div className={styles.contentInner}>
      
      {/* WIDGET 1: Header */}
      <div className={styles.header}>
        <div className={styles.titleInfo}>
          <div className={styles.title}>{props.CNAME_E}</div>
          {props.priorityExposure && (
            <div className={styles.priorityBadge}>Priority</div>
          )}
        </div>
        <button className={styles.closeButton} onClick={onClose} aria-label="Close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div className={styles.dashboardGrid}>
        
        {/* WIDGET 2: Temperature Gauge */}
        <div className={styles.widgetBox}>
          <div className={styles.widgetHeader}>
            <span className={styles.widgetTitle}>Mean Temp Anomaly</span>
            <span className={`${styles.widgetValue} ${isHot ? styles.anomalyHot : styles.anomalyCool}`}>
              {anomalyValue > 0 ? "+" : ""}{anomalyValue.toFixed(2)}°C
            </span>
          </div>
          <div className={styles.gaugeTrack}>
            <div className={styles.gaugeCenterLine} />
            <div className={styles.gaugeFill} style={barStyle} />
          </div>
          <div className={styles.gaugeLabels}>
            <span>Cooler</span>
            <span>Average</span>
            <span>Hotter</span>
          </div>
        </div>

        {/* WIDGET 3: Land Composition Donut */}
        <div className={styles.widgetBox}>
          <span className={styles.widgetTitle}>Land Composition</span>
          <div className={styles.donutRow}>
            <svg width="42" height="42" viewBox="0 0 42 42" className={styles.donutSvg}>
              {/* background ring */}
              <circle cx="21" cy="21" r="15.91549430" fill="transparent" stroke="var(--border-subtle)" strokeWidth="6" />
              {/* slices */}
              {donutSlices}
            </svg>
            <div className={styles.donutLegend}>
              {compData.map(d => {
                if(d.val < 1) return null;
                return (
                  <div key={d.label} className={styles.legendItem}>
                    <span className={styles.legendDot} style={{backgroundColor: d.color}}></span>
                    <span className={styles.legendText}>{d.label} {Math.round(d.val)}%</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* WIDGET 4: Diurnal Profile */}
        <div className={styles.widgetBox}>
          <div className={styles.widgetHeader}>
            <span className={styles.widgetTitle}>Diurnal Profile</span>
            <div className={styles.chartLegendRow}>
              <div className={styles.chartLegendItem}>
                <span className={styles.legendLine} style={{borderColor: hviSVGColor}}/> Community
              </div>
              <div className={styles.chartLegendItem}>
                <span className={styles.legendLine} style={{borderColor: 'var(--text-secondary)', borderStyle: 'dashed'}}/> City Avg
              </div>
            </div>
          </div>
          <div className={styles.chartContainer}>
            <svg width="100%" height="auto" viewBox="0 0 350 120">
              <line x1="10" y1={normY(0)} x2="340" y2={normY(0)} stroke="var(--border-subtle)" strokeDasharray="4 4" />
              <path d={cityPath} fill="none" stroke="var(--text-secondary)" strokeWidth="2" strokeDasharray="6 6" />
              <path d={commPath} fill="none" stroke={hviSVGColor} strokeWidth="3" />
              {diurnalData.map((d, i) => {
                const isCurrentTime = (timeOfDay === 'morning' && i === 0) || (timeOfDay === 'afternoon' && i === 1) || (timeOfDay === 'night' && i === 2);
                return (
                  <circle 
                    key={i} 
                    cx={xVals[i]} 
                    cy={normY(d.comm)} 
                    r={isCurrentTime ? 6 : 4} 
                    fill={isCurrentTime ? hviSVGColor : "var(--bg-primary)"} 
                    stroke={hviSVGColor} 
                    strokeWidth="2.5" 
                  />
                )
              })}
              <text x={xVals[0]} y="112" fontSize="13" fill="var(--text-secondary)" textAnchor="middle">Morning</text>
              <text x={xVals[1]} y="112" fontSize="13" fill="var(--text-secondary)" textAnchor="middle">Afternoon</text>
              <text x={xVals[2]} y="112" fontSize="13" fill="var(--text-secondary)" textAnchor="middle">Night</text>
            </svg>
          </div>
        </div>

        {/* WIDGET 5: Key Stats */}
        <div className={styles.keyStatsGrid}>
          <div className={styles.statPair}>
            <div className={styles.statLabel}>Area</div>
            <div className={styles.statValue}>{(props.area_km2 || 0).toFixed(1)} km²</div>
          </div>
          <div className={styles.statPair}>
            <div className={styles.statLabel}>Population Density</div>
            <div className={styles.statValue}>{props.pop_density ? Math.round(props.pop_density).toLocaleString() : "N/A"}</div>
          </div>
          <div className={styles.statPair}>
            <div className={styles.statLabel}>HVI Rank</div>
            <div className={styles.statValue}><span className={`${styles.hviDot} ${hviClass}`} />{rank} <span style={{fontSize: "0.7em", opacity: 0.6}}>/{computedCommunities.features.length}</span></div>
          </div>
          <div className={styles.statPair}>
            <div className={styles.statLabel}>Extreme Heat %</div>
            <div className={styles.statValue}>{((extPct || 0) * 100).toFixed(1)}%</div>
          </div>
        </div>

      </div>
    </div>
  );
}
