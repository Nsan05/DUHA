"use client";
// createContext → Creates a global shared data container.

// useContext → Reads data from a context.

// useState → Stores state (data that changes and re-renders UI if function triggered).

// useEffect → Do an action when somehting changes.

// useRef -> Stores value

// useMemo → Caches a calculated value to avoid recalculating every render.
import React, { createContext, useContext, useState, useEffect, useMemo, ReactNode } from "react";
import { CommunityFeatureCollection, TimeOfDay } from "../lib/types";

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
}

const AppContext = createContext<AppContextState | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [timeOfDay, setTimeOfDay] = useState<TimeOfDay>('afternoon');
  const [rawCommunities, setRawCommunities] = useState<CommunityFeatureCollection | null>(null);
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

  // Initial Data Fetch
  useEffect(() => {
    async function fetchCommunities() {
      try {
        setLoading(true);
        const res = await fetch("http://localhost:8000/api/communities");
        if (!res.ok) throw new Error("Failed to fetch community data");
        const data: CommunityFeatureCollection = await res.json();
        setRawCommunities(data);
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
      if (!selectedCommunity) {
        setPixelGridData(null);
        setPixelGridLoading(false);
        setHoveredPixelAnomaly(null); 
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
    pixelGridLoading, setPixelGridLoading
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
