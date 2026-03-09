"use client";
// createContext → Creates a global shared data container.

// useContext → Reads data from a context.

// useState → Stores state (data that changes and re-renders UI if function triggered).

// useEffect → Do an action when somehting changes.

// useRef -> Stores value

// useMemo → Caches a calculated value to avoid recalculating every render.
import React, { createContext, useContext, useState, useEffect, useMemo, ReactNode } from "react";
import { CommunityFeatureCollection, TimeOfDay } from "../lib/types";
import { FeatureVector, InterventionId, InterventionParams } from "../lib/interventions";

// The shape of our global state - shared by all componeents
interface AppContextState {
  timeOfDay: TimeOfDay;
  setTimeOfDay: (time: TimeOfDay) => void;
  
  // RAW data from backend
  rawCommunities: CommunityFeatureCollection | null;
  // COMPUTED data with HVI and Priority tags (changes based on timeOfDay)
  computedCommunities: CommunityFeatureCollection | null;
  
  selectedCommunity: string | null;
  setSelectedCommunity: (id: string | null) => void;
  hoveredCommunity: string | null;
  setHoveredCommunity: (id: string | null) => void;
  hoveredPixelAnomaly: number | null;
  setHoveredPixelAnomaly: (val: number | null) => void;
  
  loading: boolean;
  error: string | null;
  
  // F17 controls
  showPriorityOnly: boolean;
  setShowPriorityOnly: (show: boolean) => void;
  
  // F2 sorting controls
  sortField: string;
  setSortField: (field: string) => void;
  sortDirection: 'asc' | 'desc';
  setSortDirection: (dir: 'asc' | 'desc') => void;

  // Phase 2: Community Pixel Grid
  pixelGridData: any | null;
  setPixelGridData: (data: any | null) => void;
  pixelGridLoading: boolean;
  setPixelGridLoading: (loading: boolean) => void;

  // Phase 3: Pixel Inspector
  selectedPixel: { lat: number; lng: number; anomaly: number } | null;
  setSelectedPixel: (pixel: { lat: number; lng: number; anomaly: number } | null) => void;
  pixelInspectorData: any | null;
  setPixelInspectorData: (data: any | null) => void;
  pixelInspectorLoading: boolean;
  setPixelInspectorLoading: (loading: boolean) => void;

  // Phase 3: Dynamic Radar Constraints
  globalFeatureRanges: Record<string, [number, number]> | null;

  // Phase 4: Intervention Simulator
  interventionMode: boolean;
  setInterventionMode: (mode: boolean) => void;

  selectedPixels: Array<{
    id: string | number;
    lat: number;
    lng: number;
    anomaly: number;
    features: FeatureVector;
    anomalies: { morning: number; afternoon: number; night: number };
  }>;
  setSelectedPixels: (pixels: Array<{ id: string | number; lat: number; lng: number; anomaly: number; features: FeatureVector; anomalies: { morning: number; afternoon: number; night: number } }>) => void;
  addSelectedPixel: (pixel: { id: string | number; lat: number; lng: number; anomaly: number; features: FeatureVector; anomalies: { morning: number; afternoon: number; night: number } }) => void;
  removeSelectedPixel: (id: string | number) => void;

  modifiedFeatures: FeatureVector | null;
  setModifiedFeatures: (f: FeatureVector | null) => void;

  predictedAnomalies: { morning: number; afternoon: number; night: number } | null;
  setPredictedAnomalies: (a: { morning: number; afternoon: number; night: number } | null) => void;

  activeInterventions: Array<{ templateId: InterventionId; params?: InterventionParams }>;
  setActiveInterventions: (i: Array<{ templateId: InterventionId; params?: InterventionParams }>) => void;

  expertMode: boolean;
  setExpertMode: (mode: boolean) => void;
}

