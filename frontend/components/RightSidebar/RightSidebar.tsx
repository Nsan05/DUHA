"use client";

import React, { useState, useEffect } from "react";
import { useAppContext } from "../../context/AppContext";
import styles from "./RightSidebar.module.css";
import { CommunityFeature } from "../../lib/types";

export default function RightSidebar() {
  const { selectedCommunity, computedCommunities, timeOfDay } = useAppContext();
  const [isOpen, setIsOpen] = useState(false);

  // The community to display: exclusively the selected one
  const activeCommId = selectedCommunity;

  // Re-open sidebar automatically if a new community is selected
  useEffect(() => {
    if (activeCommId) {
      setIsOpen(true);
    } else {
      setIsOpen(false);
    }
  }, [activeCommId]);

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

{/* If community is selected display its details otherwise dispaly the default text. */}
      {/* Main Panel */}
      <div className={`glass-panel ${styles.sidebarPanel}`}>
        {feature ? (
          <SidebarContent feature={feature} timeOfDay={timeOfDay} />
        ) : (
          <div className={styles.emptyState}>
            <p>Hover or select a community to view details.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function SidebarContent({ feature, timeOfDay }: { feature: CommunityFeature, timeOfDay: string }) {
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
    <div className={styles.contentInner}>
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
