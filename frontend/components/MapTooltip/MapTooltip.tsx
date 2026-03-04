"use client";

import React, { useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import styles from "./MapTooltip.module.css";
import { CommunityFeature } from "../../lib/types";

export default function MapTooltip() {
  // Extract all the data from the context
  const { hoveredPixelAnomaly, hoveredCommunity, computedCommunities, timeOfDay, selectedCommunity } = useAppContext();
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Track mouse position globally so the tooltip follows the cursor
  useEffect(() => {
    // Happens everytime the mouse moves
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };

    // Listen if we have a pixel anomaly OR an unselected community hovered - If tooltip should exist
    if (hoveredPixelAnomaly !== null || (hoveredCommunity && hoveredCommunity !== selectedCommunity)) {
      window.addEventListener("mousemove", handleMouseMove);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, [hoveredPixelAnomaly, hoveredCommunity, selectedCommunity]);

  // Priority 1: If hovering over a pixel of the selected community, show the small pixel tooltip
  if (hoveredPixelAnomaly !== null) {
    return (
      <div 
        className={`glass-panel ${styles.tooltipContainer}`}
        style={{ left: mousePos.x, top: mousePos.y }}
      >
        <div className={styles.pixelDetailRow}>
          <div className={styles.statLabel}>Local 30m² Pixel Anomaly</div>
          <div className={`${styles.statValue} ${styles.anomalyValue} ${hoveredPixelAnomaly > 0 ? styles.anomalyHot : styles.anomalyCool}`}>
            {hoveredPixelAnomaly > 0 ? "+" : ""}{hoveredPixelAnomaly.toFixed(1)}°C
          </div>
        </div>
      </div>
    );
  }

  // Priority 2: If hovering over an unselected community, show the large community tooltip
  if (hoveredCommunity && hoveredCommunity !== selectedCommunity && computedCommunities) {
    // Find the community feature that matches the hovered community
    const feature = computedCommunities.features.find(
      (f: CommunityFeature) => f.properties.COMM_NUM.toString() === hoveredCommunity
    );

    if (!feature) return null;

    const props = feature.properties;
    
    // Get the correct anomaly value based on time of day
    let anomalyValue = 0;
    if (timeOfDay === "morning") anomalyValue = props.anomaly_morning_mean;
    else if (timeOfDay === "afternoon") anomalyValue = props.anomaly_afternoon_mean;
    else anomalyValue = props.anomaly_night_mean;

    // Determine HVI color class
    let hviClass = styles.hviLow;
    if (props.hvi! >= 75) hviClass = styles.hviHigh;
    else if (props.hvi! >= 40) hviClass = styles.hviMed;

    return (
      <div 
        className={`glass-panel ${styles.tooltipContainer} ${styles.largeTooltip}`}
        style={{ left: mousePos.x, top: mousePos.y }}
      >
        <div className={styles.header}>
          <div className={styles.title}>{props.CNAME_E}</div>
          {props.priorityExposure && (
            <div className={styles.priorityBadge}>Priority</div>
          )}
        </div>

        <div className={styles.statsGrid}>
          <div className={styles.statPair}>
            <div className={styles.statLabel}>HVI Score</div>
            <div className={styles.statValue}>
              <span className={`${styles.hviDot} ${hviClass}`} />
              {props.hvi} <span style={{fontSize: "0.8em", opacity: 0.6}}>/ 100</span>
            </div>
          </div>
          
          <div className={styles.statPair}>
            <div className={styles.statLabel}>Population</div>
            <div className={styles.statValue}>
              {props.population ? props.population.toLocaleString() : "N/A"}
            </div>
          </div>

          <div className={styles.statPair}>
            <div className={styles.statLabel}>Temp Anomaly</div>
            <div className={`${styles.statValue} ${styles.anomalyValue} ${anomalyValue > 0 ? styles.anomalyHot : styles.anomalyCool}`}>
              {anomalyValue > 0 ? "+" : ""}{anomalyValue.toFixed(2)}°C
            </div>
          </div>
          
          <div className={styles.statPair}>
            <div className={styles.statLabel}>Greenery</div>
            <div className={styles.statValue}>
              {(props.green_fraction * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Nothing to show
  return null;
}
