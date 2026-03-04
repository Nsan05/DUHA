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
    selectedCommunity,
    setSelectedCommunity,
    setHoveredCommunity 
  } = useAppContext();

  // Keep a ref of selectedCommunity for the click handler to access which will be updated when the selectedCommunity changes
  const selectedCommunityRef = useRef(selectedCommunity);
  useEffect(() => {
    selectedCommunityRef.current = selectedCommunity;
  }, [selectedCommunity]);

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
    const isDarkMap = timeOfDay === "night";
    
    // Darker faint lines for light map, Lighter faint lines for dark map
    const standardLineColor = isDarkMap ? "rgba(255, 255, 255, 0.25)" : "rgba(0, 0, 0, 0.15)";
    const priorityLineColor = isDarkMap ? "rgba(255, 255, 255, 1)" : "rgba(0, 0, 0, 0.9)";
    
    // If the community is priority then use the appropriate color
    const lineColorExpression = [
      "case",
      ["==", ["get", "priorityExposure"], true],
      priorityLineColor,
      standardLineColor
    ];

    // Liek above use the appropriate width of the line
    const lineWidthExpression = [
      "case",
      ["==", ["get", "priorityExposure"], true],
      2.5, // Bold boundary for priority
      1.0  // Standard boundary
    ];

    if (!map.getLayer("communities-outline")) {
      map.addLayer({
        id: "communities-outline",
        type: "line",
        source: "communities",
        paint: {
          "line-color": lineColorExpression as any,
          "line-width": lineWidthExpression as any
        }
      });
    } else {
      // Must dynamically update paint properties when timeOfDay changes - default function
      map.setPaintProperty("communities-outline", "line-color", lineColorExpression as any);
      map.setPaintProperty("communities-outline", "line-width", lineWidthExpression as any);
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

    // Runs when map is clicked
    const onMapClick = (e: mapboxgl.MapMouseEvent) => {
      // Check if we clicked on a community polygon
      const features = map.queryRenderedFeatures(e.point, { layers: ["communities-fill"] });
      // If we did indeed click on a real community
      if (features.length > 0) {
        const commId = features[0].properties?.COMM_NUM?.toString();
        if (commId) {
          // Toggle selection if clicking the already selected community
          if (selectedCommunityRef.current === commId) {
            setSelectedCommunity(null);
          } else {
            setSelectedCommunity(commId);
          }
        }
      } else {
        // If clicked on water/empty space, deselect
        setSelectedCommunity(null);
      }
    };

    // Attach listeners
    map.on("mousemove", "communities-fill", onMouseMove);
    map.on("mouseleave", "communities-fill", onMouseLeave);
    map.on("click", onMapClick);

    return () => {
      // Cleanup listeners if effect re-runs
      map.off("mousemove", "communities-fill", onMouseMove);
      map.off("mouseleave", "communities-fill", onMouseLeave);
      map.off("click", onMapClick);
    };
  }, [mapLoaded, computedCommunities]);

  // 4. Fly to Selected Community
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || !computedCommunities) return;
    
    // If deselected, fly back to city-wide view
    if (!selectedCommunity) {
      mapRef.current.flyTo({ 
        center: [55.27, 25.2], 
        zoom: 11, 
        pitch: 30, 
        bearing: 0, 
        duration: 2000,
        essential: true 
      });
      return;
    }

    // Get the feature for the selected community
    const feature = computedCommunities.features.find(
      (f: any) => f.properties.COMM_NUM.toString() === selectedCommunity
    );
    
    if (feature && feature.geometry) {
      // Calculate BBox manually to see where the coordinates lie to avoid pulling in external Turf.js dependencies
      let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
      
      const updateBounds = (coord: number[]) => {
        if (coord[0] < minLng) minLng = coord[0];
        if (coord[0] > maxLng) maxLng = coord[0];
        if (coord[1] < minLat) minLat = coord[1];
        if (coord[1] > maxLat) maxLat = coord[1];
      };

      // Going through all the cooridinates mentioned within the geometry feature to get the box
      const coords = feature.geometry.coordinates;
      if (feature.geometry.type === 'Polygon') {
        coords[0].forEach(updateBounds);
      } else if (feature.geometry.type === 'MultiPolygon') {
        coords.forEach((poly: any) => poly[0].forEach(updateBounds));
      }

      if (minLng !== Infinity) {
        mapRef.current.fitBounds(
          [[minLng, minLat], [maxLng, maxLat]],
          { 
            padding: { top: 40, bottom: 300, left: 40, right: 40 }, // Tighter padding for closer focus
            maxZoom: 14.5,  // Prevent zooming indiscriminately close on very small communities
            duration: 2000, // Cinematic 2.0s flight 
            pitch: 38,      // Shallower tilt so it's not too angled
            bearing: -10,   // Slight rotation for dynamism
            essential: true 
          }
        );
      }
    }
  }, [selectedCommunity, computedCommunities, mapLoaded]);

  return (
    <>
      <div className={styles.mapContainer} ref={mapContainerRef} />
      <div className="map-atmospheric-overlay" />
    </>
  );
}
