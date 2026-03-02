"use client";

import React, { useRef, useEffect, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import styles from "./MapView.module.css";
import { useAppContext } from "../../context/AppContext";

if (process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
  mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
}

export default function MapView() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const { timeOfDay } = useAppContext();

  // 1. Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (!process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
      console.error("Missing NEXT_PUBLIC_MAPBOX_TOKEN in .env.local");
      return;
    }
    if (mapRef.current) return;

    // Default to dark-v11 initially
    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [55.27, 25.2], // Dubai
      zoom: 11,
      minZoom: 9, 
      maxZoom: 18,
      pitch: 30, // Slight 3D tilt
      bearing: 0,
      attributionControl: true,
      antialias: true, 
    });

    const map = mapRef.current;

    map.on("load", () => {
      setMapLoaded(true);
    });

    map.addControl(
      new mapboxgl.NavigationControl({
        showCompass: true, 
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

  // 2. Respond to Time of Day changes by swapping Basemap
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    let newStyle = "mapbox://styles/mapbox/dark-v11"; // Default Night
    if (timeOfDay === "morning") {
      newStyle = "mapbox://styles/mapbox/light-v11";
    } else if (timeOfDay === "afternoon") {
      newStyle = "mapbox://styles/mapbox/outdoors-v12"; // Warm, sandy look suited for afternoon
    }

    // Only set style if it's different to prevent flickering
    const currentStyle = mapRef.current.getStyle()?.sprite;
    if (currentStyle && !currentStyle.includes(newStyle.replace("mapbox://styles/", ""))) {
        mapRef.current.setStyle(newStyle);
    }
  }, [timeOfDay, mapLoaded]);

  return (
    <>
      <div className={styles.mapContainer} ref={mapContainerRef} />
      <div className="map-atmospheric-overlay" />
    </>
  );
}
