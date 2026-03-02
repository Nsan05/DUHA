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
  const { 
    timeOfDay, 
    computedCommunities, 
    setSelectedCommunity,
    setHoveredCommunity 
  } = useAppContext();

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
        // mapbox gl removes all custom layers when setStyle is called. 
        // We set a once listener on 'style.load' to re-trigger our layer addition effect
        mapRef.current.once('style.load', () => {
          // Force a re-render/re-evaluation of the layer addition effect
          setMapLoaded(prev => !prev); 
          setTimeout(() => setMapLoaded(true), 10);
        });
        mapRef.current.setStyle(newStyle);
    }
  }, [timeOfDay, mapLoaded]);

  // 3. Render Community Polygons and Handle Interactions
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !computedCommunities) return;

    // Check if source already exists
    if (!map.getSource("communities")) {
      map.addSource("communities", {
        type: "geojson",
        data: computedCommunities as any,
        generateId: true // Required for feature state (hover) to work
      });
    } else {
      // Just update the data if source already exists (e.g., HVI changed)
      (map.getSource("communities") as mapboxgl.GeoJSONSource).setData(computedCommunities as any);
    }

    // Add Fill Layer (colored by HVI)
    if (!map.getLayer("communities-fill")) {
      map.addLayer({
        id: "communities-fill",
        type: "fill",
        source: "communities",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "hvi"],
            0, "#30d158",   // Green (low vulnerability)
            50, "#ff9f0a",  // Amber (medium)
            100, "#ff473e"  // Red (high vulnerability)
          ],
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "hover"], false],
            0.65, // Opacity when hovered
            0.35  // Default opacity
          ]
        }
      });
    }

    // Add Outline Layer
    if (!map.getLayer("communities-outline")) {
      map.addLayer({
        id: "communities-outline",
        type: "line",
        source: "communities",
        paint: {
          "line-color": "rgba(255, 255, 255, 0.4)",
          "line-width": [
            "case",
            ["==", ["get", "priorityExposure"], true],
            2.5, // Thicker border for priority communities
            0.5  // Standard faint border
          ]
        }
      });
    }

    // stores which community is hovered
    let hoveredStateId: number | string | null = null;
    
    const onMouseMove = (e: mapboxgl.MapMouseEvent & { features?: mapboxgl.MapboxGeoJSONFeature[] }) => {
      if (e.features && e.features.length > 0) { // Ensures we are hovering over a community
        if (hoveredStateId !== null) {
          map.setFeatureState(
            { source: "communities", id: hoveredStateId },
            { hover: false } // If yes turn off previous hover state
          );
        }
        hoveredStateId = e.features[0].id!; // Update hovered state to current hover
        map.setFeatureState(
          { source: "communities", id: hoveredStateId },
          { hover: true }
        );
        map.getCanvas().style.cursor = "pointer";
        
        // Pass info to state for tooltip
        const props = e.features[0].properties;
        setHoveredCommunity(props?.COMM_NUM?.toString() || null);
      }
    };

    const onMouseLeave = () => {
      if (hoveredStateId !== null) {
        map.setFeatureState(
          { source: "communities", id: hoveredStateId },
          { hover: false }
        );
      }
      hoveredStateId = null;
      map.getCanvas().style.cursor = "";
      setHoveredCommunity(null);
    };

    const onClick = (e: mapboxgl.MapMouseEvent & { features?: mapboxgl.MapboxGeoJSONFeature[] }) => {
      if (e.features && e.features.length > 0) {
        const commId = e.features[0].properties?.COMM_NUM?.toString();
        if (commId) {
          setSelectedCommunity(commId); // Updates global context for selected community
        }
      }
    };

    // Attach listeners
    map.on("mousemove", "communities-fill", onMouseMove);
    map.on("mouseleave", "communities-fill", onMouseLeave);
    map.on("click", "communities-fill", onClick);

    return () => {
      // Cleanup listeners if effect re-runs
      map.off("mousemove", "communities-fill", onMouseMove);
      map.off("mouseleave", "communities-fill", onMouseLeave);
      map.off("click", "communities-fill", onClick);
    };

  }, [mapLoaded, computedCommunities]);

  return (
    <>
      <div className={styles.mapContainer} ref={mapContainerRef} />
      <div className="map-atmospheric-overlay" />
    </>
  );
}
