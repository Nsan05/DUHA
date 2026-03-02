"use client";

import React, { useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import styles from "./MapTooltip.module.css";
import { CommunityFeature } from "../../lib/types";

export default function MapTooltip() {
  const { hoveredCommunity, computedCommunities, timeOfDay } = useAppContext();
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Track mouse position globally so the tooltip follows the cursor
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };

    // Only listen if we actually have a tooltip to show
    if (hoveredCommunity) {
      window.addEventListener("mousemove", handleMouseMove);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
    };
  }, [hoveredCommunity]);

  if (!hoveredCommunity || !computedCommunities) return null;

  // Find the exact community feature
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
      className={`glass-panel ${styles.tooltipContainer}`}
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
            {props.hvi} / 100
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
