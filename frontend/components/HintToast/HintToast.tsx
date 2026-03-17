"use client";

import React, { useEffect, useState, useRef } from "react";
import { useAppContext } from "../../context/AppContext";
import styles from "./HintToast.module.css";

export default function HintToast() {
  const { selectedCommunity, timeOfDay } = useAppContext();
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track how many distinct communities have been selected
  const prevCommunityRef = useRef<string | null>(null);

  useEffect(() => {
    // Only trigger when a community is freshly selected (not on deselect)
    if (selectedCommunity && selectedCommunity !== prevCommunityRef.current) {
      prevCommunityRef.current = selectedCommunity;

      // Clear any existing timer
      if (timerRef.current) clearTimeout(timerRef.current);

      setVisible(true);

      // Auto-dismiss after 5 seconds
      timerRef.current = setTimeout(() => {
        setVisible(false);
      }, 5000);
    }

    // When the community is deselected, hide immediately
    if (!selectedCommunity) {
      prevCommunityRef.current = null;
      setVisible(false);
      if (timerRef.current) clearTimeout(timerRef.current);
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [selectedCommunity]);

  const isLight = timeOfDay === "morning";

  return (
    <div className={`${styles.toast} ${visible ? styles.visible : ""} ${isLight ? styles.light : ""}`} role="status" aria-live="polite">
      <span className={styles.icon}>⇧</span>
      <span className={styles.text}>
        <strong>Shift + Click</strong> pixels to enter Intervention Mode
      </span>
      <button
        className={styles.dismiss}
        onClick={() => setVisible(false)}
        aria-label="Dismiss hint"
      >
        ✕
      </button>
    </div>
  );
}
