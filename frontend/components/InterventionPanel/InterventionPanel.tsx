import React, { useState, useEffect } from "react";
import styles from "./InterventionPanel.module.css";
import { useAppContext } from "../../context/AppContext";
import {
  INTERVENTION_TEMPLATES,
  validateFeatures,
  getConflicts,
  FeatureVector,
  InterventionId,
  FEATURE_KEYS,
  FEATURE_RANGES
} from "../../lib/interventions";
import { suggestInterventions, Suggestion } from "../../lib/suggestions";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function InterventionPanel() {
  const {
    selectedPixels,
    pixelInspectorData,
    activeInterventions,
    setActiveInterventions,
    modifiedFeatures,
    setModifiedFeatures,
    predictedAnomalies,
    setPredictedAnomalies,
    expertMode,
    setExpertMode,
    timeOfDay,
    setInterventionMode,
    setSelectedPixels
  } = useAppContext();

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  // To track if backend prediciton is running 
  const [predicting, setPredicting] = useState(false);
  const [buildingSliders, setBuildingSliders] = useState({ density: 0.5, height: 10 });
  
  // Expert mode local state
  const [expertSliders, setExpertSliders] = useState<FeatureVector | null>(null);

  // Initialize expert sliders when toggling expert mode
  useEffect(() => {
    if (expertMode) {
      setExpertSliders(modifiedFeatures || pixelInspectorData?.features || null);
    }
  }, [expertMode, modifiedFeatures, pixelInspectorData]);

  // Fetch suggestions
  useEffect(() => {
    if (pixelInspectorData?.features && selectedPixels.length > 0) {
      setSuggestionsLoading(true);
      
      const allFeaturesBatch = selectedPixels.map(p => p.features);
      const avgCurrentAnomalies = {
        morning: selectedPixels.reduce((sum, p) => sum + p.anomalies.morning, 0) / selectedPixels.length,
        afternoon: selectedPixels.reduce((sum, p) => sum + p.anomalies.afternoon, 0) / selectedPixels.length,
        night: selectedPixels.reduce((sum, p) => sum + p.anomalies.night, 0) / selectedPixels.length,
      };
      
      suggestInterventions(
        allFeaturesBatch,
        avgCurrentAnomalies,
        timeOfDay,
        activeInterventions.map(i => i.templateId)
      ).then(res => {
        setSuggestions(res);
        setSuggestionsLoading(false);
      });
    }
  }, [pixelInspectorData, activeInterventions, timeOfDay, selectedPixels]);

  if (selectedPixels.length === 0 || !pixelInspectorData) {
    return null; // hide if nothing selected
  }

  // Calculate current anamolies before any interventions
  const currentAnomalies = {
    morning: selectedPixels.reduce((sum, p) => sum + p.anomalies.morning, 0) / selectedPixels.length,
    afternoon: selectedPixels.reduce((sum, p) => sum + p.anomalies.afternoon, 0) / selectedPixels.length,
    night: selectedPixels.reduce((sum, p) => sum + p.anomalies.night, 0) / selectedPixels.length,
  };
  
  // Calculate true mathematical average of features across the entire selection for visual composition accurately before any intervention is applied
  const avgOriginalVector: any = {};
  for (const key of FEATURE_KEYS) {
    avgOriginalVector[key] = selectedPixels.reduce((sum, p) => sum + (p.features[key] as number), 0) / selectedPixels.length;
  }
  const originalFeatures = avgOriginalVector as FeatureVector;

  const recalculateAndPredict = async (newActiveList: typeof activeInterventions) => {
    // creates a list of feature vectors for each pixel
    let batchCurrentV = selectedPixels.map(p => ({ ...p.features }));

    for (const active of newActiveList) {
      // pick the intervention template to apply based on the active interventions list item 
      const t = INTERVENTION_TEMPLATES.find(x => x.id === active.templateId);
      if (t) {
         batchCurrentV = batchCurrentV.map(v => t.apply(v, active.params));
      }
    }

    // Validate all pixels to ensure the feature combination is mathematically sound across the board
    let allValid = true;
    const allErrors = new Set<string>();
    
    for (const v of batchCurrentV) {
      const { valid, errors } = validateFeatures(v);
      if (!valid) {
        allValid = false;
        errors.forEach(e => allErrors.add(e));
      }
    }

    if (!allValid) {
      alert("Invalid feature combination detected in selection: \n" + Array.from(allErrors).join("\n"));
      return;
    }

    // Set the averaged modified feature vector strictly for visual Composition UI purposes so each feature name has its mean value 
    const avgModifiedVector: any = {};
    for (const key of FEATURE_KEYS) {
      avgModifiedVector[key] = batchCurrentV.reduce((sum, v) => sum + (v[key] as number), 0) / batchCurrentV.length;
    }
    setModifiedFeatures(avgModifiedVector as FeatureVector);
    setPredicting(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/predict-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pixels: batchCurrentV })
      });
      if (res.ok) {
        const data = await res.json();
        setPredictedAnomalies(data.predicted_anomalies);
        setActiveInterventions(newActiveList);
      } else {
        alert("Prediction failed.");
      }
    } catch (e) {
      alert("Error predicting: " + e);
    } finally {
      setPredicting(false);
    }
  };

  // When user clicks on an intervention apply button
  const handleApply = (templateId: InterventionId, params?: any) => {
    const newList = [...activeInterventions, { templateId, params }];
    recalculateAndPredict(newList);
  };

  const handleRemove = (templateId: InterventionId) => {
    // Choose everythign expect the specified intervention to remove
    const newList = activeInterventions.filter(i => i.templateId !== templateId);
    if (newList.length === 0) {
      // Clear out
      setActiveInterventions([]);
      setModifiedFeatures(null);
      setPredictedAnomalies(null);
    } else {
      recalculateAndPredict(newList);
    }
  };

  const activeIds = activeInterventions.map(i => i.templateId);

  // Composition Rendering (Based on true mathematical average of the active selection area)
  const activeFeaturesVector = modifiedFeatures || originalFeatures;
  const cSand = activeFeaturesVector.sand_mask_fraction * 100;
  const cWater = activeFeaturesVector.water_mask_full_fraction * 100;
  const cBldg = activeFeaturesVector.building_density_mean * 100;
  const cRoad = activeFeaturesVector.road_density_mean * 100;
  const cVeg = Math.max(0, activeFeaturesVector.ndvi_mean * 100); // Approximation
  
  // Normalize to 100% just for visual scale
  const totalRaw = cSand + cWater + cBldg + cRoad + cVeg || 1; 
  const pSand = (cSand / totalRaw) * 100;
  const pWater = (cWater / totalRaw) * 100;
  const pBldg = (cBldg / totalRaw) * 100;
  const pRoad = (cRoad / totalRaw) * 100;
  const pVeg = (cVeg / totalRaw) * 100;

  const handleExpertPredict = async () => {
    if (!expertSliders) return;
    const { valid, errors } = validateFeatures(expertSliders);
    if (!valid) {
      alert("Invalid feature combination: \n" + errors.join("\n"));
      return;
    }
    setModifiedFeatures(expertSliders);
    setPredicting(true);
    
    // Clone expert settings onto all pixels for batch operation
    const batchExpertV = selectedPixels.map(() => expertSliders);
    
    try {
      const res = await fetch(`${API_BASE_URL}/api/predict-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pixels: batchExpertV })
      });
      if (res.ok) {
        const data = await res.json();
        setPredictedAnomalies(data.predicted_anomalies);
        // Clear normal active interventions since we are manually overriding now
        setActiveInterventions([]);
      }
    } catch (e) {
      alert("Error predicting user inputs");
    } finally {
      setPredicting(false);
    }
  };

  const formatDelta = (delta: number) => {
    const sign = delta > 0 ? "+" : "";
    return `${sign}${delta.toFixed(2)}°C`;
  };

  return (
    <div className={styles.panelContainer}>
      <div className={styles.header}>
        <div className={styles.titleInfo}>
          <div className={styles.title}>Intervention Panel ({selectedPixels.length} pixels)</div>
        </div>
        <button className={styles.closeButton} onClick={() => {
          setSelectedPixels([]); // This cleans up Phase 4 state through MapView listener
          setInterventionMode(false);
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>

      {!expertMode && (
        <>
          {/* Smart Suggestions */}
          <div className={styles.section}>
            <div className={styles.sectionTitle}>⚡ Smart Suggestions</div>
            {suggestionsLoading ? (
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Analyzing cooling potential...</div>
            ) : suggestions.length === 0 ? (
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>No fresh suggestions right now.</div>
            ) : (
              <div className={styles.suggestionsList}>
                {suggestions.map((s, i) => (
                  <div key={i} className={styles.card}>
                    <div className={styles.cardHeader}>
                      <span className={styles.cardTitle}>{s.icon} {s.name}</span>
                      <span className={`${styles.deltaBadge} ${s.deltaT < 0 ? styles.cooling : styles.warming}`}>
                        {formatDelta(s.deltaT)}
                      </span>
                    </div>
                    <button className={styles.applyButton} onClick={() => handleApply(s.templateId, s.params)} disabled={predicting}>
                      {predicting ? "Applying..." : "Quick Apply"}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Current Composition */}
          <div className={styles.section}>
            <div className={styles.sectionTitle}>📊 Pixel Composition</div>
            <div className={styles.compositionBar}>
              {pSand > 0 && <div className={styles.compSegment} style={{ width: `${pSand}%`, backgroundColor: '#e6c229' }} data-tooltip={`Sand: ${cSand.toFixed(1)}%`} />}
              {pWater > 0 && <div className={styles.compSegment} style={{ width: `${pWater}%`, backgroundColor: '#1E90FF' }} data-tooltip={`Water: ${cWater.toFixed(1)}%`} />}
              {pBldg > 0 && <div className={styles.compSegment} style={{ width: `${pBldg}%`, backgroundColor: '#9e9e9e' }} data-tooltip={`Building: ${cBldg.toFixed(1)}%`} />}
              {pRoad > 0 && <div className={styles.compSegment} style={{ width: `${pRoad}%`, backgroundColor: '#5c5c5c' }} data-tooltip={`Road: ${cRoad.toFixed(1)}%`} />}
              {pVeg > 0 && <div className={styles.compSegment} style={{ width: `${pVeg}%`, backgroundColor: '#4CAF50' }} data-tooltip={`Vegetation: ~${cVeg.toFixed(1)}%`} />}
            </div>
            <div className={styles.compLabels}>
              <span className={styles.compLabel}><div className={styles.compDot} style={{ background: '#e6c229' }}/> Sand</span>
              <span className={styles.compLabel}><div className={styles.compDot} style={{ background: '#1E90FF' }}/> Water</span>
              <span className={styles.compLabel}><div className={styles.compDot} style={{ background: '#9e9e9e' }}/> Bldg</span>
              <span className={styles.compLabel}><div className={styles.compDot} style={{ background: '#5c5c5c' }}/> Road</span>
              <span className={styles.compLabel}><div className={styles.compDot} style={{ background: '#4CAF50' }}/> Veg</span>
            </div>
            <div className={styles.chipRow}>
              <div className={styles.chip}>Albedo: {activeFeaturesVector.albedo_mean.toFixed(2)}</div>
              <div className={styles.chip}>Height: {Math.round(activeFeaturesVector.height_mean)}m</div>
              <div className={styles.chip}>Dist2Coast: {Math.round(activeFeaturesVector.dist_to_coast_m)}m</div>
            </div>
          </div>

          {/* All Interventions */}
          <div className={styles.section}>
            <div className={styles.sectionTitle}>🔧 Interventions</div>
            <div className={styles.interventionsGrid}>
              {INTERVENTION_TEMPLATES.map(template => {
                const isActive = activeIds.includes(template.id);
                
                // For the UI grid buttons, we ensure the template is valid for EVERY pixel in the selection array
                const canApply = selectedPixels.every(p => template.canApply(p.features));
                const conflicts = getConflicts(activeIds, template.id);
                const isConflict = conflicts.length > 0;
                
                let disableReason = "";
                if (!canApply) disableReason = "Current selection contains pixels incompatible with this intervention.";
                if (isConflict) disableReason = `Conflicts with: ${conflicts.join(", ")}`;

                const numActive = activeIds.length;
                const isConstructActive = template.id === "construct_building" && !isActive && !isConflict && canApply;

                return (
                  <div key={template.id} className={`${styles.card} ${isActive ? styles.active : ''} ${(!canApply || isConflict) && !isActive ? styles.disabled : ''}`} title={disableReason}>
                    <div className={styles.cardHeader}>
                      <span className={styles.cardTitle}>{template.icon} {template.name}</span>
                      {isActive && <span style={{color: '#4CAF50', fontSize: '14px'}}>✓</span>}
                    </div>
                    <div className={styles.cardDescription}>{template.description}</div>
                    
                    {isConstructActive && (
                      <div className={styles.constructSliders}>
                         <div className={styles.sliderRow}>
                           <div className={styles.sliderLabelRow}><span>Density: {buildingSliders.density.toFixed(2)}</span></div>
                           <input type="range" className={styles.sliderInput} min="0.10" max="0.85" step="0.05" value={buildingSliders.density} onChange={e => setBuildingSliders(prev => ({...prev, density: parseFloat(e.target.value)}))} />
                         </div>
                         <div className={styles.sliderRow}>
                           <div className={styles.sliderLabelRow}><span>Height: {buildingSliders.height}m</span></div>
                           <input type="range" className={styles.sliderInput} min="3" max="103" step="1" value={buildingSliders.height} onChange={e => setBuildingSliders(prev => ({...prev, height: parseInt(e.target.value)}))} />
                         </div>
                      </div>
                    )}

                    {!isActive ? (
                      <button className={styles.applyButton} onClick={() => handleApply(template.id, template.id === "construct_building" ? buildingSliders : undefined)} disabled={predicting}>
                        Apply
                      </button>
                    ) : (
                      <button className={`${styles.applyButton} ${styles.remove}`} onClick={() => handleRemove(template.id)} disabled={predicting}>
                        Remove
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </>

      )}

      {/* Before / After Results */}
      {predictedAnomalies && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>📈 Simulation Results</div>
          <div className={styles.resultsRow}>
            {(['morning', 'afternoon', 'night'] as const).map(time => {
              const before = currentAnomalies[time];
              const after = predictedAnomalies[time];
              const delta = after - before;
              const isCurrentTime = time === timeOfDay;
              return (
                <div key={time} className={`${styles.resultChip} ${isCurrentTime ? styles.active : ''}`}>
                  <div className={styles.resultTimes}>
                    <span className={styles.resultTimeName}>{time}</span>
                    <span className={styles.resultTemps}>
                       {signFormat(before)}° <span className={styles.arrow}>→</span> {signFormat(after)}°
                    </span>
                  </div>
                  <div className={`${styles.deltaBadge} ${delta < 0 ? styles.cooling : styles.warming} ${isCurrentTime ? styles.activeBadge : ''}`}>
                    {delta > 0 ? '🔺' : '💧'} {formatDelta(delta)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Expert Mode */}
      <div className={styles.expertToggle}>
        <span className={styles.expertToggleLabel}>🔬 Expert Mode</span>
        <label className={styles.switch}>
          <input type="checkbox" checked={expertMode} onChange={e => setExpertMode(e.target.checked)} />
          <span className={styles.slider}></span>
        </label>
      </div>

      {expertMode && expertSliders && (
        <div className={styles.expertSliders}>
           {FEATURE_KEYS.map(key => {
             const immutable = key === "dist_to_coast_m";
             const range = FEATURE_RANGES[key];
             if (!range) return null;
             const isMask = key.includes("mask");
             
             return (
               <div key={key} className={styles.sliderRow}>
                 <div className={styles.sliderLabelRow}>
                   <span>{key.replace("_mean", "").replace("_fraction", "")}</span>
                   <span>{expertSliders[key].toFixed(2)} {immutable && "(Fixed)"}</span>
                 </div>
                 {isMask ? (
                   <div style={{display: 'flex', gap: '8px'}}>
                     <label style={{fontSize: '12px'}}><input type="radio" name={key} checked={expertSliders[key]===0} onChange={() => setExpertSliders(p => p ? {...p, [key]: 0} : p)} /> 0</label>
                     <label style={{fontSize: '12px'}}><input type="radio" name={key} checked={expertSliders[key]===1} onChange={() => setExpertSliders(p => p ? {...p, [key]: 1} : p)} /> 1</label>
                   </div>
                 ) : (
                   <input 
                     type="range" 
                     className={styles.sliderInput} 
                     disabled={immutable || predicting}
                     min={range[0]} 
                     max={range[1]} 
                     step={key === "height_mean" ? 1 : 0.01}
                     value={expertSliders[key]}
                     onChange={e => setExpertSliders(prev => prev ? {...prev, [key]: parseFloat(e.target.value)} : prev)}
                   />
                 )}
               </div>
             )
           })}
           <div className={styles.expertActions}>
             <button className={styles.expertBtn} onClick={() => {
                setExpertSliders({...originalFeatures});
                setModifiedFeatures(null);
                setPredictedAnomalies(null);
                setActiveInterventions([]);
             }}>Reset</button>
             <button className={`${styles.expertBtn} ${styles.primary}`} onClick={handleExpertPredict} disabled={predicting}>
               {predicting ? "Predicting..." : "Predict Delta"}
             </button>
           </div>
        </div>
      )}
    </div>
  );
}

function signFormat(num: number) {
  return (num > 0 ? "+" : "") + num.toFixed(2);
}
