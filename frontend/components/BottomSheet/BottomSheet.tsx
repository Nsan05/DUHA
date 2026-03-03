"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { useAppContext } from "../../context/AppContext";
import { CommunityFeature } from "../../lib/types";
import CityCharts from "../Analytics/CityCharts";
import styles from "./BottomSheet.module.css";

// Snap heights (pixels from bottom)
const SNAP_COLLAPSED = 60;
const SNAP_HALF = 300;
const SNAP_FULL = typeof window !== "undefined" ? window.innerHeight * 0.85 : 600;

export default function BottomSheet() {
  const { 
    computedCommunities, 
    timeOfDay,
    selectedCommunity, 
    setSelectedCommunity,
    showPriorityOnly, setShowPriorityOnly,
    sortField, setSortField,
    sortDirection, setSortDirection
  } = useAppContext();

  // UI View state
  const [viewMode, setViewMode] = useState<'list' | 'analytics'>('list');
  
  // Dragging state
  const [height, setHeight] = useState(SNAP_COLLAPSED); // Height starts at collapsed
  const [showHviInfo, setShowHviInfo] = useState(false);
  const isDragging = useRef(false); 
  const startY = useRef(0);
  const startHeight = useRef(0);
  
  // Ref for the list container to handle internal scrolling
  const listRef = useRef<HTMLUListElement>(null);

  // --- 1. DRAG LOGIC ---
  const handlePointerDown = (e: React.PointerEvent) => {
    isDragging.current = true;
    startY.current = e.clientY;
    startHeight.current = height;
    
    // Prevent default touch actions (like scrolling the underlying body) while dragging the handle
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging.current) return;
    // Calcualte how much mouse has moved and update height accordingly
    const deltaY = startY.current - e.clientY;
    const newHeight = Math.max(SNAP_COLLAPSED, Math.min(SNAP_FULL, startHeight.current + deltaY));
    setHeight(newHeight);
  };

  // When mouse is released, snap to closest position
  const handlePointerUp = (e: React.PointerEvent) => {
    if (!isDragging.current) return;
    isDragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);

    // Snap to closest position
    const currentHeight = height;
    const distCollapsed = Math.abs(currentHeight - SNAP_COLLAPSED);
    const distHalf = Math.abs(currentHeight - SNAP_HALF);
    const distFull = Math.abs(currentHeight - SNAP_FULL);

    if (distCollapsed < distHalf && distCollapsed < distFull) setHeight(SNAP_COLLAPSED);
    else if (distHalf < distCollapsed && distHalf < distFull) setHeight(SNAP_HALF);
    else setHeight(SNAP_FULL);
  };

  // --- 2. SORTING & FILTERING ---
  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc'); // If already sorting by this field, reverse direction
    } else {
      setSortField(field);
      setSortDirection('desc'); // Default to descending when picking a new field
    }
    // Auto expand if we sort while collapsed
    if (height === SNAP_COLLAPSED) setHeight(SNAP_HALF);
  };

  const sortedCommunities = useMemo(() => {
    if (!computedCommunities) return [];
    
    let features = [...computedCommunities.features];

    // Filter
    if (showPriorityOnly) {
      features = features.filter(f => f.properties.priorityExposure);
    }

    // Sort
    features.sort((a, b) => {
      const pA = a.properties;
      const pB = b.properties;
      let valA = 0;
      let valB = 0;

      if (sortField === 'hvi') {
        valA = pA.hvi || 0;
        valB = pB.hvi || 0;
      } else if (sortField === 'population') {
        valA = pA.population || 0;
        valB = pB.population || 0;
      } else if (sortField === 'temperature') {
        // use the active time of day average
        valA = timeOfDay === 'morning' ? pA.anomaly_morning_mean : 
               timeOfDay === 'afternoon' ? pA.anomaly_afternoon_mean : pA.anomaly_night_mean;
        valB = timeOfDay === 'morning' ? pB.anomaly_morning_mean : 
               timeOfDay === 'afternoon' ? pB.anomaly_afternoon_mean : pB.anomaly_night_mean;
      } else if (sortField === 'diurnal') {
        valA = pA.diurnal_range_mean || 0;
        valB = pB.diurnal_range_mean || 0;
      }

      if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
      if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return features;
  }, [computedCommunities, sortField, sortDirection, showPriorityOnly, timeOfDay]);


  // --- 3. RENDERING ---
  const getHviColor = (hvi: number) => {
    if (hvi >= 75) return "var(--accent-hot)";
    if (hvi >= 40) return "var(--accent-amber)";
    return "var(--accent-green)";
  };

  // Simple Mini SVG line chart for diurnal profile -normalizes them to fit into 30px height
  const renderSparkline = (props: any) => {
    const minVal = Math.min(props.anomaly_morning_mean, props.anomaly_afternoon_mean, props.anomaly_night_mean);
    const maxVal = Math.max(props.anomaly_morning_mean, props.anomaly_afternoon_mean, props.anomaly_night_mean);
    const range = Math.max(maxVal - minVal, 1); // Avoid div by 0

    // Map 3 values to Y coordinates (0 top, 25 bottom, leaving room for labels below)
    const normalizeY = (val: number) => 30 - ((val - minVal) / range) * 20 - 5; 
    
    const y1 = normalizeY(props.anomaly_morning_mean);
    const y2 = normalizeY(props.anomaly_afternoon_mean);
    const y3 = normalizeY(props.anomaly_night_mean);

    // Active point x coordinate
    const activeX = timeOfDay === 'morning' ? 0 : timeOfDay === 'afternoon' ? 30 : 60;
    const activeY = timeOfDay === 'morning' ? y1 : timeOfDay === 'afternoon' ? y2 : y3;

    return (
      <div className={styles.sparklineContainer} style={{ height: "45px" }}>
        <svg width="60" height="45" style={{ overflow: "visible" }}>
          {/* Main line */}
          <polyline 
            points={`0,${y1} 30,${y2} 60,${y3}`} 
            fill="none" 
            stroke="var(--text-tertiary)" 
            strokeWidth="2" 
            strokeLinejoin="round" 
            strokeLinecap="round" 
          />
          {/* Subtle dots for all */}
          <circle cx="0" cy={y1} r="3" fill="var(--text-tertiary)" />
          <circle cx="30" cy={y2} r="3" fill="var(--text-tertiary)" />
          <circle cx="60" cy={y3} r="3" fill="var(--text-tertiary)" />
          {/* Bright dot for active time of day */}
          <circle cx={activeX} cy={activeY} r="4" fill="var(--accent-hot)" />
          
          {/* Text Labels for Time of Day */}
          <text x="0" y="42" fontSize="9" fill="var(--text-secondary)" textAnchor="middle" fontWeight="600">M</text>
          <text x="30" y="42" fontSize="9" fill="var(--text-secondary)" textAnchor="middle" fontWeight="600">A</text>
          <text x="60" y="42" fontSize="9" fill="var(--text-secondary)" textAnchor="middle" fontWeight="600">N</text>
        </svg>
      </div>
    );
  };

  return (
    <div 
      className={`${styles.sheet} ${viewMode === 'analytics' ? styles.sheetWide : ''}`}
      style={{ height: `${height}px` }}
    >
      {/* DRAG HANDLE & HEADER */}
      <div 
        className={styles.dragHeader}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <div className={styles.handle} />
        
        <div className={styles.titleRow}>
          <div className={styles.title}>
            Community Rankings
            <button 
              className={`${styles.infoButton} ${showHviInfo ? styles.active : ''}`}
              onClick={(e) => {
                e.stopPropagation(); // prevent drag trigger
                setShowHviInfo(!showHviInfo);
                if (height === SNAP_COLLAPSED) setHeight(SNAP_HALF);
              }}
              title="What is HVI?"
            >
              ?
            </button>
          </div>
          <button 
            className={`${styles.priorityToggle} ${showPriorityOnly ? styles.active : ""}`}
            onClick={(e) => {
              e.stopPropagation();
              setShowPriorityOnly(!showPriorityOnly);
              if (height === SNAP_COLLAPSED) setHeight(SNAP_HALF);
            }}
          >
            🔴 Priority Only
          </button>
        </div>

        {/* HVI Info Panel */}
        {showHviInfo && height > SNAP_COLLAPSED && (
          <div className={styles.infoPanel}>
            <strong>Heat Vulnerability Index (HVI)</strong> is a comparative score (0–100) measuring severe human exposure to heat. It combines:
            <br/><br/>
            • <strong>40%</strong> Mean Temperature Anomaly<br/>
            • <strong>30%</strong> Total Population Volume<br/>
            • <strong>30%</strong> % of Extreme Heat Pixels
            <br/><br/>
            <strong>Diurnal Sparkline:</strong> The mini-chart on the right shows how the community's temperature anomaly changes throughout the day (<strong>M</strong>orning, <strong>A</strong>fternoon, <strong>N</strong>ight). The glowing dot indicates the currently selected time.
          </div>
        )}
      </div>

      {/* SORT CONTROLS / VIEW TOGGLES */}
      {(height > SNAP_COLLAPSED) && (
        <div className={styles.controlsRow}>
          
          <div className={styles.viewToggleGroup}>
            <button 
              className={`${styles.viewToggle} ${viewMode === 'list' ? styles.viewActive : ''}`}
              onClick={() => setViewMode('list')}
            >
              📋 Directory
            </button>
            <button 
              className={`${styles.viewToggle} ${viewMode === 'analytics' ? styles.viewActive : ''}`}
              onClick={() => {
                setViewMode('analytics');
                if (height < SNAP_FULL) setHeight(SNAP_FULL); // Automatically expand fully to show charts
              }}
            >
              📈 Analytics
            </button>
          </div>

          <div className={styles.divider} />

          {viewMode === 'list' && (
            <>
              <button 
                className={`${styles.sortPill} ${sortField === 'hvi' ? styles.sortActive : ''}`} 
                onClick={() => handleSort('hvi')}
              >
                Score {sortField === 'hvi' && (sortDirection === 'asc' ? '↑' : '↓')}
              </button>
              <button 
                className={`${styles.sortPill} ${sortField === 'population' ? styles.sortActive : ''}`} 
                onClick={() => handleSort('population')}
              >
                Population {sortField === 'population' && (sortDirection === 'asc' ? '↑' : '↓')}
              </button>
              <button 
                className={`${styles.sortPill} ${sortField === 'temperature' ? styles.sortActive : ''}`} 
                onClick={() => handleSort('temperature')}
              >
                Temp {sortField === 'temperature' && (sortDirection === 'asc' ? '↑' : '↓')}
              </button>
            </>
          )}
        </div>
      )}

      {/* RENDER CONTENT BASED ON VIEW MODE */}
      {(height > SNAP_COLLAPSED) && viewMode === 'analytics' && (
        <div className={styles.analyticsContainer}>
          <CityCharts />
        </div>
      )}

      {(height > SNAP_COLLAPSED) && viewMode === 'list' && (
        <ul className={styles.listContainer} ref={listRef}>
          {sortedCommunities.map((feature: CommunityFeature) => {
            const props = feature.properties;
            const isSelected = selectedCommunity === props.COMM_NUM.toString();
            
            return (
              <li 
                key={props.COMM_NUM} 
                className={`${styles.card} ${isSelected ? styles.selected : ''}`}
                onClick={() => setSelectedCommunity(props.COMM_NUM.toString())}
              >
                {/* 1. Badge */}
                <div 
                  className={styles.hviBadge} 
                  style={{ backgroundColor: getHviColor(props.hvi || 0) }}
                >
                  {props.hvi}
                </div>
                
                {/* 2. Info */}
                <div className={styles.cardInfo}>
                  <div className={styles.commName}>
                    {props.CNAME_E}
                    {props.priorityExposure && <span style={{fontSize: "10px"}}>🔴</span>}
                  </div>
                  <div className={styles.commMeta}>
                    <span>Pop: {props.population ? props.population.toLocaleString() : "N/A"}</span>
                    <span>•</span>
                    <span>HVI Rank: {sortedCommunities.findIndex(f => f.properties.COMM_NUM === props.COMM_NUM) + 1}</span>
                  </div>
                </div>

                {/* 3. Sparkline */}
                {renderSparkline(props)}
              </li>
            );
          })}
          {sortedCommunities.length === 0 && (
            <div style={{ padding: "32px", textAlign: "center", color: "var(--text-secondary)" }}>
              No communities match the current filters.
            </div>
          )}
        </ul>
      )}
    </div>
  );
}
