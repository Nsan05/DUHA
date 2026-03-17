"use client";

import React, { useRef, useEffect, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import styles from "./MapView.module.css";
import { useAppContext } from "../../context/AppContext";
import LayerPanel from "../LayerPanel/LayerPanel";

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
    setHoveredCommunity,
    pixelGridData,
    pixelGridLoading,
    setHoveredPixelAnomaly,
    selectedPixel,
    setSelectedPixel,
    interventionMode,
    setInterventionMode,
    setActiveInterventions,
    setModifiedFeatures,
    predictedAnomalies,
    setPredictedAnomalies,
    perPixelAnomalies,
    selectedPixels,
    setSelectedPixels,
    addSelectedPixel,
    removeSelectedPixel,
    pixelInspectorData
  } = useAppContext();

  // Keep a ref of selectedCommunity for the click handler to access which will be updated when the selectedCommunity changes
  const selectedCommunityRef = useRef(selectedCommunity);
  useEffect(() => {
    selectedCommunityRef.current = selectedCommunity;
  }, [selectedCommunity]);

  // Keep a ref of selectedPixel for click handlers - Mapbox event handlers require refs to reliably access the freshest state values
  const selectedPixelRef = useRef(selectedPixel);
  const isPixelGridEnabled = useRef(false);
  const activePixelsRef = useRef<{ hovered: any | null, selected: any | null, multiSelected: any[] }>({ hovered: null, selected: null, multiSelected: [] });
  const timeOfDayRef = useRef(timeOfDay);
  const selectedPixelsRef = useRef(selectedPixels);
  const pixelInspectorDataRef = useRef(pixelInspectorData);
  const perPixelAnomaliesRef = useRef(perPixelAnomalies);
  
  useEffect(() => {
    selectedPixelRef.current = selectedPixel;
  }, [selectedPixel]);
  useEffect(() => {
    timeOfDayRef.current = timeOfDay;
  }, [timeOfDay]);
  useEffect(() => {
    selectedPixelsRef.current = selectedPixels;
  }, [selectedPixels]);
  useEffect(() => {
    pixelInspectorDataRef.current = pixelInspectorData;
  }, [pixelInspectorData]);

  useEffect(() => {
    perPixelAnomaliesRef.current = perPixelAnomalies;
  }, [perPixelAnomalies]);

  // 1. Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (!process.env.NEXT_PUBLIC_MAPBOX_TOKEN) {
      console.error("Missing NEXT_PUBLIC_MAPBOX_TOKEN in .env.local");
      return;
    }
    if (mapRef.current) return;

    // Generate the correct initial style URL based on timeOfDay prop to prevent flashing
    let initialStyle = "mapbox://styles/mapbox/dark-v11";
    if (timeOfDay === "morning") initialStyle = "mapbox://styles/mapbox/navigation-day-v1";
    if (timeOfDay === "afternoon") initialStyle = "mapbox://styles/mapbox/outdoors-v12";

    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: initialStyle,
      center: [55.27, 25.2], // Dubai
      zoom: 11,
      minZoom: 9, 
      maxZoom: 18,
      pitch: 30, // Slight 3D tilt
      bearing: 0,
      attributionControl: true,
      antialias: true,
      boxZoom: false, // Mapbox's default boxZoom swallows Shift+mousedowns. Disable it so we can capture Shift+clicks!
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
      window.removeEventListener("duha:resetView", handleResetView as EventListener);
    };
  }, []);

  // Listener for the DUHA logo reset — defined outside the useEffect so it stays stable
  const handleResetView = () => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({
      center: [55.27, 25.2],
      zoom: 11,
      pitch: 30,
      bearing: 0,
      duration: 1200,
      essential: true,
    });
  };

  // Attach the reset listener once on mount
  React.useEffect(() => {
    window.addEventListener("duha:resetView", handleResetView as EventListener);
    return () => window.removeEventListener("duha:resetView", handleResetView as EventListener);
  }, []);

  // 2. Respond to Time of Day changes by swapping Basemap
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    let newStyle = "mapbox://styles/mapbox/dark-v11"; // Default Night
    if (timeOfDay === "morning") {
      newStyle = "mapbox://styles/mapbox/navigation-day-v1"; // Cool pale blue-grey — crisp dawn feel, distinct from afternoon
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

  // Clear active pixels overlay and states when selected community changes
  useEffect(() => {
    activePixelsRef.current = { hovered: null, selected: null, multiSelected: [] };
    if (mapLoaded && mapRef.current) {
      const activeSrc = mapRef.current.getSource("active-pixels") as mapboxgl.GeoJSONSource;
      if (activeSrc) {
        activeSrc.setData({ type: "FeatureCollection", features: [] });
      }
      
      // CRITICAL: Mapbox remembers feature-state by ID even if the source data is swapped or hidden.
      // We must explicitly wipe all feature states (hover, selected, multiSelected) from the pixel grid. - clearing memory so that the grid is not loaded in from cache
      if (mapRef.current.getSource("pixel-grid")) {
        mapRef.current.removeFeatureState({ source: "pixel-grid" });
      }
    }
  }, [selectedCommunity, mapLoaded]);

  // 3. Render Community Polygons and Handle Interactions
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !computedCommunities) return;

    // Check if source already exists
    if (!map.getSource("communities")) {
      map.addSource("communities", {
        type: "geojson",
        data: computedCommunities as any
      });
    } else {
      // Just update the data if source already exists (e.g., HVI changed)
      (map.getSource("communities") as mapboxgl.GeoJSONSource).setData(computedCommunities as any);
    }

    // Add Fill Layer (colored by HVI) - Gets the layer from added ones tot he map object like below
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
            ["boolean", ["feature-state", "selected"], false],
            0.0, // Completely transparent when selected to see map beneath pixel grid
            ["boolean", ["feature-state", "hover"], false],
            0.70, // Opacity when hovered
            0.30  // Default opacity
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
        const props = e.features[0].properties;
        const commId = props?.COMM_NUM?.toString();
        const featureId = e.features[0].id!;

        // If we are over the selected community, we don't want any hover state. - False if the selected community is being hovered over
        const shouldHover = commId !== selectedCommunityRef.current;

        // Clear previous hover state if moving to a new community, or if we hover the selected community
        if (hoveredStateId !== null) {
          if (hoveredStateId !== featureId || !shouldHover) {
            map.setFeatureState(
              { source: "communities", id: hoveredStateId },
              { hover: false }
            );
            hoveredStateId = null;
          }
        }

        // Apply new hover state if it's NOT the selected community
        if (shouldHover && hoveredStateId !== featureId) {
          hoveredStateId = featureId; 
          map.setFeatureState(
            { source: "communities", id: hoveredStateId },
            { hover: true }
          );
        }
        
        map.getCanvas().style.cursor = "pointer";
        
        // Pass info to state for tooltip (needs to happen even if selected)
        setHoveredCommunity(commId || null);
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
      // PREVENT community toggle if the pixel grid is currently active and rendered
      if (isPixelGridEnabled.current) {
        const pixelFeatures = map.queryRenderedFeatures(e.point, { layers: ["pixel-grid-fill"] });
        if (pixelFeatures.length > 0) return; // Let the dedicated pixel click handler deal with it
      }

      // Check if we clicked on a community polygon
      const features = map.queryRenderedFeatures(e.point, { layers: ["communities-fill"] });
      // If we did indeed click on a real community
      if (features.length > 0) {
        const commId = features[0].properties?.COMM_NUM?.toString();
        if (commId) {
          // Toggle selection if clicking the already selected community
          if (selectedCommunityRef.current === commId) {
            setSelectedCommunity(null);
            setSelectedPixel(null);
          } else {
            setSelectedCommunity(commId);
            setSelectedPixel(null);
          }
        }
      } else {
        // If clicked on water/empty space, deselect
        setSelectedCommunity(null);
        setSelectedPixel(null);
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
      map.off("click", "communities-fill", onMapClick);
    };
  }, [timeOfDay, mapLoaded, computedCommunities]);

  // Handle selected state visually on the main community polygons
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !computedCommunities) return;
    // Ensure map is actually completely loaded with our custom sources
    if (!map.getSource("communities")) return;
    
    // Clear 'selected' feature state for all communities
    computedCommunities.features.forEach((f: any) => {
      if (f.id !== undefined) {
        map.setFeatureState(
          { source: "communities", id: f.id },
          { selected: false }
        );
      }
    });

    // Set 'selected' state for the actively selected community ONLY when pixel grid finishes loading
    // Selcted state makes the community polygon transparent to see the pixel grid - line 136 mentioned
    if (selectedCommunity && !pixelGridLoading) {
      const activeFeature = computedCommunities.features.find(
        (f: any) => f.properties.COMM_NUM.toString() === selectedCommunity
      );
      if (activeFeature && activeFeature.id !== undefined) {
        map.setFeatureState(
          { source: "communities", id: activeFeature.id },
          { selected: true }
        );
      }
    }
  }, [selectedCommunity, computedCommunities, mapLoaded, pixelGridLoading]);

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

  // 5. Render Pixel Grid and Handle Cell Interactions
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    // If there is no data then hide the pixel gird and close pop up
    // Hide pixel grid if no community selected
    if (!pixelGridData || !pixelGridData.grid || !selectedCommunity) {
      isPixelGridEnabled.current = false;
      if (map.getLayer("pixel-grid-fill")) {
        map.setLayoutProperty("pixel-grid-fill", "visibility", "none");
        map.setLayoutProperty("pixel-grid-outline", "visibility", "none");
        if (map.getLayer("active-pixels-extrusion")) {
          map.setLayoutProperty("active-pixels-extrusion", "visibility", "none");
        }
      }
      activePixelsRef.current = { hovered: null, selected: null, multiSelected: [] };
      
      const activeSrc = map.getSource("active-pixels") as mapboxgl.GeoJSONSource;
      if (activeSrc) activeSrc.setData({ type: "FeatureCollection", features: [] });
      
      setHoveredPixelAnomaly(null);
      return;
    }

    const source = map.getSource("pixel-grid") as mapboxgl.GeoJSONSource;
    // Mapbox needs an ID to manage feature states (like hover) correctly
    // auto-generate integer IDs inside the source initialization
    // If no source then source is added
    if (!source) {
      map.addSource("pixel-grid", {
        type: "geojson",
        data: pixelGridData.grid,
        generateId: true // gives each pixel an unique ID
      });

      // 1. The flat 2D grid for the background
      map.addLayer({
        id: "pixel-grid-fill",
        type: "fill",
        source: "pixel-grid",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "anomaly"],
            -4, "#1E90FF",   // Very Cool (Dark Blue)
            -2, "#87CEEB",   // Cool (Light Blue)
            -0.5, "#E0F7FA", // Slightly Cool
            0, "#F5F5F5",    // Neutral
            0.5, "#FFF9C4",  // Slightly Warm
            2, "#FFA500",    // Hot (Orange)
            4, "#FF4500"     // Very Hot (Red)
          ],
          "fill-opacity": [
            "case",
             // completely hide selected/hovered so the 3D block underneath takes over visual space
            ["boolean", ["feature-state", "selected"], false], 0.0,
            ["boolean", ["feature-state", "multiSelected"], false], 0.0,
            ["boolean", ["feature-state", "hover"], false], 0.0,
            0.30  // Default opacity shows underlying map nicely
          ]
        }
      }, "communities-outline");

      // 2. The dynamic 3D overlay for just the active/hovered pixels to bypass mapbox opacity limits
      if (!map.getSource("active-pixels")) {
        map.addSource("active-pixels", {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] }
        });
        
        map.addLayer({
          id: "active-pixels-extrusion",
          type: "fill-extrusion", // 3D Column
          source: "active-pixels",
          paint: {
            "fill-extrusion-color": [
              "case", // if condition
              // If we have a prediction override
              ["has", "isPredicted"],
              [
                "interpolate",
                ["linear"],
                ["get", "anomaly"],
                -4, "#1E90FF",
                -2, "#87CEEB",
                -0.5, "#E0F7FA",
                0, "#F5F5F5",
                0.5, "#FFF9C4",
                2, "#FFA500",
                4, "#FF4500"
              ],
              // Else, use normal selection colours
              // The pixel is both selected and multiselcted, adding a dark cyan color
              ["all", ["boolean", ["get", "isSelected"], false], ["boolean", ["get", "isMultiSelected"], false]],
              "#00838F", // Darker Cyan for the active primary pixel
              ["boolean", ["get", "isMultiSelected"], false],
              "#00BCD4", // Cyan block for multi-select
              // Normal single hover/select default
              [
                "interpolate",
                ["linear"],
                ["get", "anomaly"],
                -4, "#1E90FF",
                -2, "#87CEEB",
                -0.5, "#E0F7FA",
                0, "#F5F5F5",
                0.5, "#FFF9C4",
                2, "#FFA500",
                4, "#FF4500"
              ]
            ],
            "fill-extrusion-opacity": 0.70, // Solid opaque column!
            "fill-extrusion-height": [
              "case",
              ["all", ["boolean", ["get", "isSelected"], false], ["boolean", ["get", "isMultiSelected"], false]],
              32,  // Primary multi-selected height (slightly taller)
              ["boolean", ["get", "isSelected"], false],
              50,  // Selected pop logic
              ["boolean", ["get", "isMultiSelected"], false],
              30,  // Multi-selected height
              10   // Hover pop logic
            ],
            "fill-extrusion-base": 0
          }
        }, "communities-outline");
      }

      map.addLayer({
        id: "pixel-grid-outline",
        type: "line",
        source: "pixel-grid",
        paint: {
          "line-color": [
            "case",
            ["all", ["boolean", ["feature-state", "selected"], false], ["boolean", ["feature-state", "multiSelected"], false]],
            "#00838F", // Darker border for primary
            ["boolean", ["feature-state", "multiSelected"], false],
            "#00BCD4", // Cyan border for multi-select
            "rgba(255, 255, 255, 0.15)"
          ],
          "line-width": [
            "case",
            ["boolean", ["feature-state", "multiSelected"], false],
            2,
            1
          ]
        }
      }, "communities-outline"); // Before community outlines


      // Hover event logic for pixels
      let hoveredPixelId: number | string | null = null;
      
      const updateActive3DPixels = () => {
        const source = map.getSource("active-pixels") as mapboxgl.GeoJSONSource;
        if (!source) return;
        const feats = []; // Empty array to store features to draw as 3D columns (hover, select, multi)
        const hasMulti = selectedPixelsRef.current.length > 0;
        
        // Helper to get anomaly override index by getting the index position of the pixel in the selectedPixelsRef array
        const getAnomalyOverride = (pixelId: number | string) => {
          // If no predictions, return undefined
          if (!perPixelAnomaliesRef.current) return undefined;
          // Find the index of this pixel in selectedPixelsRef to grab the corresponding prediction
          const idx = selectedPixelsRef.current.findIndex(p => p.id === pixelId);
          if (idx !== -1 && idx < perPixelAnomaliesRef.current.length) {
            return perPixelAnomaliesRef.current[idx];
          }
          return undefined;
        };

        // If hovered pixel is not the same as the selected pixel, add it to the feats array
        if (activePixelsRef.current.hovered && activePixelsRef.current.hovered.id !== activePixelsRef.current.selected?.id) {
          feats.push({ ...activePixelsRef.current.hovered, properties: { ...activePixelsRef.current.hovered.properties, isSelected: false } });
        }
        // Primary selected pixel
        if (activePixelsRef.current.selected) {
          // Get override value of the selected pixel
          const overrideVal = getAnomalyOverride(activePixelsRef.current.selected.id);
          feats.push({ 
            ...activePixelsRef.current.selected, 
            properties: { 
              ...activePixelsRef.current.selected.properties, 
              // If override value exists, add it to the feats array in the anomaly property (replace the old one)
              ...(overrideVal !== undefined ? { anomaly: overrideVal, isPredicted: true } : {}),
              isSelected: true, // we keep this TRUE so the layer logic knows it's the primary pixel
              isMultiSelected: hasMulti 
            } 
          });
        }
        // Goes through each multiselected pixel
        activePixelsRef.current.multiSelected.forEach(f => {
          // If seelcted pixel is there in multiselect dont do anything as we already have it
          if (activePixelsRef.current.selected && f.id === activePixelsRef.current.selected.id) return;
          // If the hover pixel, dont add it to the feats array as we already added it before
          if (activePixelsRef.current.hovered && f.id === activePixelsRef.current.hovered.id) return;
          
          // get anomaly value for each of the selected pixels and override it if it exsits
          const overrideVal = getAnomalyOverride(f.id);
          // Add normal multi-selected pixels
          feats.push({ 
             ...f, 
             properties: { 
               ...f.properties, 
               ...(overrideVal !== undefined ? { anomaly: overrideVal, isPredicted: true } : {}),
               isMultiSelected: true 
             } 
          });
        });
        source.setData({ type: "FeatureCollection", features: feats as any });
      };

      // event when the mouse on top of a pixel
      map.on("mousemove", "pixel-grid-fill", (e) => {
        if (e.features && e.features.length > 0) {
          map.getCanvas().style.cursor = "crosshair";
          
          if (hoveredPixelId !== null) {
            map.setFeatureState(
              { source: "pixel-grid", id: hoveredPixelId },
              { hover: false } // turn off previous hover
            );
          }
          // set new hover
          hoveredPixelId = e.features[0].id!;
          map.setFeatureState(
            { source: "pixel-grid", id: hoveredPixelId },
            { hover: true }
          );

          // update 3D layer
          activePixelsRef.current.hovered = {
            type: "Feature",
            geometry: e.features[0].geometry,
            properties: e.features[0].properties,
            id: hoveredPixelId
          } as any;
          updateActive3DPixels();

          // Update hovered pixel anomaly state instead of local popup
          const anomaly = e.features[0].properties?.anomaly;
          setHoveredPixelAnomaly(anomaly);
        }
      });

      // Click event logic for pixels
      let clickedPixelId: number | string | null = null;

      map.on("click", "pixel-grid-fill", (e) => {
        // PREVENT the event from bubbling down to the community polygon click handler
        e.originalEvent.stopPropagation();
        
        // If the global state considers no pixel as active (e.g., navigated back to Community View), 
        // silently flush the stale active pixel ID from the map event closure state.
        if (selectedPixelRef.current === null) {
          clickedPixelId = null;
        }

        if (e.features && e.features.length > 0) {
          const feature = e.features[0];
          const pixelId = feature.id!;
          
          if (e.originalEvent.shiftKey) {
            // Prevents the default behaviour of rectangle tool box
            e.originalEvent.preventDefault();
            
            // Check if already exactly present in selected pixels or not by ID - If yes then remove it
            // Shift click again deselects a pixel
            if (selectedPixelsRef.current.some(p => p.id === pixelId)) {
               removeSelectedPixel(pixelId);
               return; 
            }
            
            // Auto-add the initially selected pixel to `selectedPixels` at first using clickedPixelID which only changes on normal clicks and not shift clicks
            if (selectedPixelsRef.current.length === 0 && clickedPixelId !== null && clickedPixelId !== pixelId && pixelInspectorDataRef.current) {
                if (selectedPixelRef.current) {
                  addSelectedPixel({
                      id: clickedPixelId,
                      lat: selectedPixelRef.current.lat,
                      lng: selectedPixelRef.current.lng,
                      anomaly: selectedPixelRef.current.anomaly,
                      features: pixelInspectorDataRef.current.features,
                      anomalies: pixelInspectorDataRef.current.anomalies
                  });
                }
            }

            map.getCanvas().style.cursor = "wait";
            
            // fetch features to add to multi-select for the selcted pixel
            fetch(`http://localhost:8000/api/pixel`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ lat: e.lngLat.lat, lon: e.lngLat.lng, time_of_day: timeOfDayRef.current }),
            })
            .then(res => res.json())
            .then(data => {
              addSelectedPixel({
                id: pixelId,
                lat: e.lngLat.lat,
                lng: e.lngLat.lng,
                anomaly: feature.properties!.anomaly,
                features: data.features,
                anomalies: data.anomalies
              });


              // Checks if the pixel has been added to the multiselect already visually
              if (!activePixelsRef.current.multiSelected.find(f => f.id === pixelId)) {
                map.setFeatureState({ source: "pixel-grid", id: pixelId }, { multiSelected: true });
                activePixelsRef.current.multiSelected.push({
                  type: "Feature",
                  geometry: feature.geometry,
                  properties: feature.properties,
                  id: pixelId
                });
                updateActive3DPixels();
              }
              
              // If NO pixel was previously active, shift-clicking essentially starts the pixel mode.
              // We must set it as the anchor selectedPixel so the the UI transitions from Community to Pixel.
              if (selectedPixelsRef.current.length === 0 && clickedPixelId === null) {
                // Mark pixel as new anchor
                clickedPixelId = pixelId;
                // Trigger the global state to switch the Right Sidebar over to the Pixel view
                setSelectedPixel({
                  lat: e.lngLat.lat,
                  lng: e.lngLat.lng,
                  anomaly: feature.properties!.anomaly
                });
                // Also update the view on the map with 3D structure
                activePixelsRef.current.selected = {
                  type: "Feature",
                  geometry: feature.geometry,
                  properties: feature.properties,
                  id: clickedPixelId
                } as any;
                map.setFeatureState(
                  { source: "pixel-grid", id: clickedPixelId },
                  { selected: true }
                );
              }

              map.getCanvas().style.cursor = "crosshair";
            })
            .catch(err => {
              console.error(err);
              map.getCanvas().style.cursor = "crosshair";
            });
            
          } else {
            // Normal click
            
            // Clear any multi-selection we had
            setSelectedPixels([]);
            setInterventionMode(false);
            setActiveInterventions([]);
            setModifiedFeatures(null);
            setPredictedAnomalies(null);
            
            // Clear previous selection visually
            if (clickedPixelId !== null) {
              map.setFeatureState(
                { source: "pixel-grid", id: clickedPixelId },
                { selected: false, multiSelected: false } // Force clear multiSelected too!
              );
            }

            // Set new selection visually
            clickedPixelId = pixelId;
            map.setFeatureState(
              { source: "pixel-grid", id: clickedPixelId },
              { selected: true }
            );

            activePixelsRef.current.selected = {
              type: "Feature",
              geometry: feature.geometry,
              properties: feature.properties,
              id: clickedPixelId
            } as any;
            updateActive3DPixels();

            // Fly to the pixel slightly to center it
            map.panTo(e.lngLat, { duration: 800 });

            // Dispatch to AppContext to trigger inspector
            const anomaly = feature.properties?.anomaly;
            setSelectedPixel({
              lat: e.lngLat.lat,
              lng: e.lngLat.lng,
              anomaly: anomaly
            });
          }
        }
      });

      // When the mouse leaves the pixel grid entirely
      map.on("mouseleave", "pixel-grid-fill", () => {
        // the last pixel value that was registered before the cursor left the pixel grid
        if (hoveredPixelId !== null) {
          map.setFeatureState(
            { source: "pixel-grid", id: hoveredPixelId },
            { hover: false }
          );
        }
        hoveredPixelId = null;
        map.getCanvas().style.cursor = "";
        
        activePixelsRef.current.hovered = null;
        updateActive3DPixels();
        
        setHoveredPixelAnomaly(null);
      });

      isPixelGridEnabled.current = true;
    } else {
      source.setData(pixelGridData.grid);
      map.setLayoutProperty("pixel-grid-fill", "visibility", "visible");
      map.setLayoutProperty("pixel-grid-outline", "visibility", "visible");
      if (map.getLayer("active-pixels-extrusion")) {
        map.setLayoutProperty("active-pixels-extrusion", "visibility", "visible");
      }
      isPixelGridEnabled.current = true;
    }
  }, [pixelGridData, mapLoaded, selectedCommunity]);

  // Update mapbox feature states for multi-selection
  // Upper effect: updates the map when the user interacts with pixels
  // Lower effect: updates the map when the underlying data (like predicted anomalies or selected pixels) changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    // No multiselected features - Switched back to normal or cleared multi
    if (selectedPixels.length === 0) {
      // Remove previous selected styling
      activePixelsRef.current.multiSelected.forEach(f => {
        map.setFeatureState({ source: "pixel-grid", id: f.id }, { multiSelected: false });
      });
      activePixelsRef.current.multiSelected = [];
      // fixed bug of selected pixel still marked as multi
      if (activePixelsRef.current.selected) {
        map.setFeatureState({ source: "pixel-grid", id: activePixelsRef.current.selected.id }, { multiSelected: false });
      }
    } else { // Yes multi-selected features
      // Filter out removes
      // activePixelsRef - Mapbox cache used for rendering visual things
      // Selectedpixel used as the actual app context state
      const validIds = new Set(selectedPixels.map(p => p.id)); // set lookups are faster
      const removed = activePixelsRef.current.multiSelected.filter(f => !validIds.has(f.id));
      if (removed.length > 0) {
        // Update styling for removed pixels
        removed.forEach(f => {
          map.setFeatureState({ source: "pixel-grid", id: f.id }, { multiSelected: false });
        });
        // Update cache to valid pixels alone
        activePixelsRef.current.multiSelected = activePixelsRef.current.multiSelected.filter(f => validIds.has(f.id));
      }
      // // If the primary selected pixel is no longer in the selectedPixels array, remove its multiSelected styling
      // if (activePixelsRef.current.selected && !validIds.has(activePixelsRef.current.selected.id)) {
      //   map.setFeatureState({ source: "pixel-grid", id: activePixelsRef.current.selected.id }, { multiSelected: false });
      // }
    }

    // Force redraw of 3D array
    // First normal click on a pixel → goes to activePixelsRef.current.selected
    // Every shift+click after that → goes to activePixelsRef.current.multiSelected (an array)
    const activeSrc = map.getSource("active-pixels") as mapboxgl.GeoJSONSource;
    if (activeSrc) {
      const feats = [];
      const hasMulti = selectedPixels.length > 0;
      
      const getAnomalyOverride = (pixelId: number | string) => {
        if (!perPixelAnomalies) return undefined;
        const idx = selectedPixels.findIndex(p => p.id === pixelId);
        if (idx !== -1 && idx < perPixelAnomalies.length) {
          return perPixelAnomalies[idx];
        }
        return undefined;
      };

      if (activePixelsRef.current.hovered && activePixelsRef.current.hovered.id !== activePixelsRef.current.selected?.id) {
        feats.push({ ...activePixelsRef.current.hovered, properties: { ...activePixelsRef.current.hovered.properties, isSelected: false } });
      }
      if (activePixelsRef.current.selected) {
        const overrideVal = getAnomalyOverride(activePixelsRef.current.selected.id);
        feats.push({ 
          ...activePixelsRef.current.selected, 
          properties: { 
            ...activePixelsRef.current.selected.properties, 
            ...(overrideVal !== undefined ? { anomaly: overrideVal, isPredicted: true } : {}),
            isSelected: true, // Keep it true so we can style the primary item distinctly
            isMultiSelected: hasMulti 
          } 
        });
        // We also need to force the line border state! 
        map.setFeatureState({ source: "pixel-grid", id: activePixelsRef.current.selected.id }, { multiSelected: hasMulti });
      }
      activePixelsRef.current.multiSelected.forEach(f => {
        if (activePixelsRef.current.selected && f.id === activePixelsRef.current.selected.id) return;
        if (activePixelsRef.current.hovered && f.id === activePixelsRef.current.hovered.id) return;
        
        const overrideVal = getAnomalyOverride(f.id);
        feats.push({ 
          ...f, 
          properties: { 
             ...f.properties, 
             ...(overrideVal !== undefined ? { anomaly: overrideVal, isPredicted: true } : {}),
             isMultiSelected: true 
          } 
        });
      });
      activeSrc.setData({ type: "FeatureCollection", features: feats as any });
    }
  }, [selectedPixels, perPixelAnomalies, mapLoaded]);

  return (
    <>
      {pixelGridLoading && (
        <div className={styles.pixelLoader}>
          <div className={styles.spinner} />
          Loading Community Heat Map...
        </div>
      )}
      <div className={styles.mapContainer} ref={mapContainerRef} />
      <LayerPanel map={mapRef.current} />
      <div className="map-atmospheric-overlay" />
    </>
  );
}
