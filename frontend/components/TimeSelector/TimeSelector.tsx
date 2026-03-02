"use client";

import React, { useRef, useEffect, useState } from "react";
import { useAppContext } from "../../context/AppContext";
import { TimeOfDay } from "../../lib/types";
import styles from "./TimeSelector.module.css";

const TIME_SLOTS: { id: TimeOfDay; label: string; icon: string }[] = [
  { id: "morning", label: "Morning", icon: "☀️" },
  { id: "afternoon", label: "Afternoon", icon: "🔥" },
  { id: "night", label: "Night", icon: "🌙" },
];

// Component - function that returns UI (HTML)
export default function TimeSelector() {
  const { timeOfDay, setTimeOfDay } = useAppContext(); // timeOfDay is exteacted from the global object
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });
  
  // Refs to measure button widths for the sliding indicator
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // 1. Handle sliding indicator animation
  useEffect(() => {
    // Find the active button index based on the current timeOfDay
    const activeIndex = TIME_SLOTS.findIndex(slot => slot.id === timeOfDay);
    const activeButton = buttonRefs.current[activeIndex];
    
    if (activeButton && containerRef.current) {
      // Get position relative to the container
      const containerRect = containerRef.current.getBoundingClientRect();
      const buttonRect = activeButton.getBoundingClientRect();
      
      setIndicatorStyle({
        left: buttonRect.left - containerRect.left,
        width: buttonRect.width,
      });
    }
  }, [timeOfDay]);

  // 2. Handle Global CSS Theme toggling
  useEffect(() => {
    // Remove old themes
    document.body.classList.remove("theme-morning", "theme-afternoon");
    
    // Add new theme classes (night is default, so no extra class needed)
    if (timeOfDay === "morning") {
      document.body.classList.add("theme-morning");
    } else if (timeOfDay === "afternoon") {
      document.body.classList.add("theme-afternoon");
    }
  }, [timeOfDay]);

  // HTML
  return (
    <div className={`glass-panel ${styles.container}`} ref={containerRef}>
      {/* The animated highlight pill */}
      <div 
        className={styles.indicator} 
        style={{ 
          transform: `translateX(${indicatorStyle.left}px)`,
          width: `${indicatorStyle.width}px`
        }} 
      />
      
      {TIME_SLOTS.map((slot, index) => {
        const isActive = timeOfDay === slot.id;
        return (
          <button
            key={slot.id}
            ref={(el) => {
              buttonRefs.current[index] = el;
            }}
            className={`${styles.button} ${isActive ? styles.active : ""}`}
            onClick={() => setTimeOfDay(slot.id)}
            aria-pressed={isActive}
          >
            <span className={styles.icon}>{slot.icon}</span>
            {slot.label}
          </button>
        );
      })}
    </div>
  );
}
