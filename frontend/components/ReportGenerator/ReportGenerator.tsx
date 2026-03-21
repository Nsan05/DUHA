import React from "react";
import styles from "./ReportGenerator.module.css";
import { useAppContext } from "../../context/AppContext";
import { INTERVENTION_TEMPLATES, InterventionId } from "../../lib/interventions";

const AREA_PER_PIXEL = 900;

export default function ReportGenerator() {
  const {
    selectedPixels,
    activeInterventions,
    predictedAnomalies,
    perPixelAnomalies,
    timeOfDay,
    selectedCommunity,
    computedCommunities,
  } = useAppContext();

  // Only show when predictions are active
  if (!predictedAnomalies || activeInterventions.length === 0 || selectedPixels.length === 0) {
    return null;
  }

  // Resolve selected community property and name
  const communityFeature = computedCommunities?.features?.find(
    (f: any) => f.properties.COMM_NUM.toString() === selectedCommunity
  );
  const communityName = communityFeature?.properties?.CNAME_E || `Community ${selectedCommunity}`;

  // Current anomalies (before)
  const currentAnomalies = {
    morning: selectedPixels.reduce((sum, p) => sum + p.anomalies.morning, 0) / selectedPixels.length,
    afternoon: selectedPixels.reduce((sum, p) => sum + p.anomalies.afternoon, 0) / selectedPixels.length,
    night: selectedPixels.reduce((sum, p) => sum + p.anomalies.night, 0) / selectedPixels.length,
  };

  // Budget calculations (Same as BudgetEstimator logic)
  const totalArea = selectedPixels.length * AREA_PER_PIXEL;
  let totalCost = 0;
  // For each intervention, goes througha ll the selected pixels and calulates the area affected and the total cost for that intervention
  const costBreakdown = activeInterventions.map(active => {
    const template = INTERVENTION_TEMPLATES.find(t => t.id === active.templateId)!;
    const costPerSqM = template.defaultCostPerSqM;
    let actualArea = 0;
    selectedPixels.forEach(pixel => {
      if (!template.canApply(pixel.features)) return;
      let fraction = 1.0;
      if (template.id === "cool_roof" || template.id === "green_roof") {
        fraction = pixel.features.building_density_mean;
      } else if (template.id === "cool_road") {
        fraction = pixel.features.road_density_mean;
      }
      actualArea += AREA_PER_PIXEL * fraction;
    });
    const itemTotal = actualArea * costPerSqM;
    totalCost += itemTotal;
    return { template, costPerSqM, itemTotal, actualArea };
  });

  // Cost effectiveness
  const deltaT = predictedAnomalies[timeOfDay] - currentAnomalies[timeOfDay];
  const roundedDeltaT = parseFloat(deltaT.toFixed(2));
  const costEffectiveness = deltaT < 0 && roundedDeltaT !== 0 && totalCost > 0 ? totalCost / Math.abs(roundedDeltaT) : null;

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat("en-AE", { style: "currency", currency: "AED", maximumFractionDigits: 0 }).format(val);

  const signFormat = (num: number) => (num > 0 ? "+" : "") + num.toFixed(2);

  // Handdling export report
  const handleExport = () => {
    const now = new Date();
    const dateStr = now.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    const timeStr = now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });

    // Per-pixel table rows
    const perPixelRows = selectedPixels.map((pixel, i) => {
      const original = pixel.anomaly;
      const predicted = perPixelAnomalies ? perPixelAnomalies[i] : null;
      const delta = predicted !== null ? predicted - original : null;
      return `
        <tr>
          <td>${i + 1}</td>
          <td>${pixel.lat.toFixed(5)}</td>
          <td>${pixel.lng.toFixed(5)}</td>
          <td>${signFormat(original)}°C</td>
          <td>${predicted !== null ? signFormat(predicted) + "°C" : "—"}</td>
          <td class="${delta !== null && delta < 0 ? "cool" : "warm"}">${delta !== null ? signFormat(delta) + "°C" : "—"}</td>
        </tr>`;
    }).join("");

    // Interventions list
    const interventionRows = costBreakdown.map(item => `
      <tr>
        <td>${item.template.icon} ${item.template.name}</td>
        <td>${item.template.description}</td>
        <td>${item.actualArea.toLocaleString(undefined, { maximumFractionDigits: 0 })} m²</td>
        <td>${formatCurrency(item.costPerSqM)}/m²</td>
        <td>${formatCurrency(item.itemTotal)}</td>
      </tr>
    `).join("");

    // Time-of-day rows
    const timeRows = (["morning", "afternoon", "night"] as const).map(time => {
      const before = currentAnomalies[time];
      const after = predictedAnomalies[time];
      const d = after - before;
      const isActive = time === timeOfDay;
      return `
        <tr class="${isActive ? "active-row" : ""}">
          <td>${time.charAt(0).toUpperCase() + time.slice(1)}</td>
          <td>${signFormat(before)}°C</td>
          <td>${signFormat(after)}°C</td>
          <td class="${d < 0 ? "cool" : "warm"}">${signFormat(d)}°C</td>
        </tr>`;
    }).join("");

    // Recommendations
    const avgDelta = deltaT;

    const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Urban Heat Intervention Report - ${communityName}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: #f4f4f6;
      color: #2d2d2d;
      -webkit-font-smoothing: antialiased;
      font-size: 13px;
      line-height: 1.6;
    }
    @media print {
      * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
      body { background: white; }
      .page { box-shadow: none; margin: 0; max-width: 100%; }
      .no-print { display: none !important; }
    }

    .page {
      max-width: 820px;
      margin: 32px auto;
      background: white;
      box-shadow: 0 1px 12px rgba(0,0,0,0.08);
    }

    /* ── Header ── */
    .header {
      padding: 48px 56px 40px;
      border-bottom: 3px solid #1a3a5c;
    }
    .header-org {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 2px;
      color: #1a3a5c;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .header-title {
      font-family: 'Merriweather', Georgia, serif;
      font-size: 26px;
      font-weight: 700;
      color: #1a1a1a;
      line-height: 1.3;
      margin-bottom: 4px;
    }
    .header-subtitle {
      font-size: 15px;
      color: #5a5a6a;
      font-weight: 400;
      margin-bottom: 24px;
    }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
      border: 1px solid #d8d8dc;
      border-radius: 4px;
      overflow: hidden;
    }
    .meta-cell {
      padding: 12px 16px;
      border-right: 1px solid #d8d8dc;
    }
    .meta-cell:last-child { border-right: none; }
    .meta-label {
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #888;
      font-weight: 600;
      margin-bottom: 2px;
    }
    .meta-val {
      font-size: 13px;
      font-weight: 600;
      color: #1a1a1a;
    }

    /* ── Content ── */
    .content { padding: 36px 56px 48px; }

    .section { margin-bottom: 36px; }
    .section-num {
      font-size: 11px;
      font-weight: 700;
      color: #1a3a5c;
      margin-bottom: 4px;
    }
    .section-heading {
      font-family: 'Merriweather', Georgia, serif;
      font-size: 16px;
      font-weight: 700;
      color: #1a1a1a;
      margin-bottom: 14px;
      padding-bottom: 8px;
      border-bottom: 1px solid #e4e4e8;
    }

    /* ── KPI Strip ── */
    .kpi-strip {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 0;
      border: 1px solid #d8d8dc;
      border-radius: 4px;
      margin-bottom: 36px;
      overflow: hidden;
    }
    .kpi-cell {
      padding: 18px 16px;
      text-align: center;
      border-right: 1px solid #d8d8dc;
      background: #fafafa;
    }
    .kpi-cell:last-child { border-right: none; }
    .kpi-label {
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #888;
      font-weight: 600;
      margin-bottom: 6px;
    }
    .kpi-value {
      font-size: 20px;
      font-weight: 700;
      color: #1a1a1a;
    }
    .kpi-unit {
      font-size: 11px;
      color: #888;
      font-weight: 400;
    }
    .val-cool { color: #0d7c4a; }
    .val-warm { color: #c53030; }

    /* ── Tables ── */
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12.5px;
      margin-top: 8px;
    }
    table th {
      text-align: left;
      padding: 9px 12px;
      background: #f0f0f3;
      color: #555;
      font-weight: 600;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.4px;
      border: 1px solid #d8d8dc;
    }
    table td {
      padding: 9px 12px;
      border: 1px solid #e4e4e8;
      color: #2d2d2d;
    }
    .active-row { background: #f6f9fc; }
    .active-row td:first-child { font-weight: 600; }
    .cool { color: #0d7c4a; font-weight: 600; }
    .warm { color: #c53030; font-weight: 600; }
    .total-row td {
      font-weight: 700;
      border-top: 2px solid #1a3a5c;
      background: #f8f8fa;
    }

    /* ── Summary Box ── */
    .summary-box {
      background: #f6f9fc;
      border: 1px solid #d0dce8;
      border-left: 4px solid #1a3a5c;
      border-radius: 3px;
      padding: 18px 22px;
      margin-top: 12px;
      line-height: 1.7;
    }
    .summary-box p { margin-bottom: 10px; }
    .summary-box p:last-child { margin-bottom: 0; }
    .summary-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: #1a3a5c;
      font-weight: 700;
      margin-bottom: 6px;
    }

    /* ── Footer ── */
    .footer {
      padding: 20px 56px;
      border-top: 1px solid #e4e4e8;
      display: flex;
      justify-content: space-between;
      font-size: 10px;
      color: #999;
    }

    .print-btn {
      position: fixed;
      bottom: 28px;
      right: 28px;
      background: #1a3a5c;
      color: white;
      border: none;
      padding: 12px 24px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      font-family: inherit;
    }
    .print-btn:hover { background: #15304d; }
  </style>
</head>
<body>
  <div class="page">

    <div class="header">
      <div class="header-org">Dubai Urban Heat Island Analysis</div>
      <div class="header-title">Intervention Impact Assessment: ${communityName}</div>
      <div class="header-subtitle">Thermal Mitigation Feasibility & Cost Analysis</div>
      <div class="meta-grid">
        <div class="meta-cell">
          <div class="meta-label">Date of Analysis</div>
          <div class="meta-val">${dateStr}</div>
        </div>
        <div class="meta-cell">
          <div class="meta-label">Assessment Period</div>
          <div class="meta-val">${timeOfDay.charAt(0).toUpperCase() + timeOfDay.slice(1)}</div>
        </div>
        <div class="meta-cell">
          <div class="meta-label">Study Area</div>
          <div class="meta-val">${selectedPixels.length} cells (${totalArea.toLocaleString()} m²)</div>
        </div>
        <div class="meta-cell">
          <div class="meta-label">Interventions Modelled</div>
          <div class="meta-val">${activeInterventions.length}</div>
        </div>
      </div>
    </div>

    <div class="content">

      <!-- Key Metrics -->
      <div class="kpi-strip">
        <div class="kpi-cell">
          <div class="kpi-label">Mean ΔT (${timeOfDay})</div>
          <div class="kpi-value ${avgDelta < 0 ? 'val-cool' : 'val-warm'}">${signFormat(avgDelta)}°C</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Total Study Area</div>
          <div class="kpi-value">${totalArea.toLocaleString()}<span class="kpi-unit"> m²</span></div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Estimated Project Cost</div>
          <div class="kpi-value">${formatCurrency(totalCost)}</div>
        </div>
        <div class="kpi-cell">
          <div class="kpi-label">Cost per °C Reduction</div>
          <div class="kpi-value">${costEffectiveness ? formatCurrency(costEffectiveness) : "N/A"}</div>
        </div>
      </div>

      <!-- 1. Temperature Analysis -->
      <div class="section">
        <div class="section-num">Section 1</div>
        <div class="section-heading">Temperature Anomaly Comparison</div>
        <table>
          <thead>
            <tr>
              <th>Period</th>
              <th>Baseline Anomaly (°C)</th>
              <th>Post-Intervention (°C)</th>
              <th>Change (ΔT)</th>
            </tr>
          </thead>
          <tbody>
            ${timeRows}
          </tbody>
        </table>
      </div>

      <!-- 2. Per-Cell Breakdown -->
      <div class="section">
        <div class="section-num">Section 2</div>
        <div class="section-heading">Per-Cell Analysis (${timeOfDay.charAt(0).toUpperCase() + timeOfDay.slice(1)})</div>
        <table>
          <thead>
            <tr>
              <th>Cell</th>
              <th>Latitude</th>
              <th>Longitude</th>
              <th>Baseline (°C)</th>
              <th>Modelled (°C)</th>
              <th>ΔT</th>
            </tr>
          </thead>
          <tbody>
            ${perPixelRows}
          </tbody>
        </table>
      </div>

      <!-- 3. Interventions & Budget -->
      <div class="section">
        <div class="section-num">Section 3</div>
        <div class="section-heading">Applied Interventions & Cost Breakdown</div>
        <table>
          <thead>
            <tr>
              <th>Intervention</th>
              <th>Description</th>
              <th>Coverage Area</th>
              <th>Unit Rate</th>
              <th>Estimated Cost</th>
            </tr>
          </thead>
          <tbody>
            ${interventionRows}
            <tr class="total-row">
              <td colspan="4" style="text-align:right;">Total Estimated Project Cost</td>
              <td>${formatCurrency(totalCost)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 4. Summary & Findings -->
      <div class="section">
        <div class="section-num">Section 4</div>
        <div class="section-heading">Summary & Findings</div>
        <div class="summary-box">
          <div class="summary-label">Thermal Impact</div>
          <p>
            The modelling of ${activeInterventions.length} intervention${activeInterventions.length > 1 ? "s" : ""} 
            across ${selectedPixels.length} grid cell${selectedPixels.length > 1 ? "s" : ""} 
            in <strong>${communityName}</strong> indicates a projected mean temperature anomaly shift of 
            <strong>${signFormat(avgDelta)}°C</strong> during the <strong>${timeOfDay}</strong> period.
          </p>
        </div>
        ${avgDelta < 0 ? `
        <div class="summary-box" style="margin-top: 14px;">
          <div class="summary-label">Financial Assessment</div>
          <p>
            The total estimated implementation cost is <strong>${formatCurrency(totalCost)}</strong>, 
            covering an effective area of <strong>${totalArea.toLocaleString()} m²</strong>.
            ${costEffectiveness ? `The cost-effectiveness ratio is <strong>${formatCurrency(costEffectiveness)} per °C</strong> of cooling achieved. This ${costEffectiveness < 500000 ? "falls within a competitive range" : costEffectiveness < 2000000 ? "represents a moderate investment" : "constitutes a significant capital expenditure"} for urban thermal mitigation in comparable contexts.` : ""}
          </p>
        </div>
        ` : ""}
      </div>

    </div>

    <div class="footer">
      <span>Dubai Urban Heat Island Analysis Platform — Confidential</span>
      <span>Report generated ${dateStr} at ${timeStr}</span>
    </div>

  </div>

  <button class="print-btn no-print" onclick="window.print()">Save as PDF</button>
</body>
</html>`;

    const w = window.open("", "_blank");
    if (w) {
      w.document.write(html);
      w.document.close();
    }
  };

  return (
    <button className={styles.exportButton} onClick={handleExport}>
      📄 Export Report
    </button>
  );
}
