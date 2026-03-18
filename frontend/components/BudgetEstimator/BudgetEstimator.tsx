import React, { useState } from "react";
import styles from "./BudgetEstimator.module.css";
import { useAppContext } from "../../context/AppContext";
import { INTERVENTION_TEMPLATES, InterventionId } from "../../lib/interventions";

export default function BudgetEstimator() {
  const { selectedPixels, activeInterventions, predictedAnomalies, timeOfDay } = useAppContext();

  // Local state for cost overrides
  const [costs, setCosts] = useState<Record<InterventionId, number>>(() => {
    // Using record for specific key value types
    const initialCosts: Partial<Record<InterventionId, number>> = {};
    INTERVENTION_TEMPLATES.forEach(t => {
      initialCosts[t.id] = t.defaultCostPerSqM;
    });
    // Dictionary-like object to store the costs of each intervention
    return initialCosts as Record<InterventionId, number>;
  });

  if (activeInterventions.length === 0 || selectedPixels.length === 0) {
    return null;
  }

  const AREA_PER_PIXEL = 900; // 30x30m
  const totalArea = selectedPixels.length * AREA_PER_PIXEL;

  // Calculate total cost
  let totalCost = 0;
  // For each intervention, goes througha ll the selected pixels and calulates the area affected and the total cost for that intervention
  // Returns a list of [{template: InterventionTemplate, costPerSqM: number, itemTotal: number}] by goin through each intervention's details
  const costBreakdown = activeInterventions.map(active => {
    // Assert template will always be found using '!'
    const template = INTERVENTION_TEMPLATES.find(t => t.id === active.templateId)!;
    
    const costPerSqM = costs[active.templateId] || 0;
    
    // Calculate the actual area affected by this intervention
    // Only count pixels where the intervention can actually be applied
    let actualAreaAffected = 0;
    
    selectedPixels.forEach(pixel => {
      // Skip pixels where this intervention doesn't apply
      if (!template.canApply(pixel.features)) return;
      
      let fraction = 1.0; // By default (e.g., Park, Water Feature, Construct Building), it affects the whole 900m2
      
      if (template.id === "cool_roof" || template.id === "green_roof") {
        fraction = pixel.features.building_density_mean;
      } else if (template.id === "cool_road") {
        fraction = pixel.features.road_density_mean;
      }
      
      actualAreaAffected += (AREA_PER_PIXEL * fraction);
    });

    const itemTotal = actualAreaAffected * costPerSqM;
    totalCost += itemTotal;

    return {
      template,
      costPerSqM,
      itemTotal,
      actualAreaAffected
    };
  });

  // Calculate cost effectiveness (AED per degree of cooling)
  let costEffectiveness: number | null = null;
  if (predictedAnomalies) {
    const avgCurrentAnomalies = {
      morning: selectedPixels.reduce((sum, p) => sum + p.anomalies.morning, 0) / selectedPixels.length,
      afternoon: selectedPixels.reduce((sum, p) => sum + p.anomalies.afternoon, 0) / selectedPixels.length,
      night: selectedPixels.reduce((sum, p) => sum + p.anomalies.night, 0) / selectedPixels.length,
    };
    const before = avgCurrentAnomalies[timeOfDay];
    const after = predictedAnomalies[timeOfDay];
    const deltaT = after - before;

    // If the intervention is effective (deltaT < 0) and the total cost is positive, calculate the cost effectiveness
    if (deltaT < 0 && totalCost > 0) {
      costEffectiveness = totalCost / Math.abs(deltaT);
    }
  }

  // Handling case where user inputs cost - change the cost in the costs state above
  const handleCostChange = (id: InterventionId, value: string) => {
    const num = parseFloat(value);
    if (!isNaN(num) && num >= 0) {
      setCosts(prev => ({ ...prev, [id]: num }));
    }
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-AE', { style: 'currency', currency: 'AED', maximumFractionDigits: 0 }).format(val);
  };

  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>💰 Budget Estimator</div>
      
      <div className={styles.summaryGrid}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Affected Area</span>
          <span className={styles.summaryValue}>{totalArea.toLocaleString()} m²</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>Total Est. Cost</span>
          <span className={styles.summaryValueHighlight}>{formatCurrency(totalCost)}</span>
        </div>
        {costEffectiveness !== null && (
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Cost-Effectiveness</span>
            <span className={styles.summaryValue}>{formatCurrency(costEffectiveness)} / °C</span>
          </div>
        )}
      </div>

      <div className={styles.breakdownList}>
        <div className={styles.breakdownHeader}>Cost Breakdown & Adjustments</div>
        {costBreakdown.map(item => (
          <div key={item.template.id} className={styles.breakdownRow}>
            <div className={styles.breakdownInfo}>
              <span className={styles.breakdownName}>
                {item.template.icon} {item.template.name}
              </span>
              <span className={styles.breakdownTotal}>
                {item.actualAreaAffected.toLocaleString(undefined, { maximumFractionDigits: 0 })} m² at {formatCurrency(item.itemTotal)}
              </span>
            </div>
            <div className={styles.costInputGroup}>
              <input 
                type="number" 
                className={styles.costInput}
                value={costs[item.template.id]}
                onChange={e => handleCostChange(item.template.id, e.target.value)}
                min="0"
              />
              <span className={styles.costUnit}>AED/m²</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
