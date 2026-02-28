"use client";

import React, { useRef, useEffect, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import styles from "./MapView.module.css";

// Store token safely (avoid public exposure if missing)
if (process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
  mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
}

export default function MapView() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (!process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
      console.error("Missing NEXT_PUBLIC_MAPBOX_TOKEN in .env.local");
      return;
    }

    // Initialize map only once
    if (mapRef.current) return;

    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [55.27, 25.2], // Dubai
      zoom: 11,
      minZoom: 9, // Keep them in the UAE
      maxZoom: 18,
      pitch: 30, // Slight 3D tilt
      bearing: 0,
      attributionControl: true,
      antialias: true, // Essential for smooth 3D rendering
    });

    const map = mapRef.current;

    map.on("load", () => {
      setMapLoaded(true);

      // Allow users to rotate and pitch the map manually using right-click drag
      // map.dragRotate.disable();

      // Optional: Add 3D buildings later in Phase 7
    });

    // Add navigation controls (zoom in/out/pitch)
    map.addControl(
      new mapboxgl.NavigationControl({
        showCompass: true, // Needed for the pitch/tilt button to appear
        visualizePitch: true,
      }),
      "bottom-right",
    );

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  return (
    <>
      <div className={styles.mapContainer} ref={mapContainerRef} />
      {/* Optional: Add a subtle overlay gradient that reacts to the theme */}
      <div className="map-atmospheric-overlay" />
    </>
  );
}