const AppContext = createContext<AppContextState | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [timeOfDay, setTimeOfDay] = useState<TimeOfDay>('afternoon');
  const [rawCommunities, setRawCommunities] = useState<CommunityFeatureCollection | null>(null);
  const [globalFeatureRanges, setGlobalFeatureRanges] = useState<Record<string, [number, number]> | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  // Selection/Hover state
  const [selectedCommunity, setSelectedCommunity] = useState<string | null>(null);
  const [hoveredCommunity, setHoveredCommunity] = useState<string | null>(null);
  const [hoveredPixelAnomaly, setHoveredPixelAnomaly] = useState<number | null>(null);
  
  // Panel controls
  const [showPriorityOnly, setShowPriorityOnly] = useState<boolean>(false);
  const [sortField, setSortField] = useState<string>('hvi');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Phase 2 data
  const [pixelGridData, setPixelGridData] = useState<any | null>(null);
  const [pixelGridLoading, setPixelGridLoading] = useState<boolean>(false);

  // Phase 3 data
  const [selectedPixel, setSelectedPixel] = useState<{ lat: number; lng: number; anomaly: number } | null>(null);
  const [pixelInspectorData, setPixelInspectorData] = useState<any | null>(null);
  const [pixelInspectorLoading, setPixelInspectorLoading] = useState<boolean>(false);

  // Phase 4 data
  const [interventionMode, setInterventionMode] = useState<boolean>(false);
  const [selectedPixels, setSelectedPixels] = useState<Array<{ id: string | number; lat: number; lng: number; anomaly: number; features: FeatureVector; anomalies: { morning: number; afternoon: number; night: number } }>>([]);
  const [modifiedFeatures, setModifiedFeatures] = useState<FeatureVector | null>(null);
  const [predictedAnomalies, setPredictedAnomalies] = useState<{ morning: number; afternoon: number; night: number } | null>(null);
  const [activeInterventions, setActiveInterventions] = useState<Array<{ templateId: InterventionId; params?: InterventionParams }>>([]);
  const [expertMode, setExpertMode] = useState<boolean>(false);

  const addSelectedPixel = (pixel: { id: string | number; lat: number; lng: number; anomaly: number; features: FeatureVector; anomalies: { morning: number; afternoon: number; night: number } }) => {
    // prev selected pixels
    setSelectedPixels(prev => {
      // Check if already exactly present in selected pixels or not by ID
      if (prev.some(p => p.id === pixel.id)) return prev;
      return [...prev, pixel];
    });
    setInterventionMode(true);
  };

  const removeSelectedPixel = (id: string | number) => {
    setSelectedPixels(prev => {
      // Only keeping items that do not match the id to be removed
      const next = prev.filter(p => p.id !== id);
      if (next.length === 0) setInterventionMode(false);
      return next;
    });
  };

  // Initial Data Fetch
  useEffect(() => {
    async function fetchCommunities() {
      try {
        setLoading(true);
        const res = await fetch("http://localhost:8000/api/communities");
        if (!res.ok) throw new Error("Failed to fetch community data");
        const data: CommunityFeatureCollection = await res.json();
        setRawCommunities(data);
        if (data.global_feature_ranges) {
          setGlobalFeatureRanges(data.global_feature_ranges);
        }
      } catch (err: any) {
        console.error("Error fetching communities:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchCommunities();
  }, []);

  // Fetch Pixel Grid when a community is selected or timeOfDay changes
  useEffect(() => {
    async function fetchPixelGrid() {
      // Phase 4 clears
      setSelectedPixels([]);
      setModifiedFeatures(null);
      setPredictedAnomalies(null);
      setActiveInterventions([]);
      setInterventionMode(false);

      if (!selectedCommunity) {
        setPixelGridData(null);
        setPixelGridLoading(false);
        setHoveredPixelAnomaly(null); 
        setSelectedPixel(null); // Phase 3: clear pixel state when leaving community view
        return;
      }
      try {
        setPixelGridData(null); // Instantly clear old grid while loading new one
        setPixelGridLoading(true);
        const res = await fetch(`http://localhost:8000/api/community/${selectedCommunity}/pixels?time=${timeOfDay}`);
        if (!res.ok) throw new Error("Failed to fetch pixel grid data");
        const data = await res.json();
        setPixelGridData(data);
      } catch (err) {
        console.error("Error fetching pixel grid:", err);
        setPixelGridData(null);
      } finally {
        setPixelGridLoading(false);
      }
    }
    fetchPixelGrid();
  }, [selectedCommunity, timeOfDay]);

  // Phase 3: Fetch Pixel Inspector Data when a pixel is selected or timeOfDay changes
  useEffect(() => {
    async function fetchPixelData() {
      if (!selectedPixel) {
        setPixelInspectorData(null);
        setPixelInspectorLoading(false);
        return;
      }

      setPixelInspectorLoading(true);
      try {
        // Parallel fetch for speed
        const [pixelRes, shapRes] = await Promise.all([
          fetch("http://localhost:8000/api/pixel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lat: selectedPixel.lat, lon: selectedPixel.lng, time_of_day: timeOfDay }),
          }),
          fetch("http://localhost:8000/api/shap", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lat: selectedPixel.lat, lon: selectedPixel.lng, time_of_day: timeOfDay }),
          })
        ]);

        if (!pixelRes.ok || !shapRes.ok) throw new Error("Failed to fetch pixel inspector data");

        const pixelData = await pixelRes.json();
        const shapData = await shapRes.json();

        setPixelInspectorData({
          features: pixelData.features,
          anomalies: pixelData.anomalies,
          shap_values: shapData.shap_values,
          explanation: shapData.explanation,
          base_value: shapData.base_value,
        });
      } catch (err) {
        console.error("Error fetching pixel inspector data:", err);
        setPixelInspectorData(null);
      } finally {
        setPixelInspectorLoading(false);
      }
    }
    fetchPixelData();
  }, [selectedPixel, timeOfDay]);

  // Step 2: HVI Computation whenever timeOfDay or raw data changes. - Does normalisation first
  // Using useMemo is perfectly safe and prevents useEffect cyclic dependency issues.
  const computedCommunities = useMemo(() => {
    if (!rawCommunities) return null;
    
    // Deep clone to avoid mutating raw state
    const collection: CommunityFeatureCollection = JSON.parse(JSON.stringify(rawCommunities));
    const features = collection.features;
    
    // 1. Find min/max for normalization across all communities
    let minPop = Infinity, maxPop = -Infinity;
    let minAnom = Infinity, maxAnom = -Infinity;
    let minExtr = Infinity, maxExtr = -Infinity;
    
    features.forEach(f => {
      const props = f.properties;
      const pop = props.population || 0;
      
      let meanAnom = 0;
      let extPct = 0;
      
      if (timeOfDay === 'morning') {
        meanAnom = props.anomaly_morning_mean;
        extPct = props.anomaly_morning_extreme_pct;
      } else if (timeOfDay === 'afternoon') {
        meanAnom = props.anomaly_afternoon_mean;
        extPct = props.anomaly_afternoon_extreme_pct;
      } else {
        meanAnom = props.anomaly_night_mean;
        extPct = props.anomaly_night_extreme_pct;
      }
      
      if (pop < minPop) minPop = pop;
      if (pop > maxPop) maxPop = pop;
      if (meanAnom < minAnom) minAnom = meanAnom;
      if (meanAnom > maxAnom) maxAnom = meanAnom;
      if (extPct < minExtr) minExtr = extPct;
      if (extPct > maxExtr) maxExtr = extPct;
    });
    
    const normalize = (val: number, min: number, max: number) => {
      if (max === min) return 0;
      return (val - min) / (max - min);
    };

    // Calculate median population for Priority logic
    const pops = features.map(f => f.properties.population || 0).sort((a, b) => a - b);
    const medianPop = pops[Math.floor(pops.length / 2)] || 0;

    // 2. Compute HVI for each community specifically for the active timeOfDay
    features.forEach(f => {
      const props = f.properties;
      const pop = props.population || 0;
      
      let meanAnom = 0;
      let extPct = 0;
      if (timeOfDay === 'morning') {
        meanAnom = props.anomaly_morning_mean;
        extPct = props.anomaly_morning_extreme_pct;
      } else if (timeOfDay === 'afternoon') {
        meanAnom = props.anomaly_afternoon_mean;
        extPct = props.anomaly_afternoon_extreme_pct;
      } else {
        meanAnom = props.anomaly_night_mean;
        extPct = props.anomaly_night_extreme_pct;
      }

      const nPop = normalize(pop, minPop, maxPop);
      const nAnom = normalize(meanAnom, minAnom, maxAnom);
      const nExtr = normalize(extPct, minExtr, maxExtr);

      // Weights: 40% Anomaly, 30% Population, 30% Extreme Heat Pixels
      const hvi = (0.4 * nAnom) + (0.3 * nPop) + (0.3 * nExtr);
      props.hvi = Math.round(hvi * 100); // 0 to 100 integer scale

      // Priority Exposure flag: HVI > 60 (Top 40% roughly) AND Population > Median
      props.priorityExposure = props.hvi > 60 && pop > medianPop;

      // Assign explicit top-level ID for MapBox feature state binding
      // Ensure it's a number (MapBox strongly prefers integer IDs for feature-state)
      f.id = props.COMM_NUM;
    });
    
    return collection;
  }, [rawCommunities, timeOfDay]);

  const value = {
    timeOfDay, setTimeOfDay,
    rawCommunities, computedCommunities,
    selectedCommunity, setSelectedCommunity,
    hoveredCommunity, setHoveredCommunity,
    hoveredPixelAnomaly, setHoveredPixelAnomaly,
    loading, error,
    showPriorityOnly, setShowPriorityOnly,
    sortField, setSortField,
    sortDirection, setSortDirection,
    pixelGridData, setPixelGridData,
    pixelGridLoading, setPixelGridLoading,
    selectedPixel, setSelectedPixel,
    pixelInspectorData, setPixelInspectorData,
    pixelInspectorLoading, setPixelInspectorLoading,
    globalFeatureRanges,
    interventionMode, setInterventionMode,
    selectedPixels, setSelectedPixels,
    addSelectedPixel, removeSelectedPixel,
    modifiedFeatures, setModifiedFeatures,
    predictedAnomalies, setPredictedAnomalies,
    activeInterventions, setActiveInterventions,
    expertMode, setExpertMode
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppContext() {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error("useAppContext must be used within an AppProvider");
  }
  return context;
}
