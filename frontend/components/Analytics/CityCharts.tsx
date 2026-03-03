"use client";

import React, { useMemo } from "react";
import { 
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  BarChart, Bar, Legend, Cell,
  LineChart, Line
} from "recharts";
import { useAppContext } from "../../context/AppContext";
import styles from "./CityCharts.module.css";
import { CommunityFeature } from "../../lib/types";

// Custom Tooltip for Recharts - Pop up for hovering over chart point
const CustomTooltip = ({ active, payload, label }: any) => {
  // If tooltip is active and there is data
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className={styles.customTooltip}>
        <div className={styles.tooltipTitle}>{data.name || label}</div> 
        {payload.map((entry: any, index: number) => (
          <div key={`item-${index}`} className={styles.tooltipRow}>
            <span className={styles.tooltipLabel}>{entry.name}:</span>
            <span className={styles.tooltipValue} style={{ color: entry.color }}>
              {typeof entry.value === 'number' ? entry.value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : entry.value}
            </span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

export default function CityCharts() {
  const { computedCommunities, timeOfDay } = useAppContext();

  // 1. Data for Scatter Plot (Population vs Anomaly)
  const scatterData = useMemo(() => {
    if (!computedCommunities) return [];
    return computedCommunities.features.map((f: CommunityFeature) => {
      const props = f.properties;
      const anomaly = timeOfDay === "morning" ? props.anomaly_morning_mean : 
                      timeOfDay === "afternoon" ? props.anomaly_afternoon_mean : props.anomaly_night_mean;
      return {
        id: props.COMM_NUM,
        name: props.CNAME_E,
        population: props.population || 0,
        temp: anomaly,
        hvi: props.hvi || 0
      };
    }).filter(d => d.population > 0); // Ignore unpopulated areas
  }, [computedCommunities, timeOfDay]);

  // 2. Data for Stacked Bar (Land Comp of Hottest vs Coolest)
  const barData = useMemo(() => {
    if (!computedCommunities) return [];
    
    // Sort all communities by current anomaly
    const sorted = [...computedCommunities.features].sort((a, b) => {
      const anomA = timeOfDay === "morning" ? a.properties.anomaly_morning_mean : 
                    timeOfDay === "afternoon" ? a.properties.anomaly_afternoon_mean : a.properties.anomaly_night_mean;
      const anomB = timeOfDay === "morning" ? b.properties.anomaly_morning_mean : 
                    timeOfDay === "afternoon" ? b.properties.anomaly_afternoon_mean : b.properties.anomaly_night_mean;
      return anomB - anomA; // Descending (hottest first)
    });

    const hottest = sorted.slice(0, 5);
    const coolest = sorted.slice(-5).reverse();

    const formatData = (features: CommunityFeature[], groupName: string, emoji: string) => {
      return features.map(f => {
        // truncate to 15 chars and add emoji prefix
        let shortName = f.properties.CNAME_E.substring(0, 15) + (f.properties.CNAME_E.length > 15 ? '...' : '');
        return {
          name: `${emoji} ${shortName}`,
          group: groupName,
          Greenery: (f.properties.green_fraction || 0) * 100, 
          Sand: (f.properties.sand_fraction_mean || 0) * 100,
          Water: (f.properties.water_fraction_mean || 0) * 100,
          Built: (f.properties.building_density_mean || 0) * 100
        };
      });
    };

    // Use an empty separator row for visual demarcation between the hot and cool groups
    const separator = { name: " ", group: "separator", Greenery: 0, Sand: 0, Water: 0, Built: 0 };

    return [
      ...formatData(hottest, "Top 5 Hottest", "🔥"), 
      separator,
      ...formatData(coolest, "Top 5 Coolest", "❄️")
    ];
  }, [computedCommunities, timeOfDay]);

  // 3. Data for Histogram (Anomaly Distribution)
  const histData = useMemo(() => {
    if (!computedCommunities) return [];
    
    // Extract just the anomalies
    const anomalies = computedCommunities.features.map(f => {
       return timeOfDay === "morning" ? f.properties.anomaly_morning_mean : 
              timeOfDay === "afternoon" ? f.properties.anomaly_afternoon_mean : f.properties.anomaly_night_mean;
    });

    if (anomalies.length === 0) return [];

    // Dynamically calculate min and max to ensure no communities are dropped
    const minVal = Math.floor(Math.min(...anomalies));
    const maxVal = Math.ceil(Math.max(...anomalies));
    
    // Create bins in 1.0 degree increments to keep the chart clean even if range is large
    const bins: number[] = [];
    for (let i = minVal; i <= maxVal; i += 1.0) {
      bins.push(i);
    }
    
    const counts = new Array(bins.length).fill(0);

    // Count how many communities fall into each bin
    anomalies.forEach(val => {
      // Find the closest bin (rounding to nearest 1.0)
      const rounded = Math.round(val);
      const idx = bins.indexOf(rounded);
      
      // If the rounded value strictly falls inside our bin array, increment it
      if (idx !== -1) {
        counts[idx]++;
      } else {
        // Edge cases for values exactly on the boundary that round out of bounds
        if (rounded < bins[0]) counts[0]++;
        if (rounded > bins[bins.length - 1]) counts[bins.length - 1]++;
      }
    });

    return bins.map((bin, i) => ({
      name: `${bin > 0 ? '+' : ''}${bin.toFixed(1)}°C`,
      count: counts[i],
      isHot: bin > 0
    }));
  }, [computedCommunities, timeOfDay]);


  if (!computedCommunities) return null;

  return (
    <div className={styles.container}>
      
      {/* CHART 1: Scatter Plot */}
      <div className={styles.chartBlock}>
        <div className={styles.chartHeader}>
          <div className={styles.title}>Population vs. Temperature Anomaly</div>
          <div className={styles.subtitle}>Identifying highly populated communities exposed to extreme heat vs those in cooling zones.</div>
        </div>
        <div style={{ width: '100%', height: 350 }}>
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 10, right: 30, bottom: 20, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
              <XAxis 
                type="number" 
                dataKey="temp" 
                name="Temp Anomaly" 
                unit="°C" 
                stroke="var(--text-secondary)" 
                fontSize={12}
                domain={['dataMin - 0.5', 'dataMax + 0.5']}
              />
              <YAxis 
                type="number" 
                dataKey="population" 
                name="Population" 
                stroke="var(--text-secondary)" 
                fontSize={12}
                tickFormatter={(value) => value > 1000 ? `${(value/1000).toFixed(0)}k` : value}
              />
              <RechartsTooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
              <Scatter name="Communities" data={scatterData} fill="var(--accent-amber)" shape="circle" fillOpacity={0.7} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* CHART 2: Histogram */}
      <div className={styles.chartBlock}>
        <div className={styles.chartHeader}>
          <div className={styles.title}>City-Wide Anomaly Distribution</div>
          <div className={styles.subtitle}>How many communities are hotter vs cooler than the city average right now.</div>
        </div>
        <div style={{ width: '100%', height: 350 }}>
          <ResponsiveContainer>
            <BarChart data={histData} margin={{ top: 10, right: 30, bottom: 20, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--text-secondary)" fontSize={11} interval={1} />
              <YAxis stroke="var(--text-secondary)" fontSize={11} />
              <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
              <Bar dataKey="count" name="Communities" radius={[4, 4, 0, 0]}>
                {histData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.isHot ? 'var(--accent-hot)' : 'var(--accent-cool)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* CHART 3: Stacked Bar */}
      <div className={styles.chartBlock}>
        <div className={styles.chartHeader}>
          <div className={styles.title}>Land Composition: Extremes</div>
          <div className={styles.subtitle}>Comparing the physical makeup of the 5 Hottest vs 5 Coolest communities.</div>
        </div>
        <div style={{ width: '100%', height: 350 }}>
          <ResponsiveContainer>
            <BarChart data={barData} layout="vertical" margin={{ top: 10, right: 30, bottom: 10, left: 30 }} barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" width={100} stroke="var(--text-secondary)" fontSize={10} />
              <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
              <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
              <Bar dataKey="Built" stackId="a" fill="#8884d8" name="Built-up %" />
              <Bar dataKey="Sand" stackId="a" fill="#ffd166" name="Sand %" />
              <Bar dataKey="Water" stackId="a" fill="#118ab2" name="Water %" />
              <Bar dataKey="Greenery" stackId="a" fill="var(--accent-green)" name="Greenery %" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
}
