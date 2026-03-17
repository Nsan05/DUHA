"use client";

import React from "react";
import styles from "./DuhaLogo.module.css";
import { useAppContext } from "../../context/AppContext";

export default function DuhaLogo() {
  const {
    timeOfDay,
    setSelectedCommunity,
    setSelectedPixel,
    setSelectedPixels,
    setInterventionMode,
    setActiveInterventions,
    setModifiedFeatures,
    setPredictedAnomalies,
    setPerPixelAnomalies,
  } = useAppContext();

  const handleClick = () => {
    // Full state reset
    setSelectedCommunity(null);
    setSelectedPixel(null);
    setSelectedPixels([]);
    setInterventionMode(false);
    setActiveInterventions([]);
    setModifiedFeatures(null);
    setPredictedAnomalies(null);
    setPerPixelAnomalies(null);
    // Fly map back to default Dubai overview
    window.dispatchEvent(new CustomEvent("duha:resetView"));
  };

  return (
    <button
      className={`${styles.logo} ${styles[timeOfDay]}`}
      onClick={handleClick}
      title="Dubai Urban Heat Analysis - Reset View"
      aria-label="DUHA - Reset to default view"
    >
      <span className={styles.wordmark}>DUHA</span>
      <span className={styles.tagline}>Dubai Urban Heat Analysis</span>
    </button>
  );
}
