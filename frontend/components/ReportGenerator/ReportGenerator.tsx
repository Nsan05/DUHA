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
  const costEffectiveness = deltaT < 0 && totalCost > 0 ? totalCost / Math.abs(deltaT) : null;

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
  <title>Urban Heat Intervention Report — ${communityName}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0F0F0F;
      color: #E8E8ED;
      -webkit-font-smoothing: antialiased;
      padding: 0;
    }
    @media print {
      * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; color-adjust: exact !important; }
      body { background: #0F0F0F !important; color: #E8E8ED !important; }
      .page { box-shadow: none !important; border: none !important; margin: 0 !important; max-width: 100% !important; background: #1C1C1E !important; border-radius: 0 !important; }
      .header-bar { background: #151530 !important; }
      .header-badge { background: #2a2a3a !important; color: #ccccdd !important; }
      .header-title { color: white !important; }
      .header-sub { color: #9999aa !important; }
      .meta-label { color: #77778a !important; }
      .meta-value { color: #e0e0ea !important; }
      .content { background: #1C1C1E !important; }
      .section { background: #252528 !important; border: 1px solid #333338 !important; }
      .section-title { color: #8888a0 !important; }
      .section-title::before { background: #63b3ed !important; }
      .kpi-card { background: #252528 !important; border: 1px solid #333338 !important; }
      .kpi-label { color: #77778a !important; }
      .kpi-value { color: #E8E8ED !important; }
      .kpi-unit { color: #666680 !important; }
      table th { background: #2a2a30 !important; color: #9999a8 !important; border-bottom: 1px solid #333338 !important; }
      table td { color: #d8d8e0 !important; border-bottom: 1px solid #2a2a30 !important; }
      .active-row { background: #1a2a3a !important; }
      .cool { color: #34d399 !important; }
      .warm { color: #f87171 !important; }
      .rec-box { background: #1a2e24 !important; border: 1px solid #2d5a3e !important; }
      .rec-title { color: #34d399 !important; }
      .rec-text { color: #b8b8c8 !important; }
      .rec-text strong { color: #e0e0ea !important; }
      .footer { background: #1a1a1d !important; border-top: 1px solid #333338 !important; color: #5a5a70 !important; }
      .no-print { display: none !important; }
    }
    .page {
      max-width: 900px;
      margin: 40px auto;
      background: #1C1C1E;
      border-radius: 20px;
      overflow: hidden;
      box-shadow: 0 24px 80px rgba(0,0,0,0.6);
    }
    .header-bar {
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
      padding: 48px 56px;
      position: relative;
      overflow: hidden;
    }
    .header-bar::after {
      content: '';
      position: absolute;
      top: -50%;
      right: -10%;
      width: 300px;
      height: 300px;
      background: radial-gradient(circle, rgba(99, 179, 237, 0.15) 0%, transparent 70%);
      border-radius: 50%;
    }
    .header-badge {
      display: inline-block;
      background: rgba(255,255,255,0.12);
      color: rgba(255,255,255,0.8);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 1.2px;
      padding: 6px 14px;
      border-radius: 20px;
      margin-bottom: 16px;
      backdrop-filter: blur(10px);
    }
    .header-title {
      font-size: 32px;
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 6px;
      color: white;
    }
    .header-sub {
      font-size: 14px;
      color: rgba(255,255,255,0.6);
      font-weight: 400;
    }
    .meta-row {
      display: flex;
      gap: 32px;
      margin-top: 24px;
      flex-wrap: wrap;
    }
    .meta-item {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .meta-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: rgba(255,255,255,0.45);
      font-weight: 600;
    }
    .meta-value {
      font-size: 15px;
      font-weight: 500;
      color: rgba(255,255,255,0.9);
    }

    .content { padding: 40px 56px; }

    .section {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 28px 32px;
      margin-bottom: 28px;
    }
    .section-title {
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: rgba(255,255,255,0.5);
      font-weight: 600;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .section-title::before {
      content: '';
      width: 3px;
      height: 14px;
      background: #63b3ed;
      border-radius: 2px;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }
    .kpi-card {
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      padding: 20px;
      text-align: center;
    }
    .kpi-label {
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: rgba(255,255,255,0.45);
      font-weight: 600;
      margin-bottom: 8px;
    }
    .kpi-value {
      font-size: 22px;
      font-weight: 700;
      color: #E8E8ED;
    }
    .kpi-unit {
      font-size: 12px;
      color: rgba(255,255,255,0.4);
      font-weight: 400;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    table th {
      text-align: left;
      padding: 10px 14px;
      background: rgba(255,255,255,0.06);
      color: rgba(255,255,255,0.6);
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    table td {
      padding: 10px 14px;
      border-bottom: 1px solid rgba(255,255,255,0.05);
      color: rgba(255,255,255,0.85);
    }
    table tr:last-child td { border-bottom: none; }
    .active-row { background: rgba(99, 179, 237, 0.08); }
    .active-row td:first-child { font-weight: 600; }
    .cool { color: #34d399; font-weight: 600; }
    .warm { color: #f87171; font-weight: 600; }

    .rec-box {
      background: rgba(52, 211, 153, 0.08);
      border: 1px solid rgba(52, 211, 153, 0.2);
      border-radius: 12px;
      padding: 20px 24px;
      margin-top: 12px;
    }
    .rec-title {
      font-size: 14px;
      font-weight: 600;
      color: #34d399;
      margin-bottom: 8px;
    }
    .rec-text {
      font-size: 13px;
      color: rgba(255,255,255,0.7);
      line-height: 1.6;
    }

    .footer {
      background: rgba(255,255,255,0.03);
      padding: 24px 56px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid rgba(255,255,255,0.06);
      font-size: 11px;
      color: rgba(255,255,255,0.35);
    }

    .print-btn {
      position: fixed;
      bottom: 32px;
      right: 32px;
      background: #63b3ed;
      color: #0F0F0F;
      border: none;
      padding: 14px 28px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 8px 24px rgba(99, 179, 237, 0.3);
      transition: transform 0.2s;
      font-family: inherit;
    }
    .print-btn:hover { transform: translateY(-2px); }
  </style>
</head>
<body>
  <div class="page">
    <div class="header-bar">
      <div class="header-badge">Intervention Report</div>
      <div class="header-title">${communityName}</div>
      <div class="header-sub">Urban Heat Mitigation Analysis & Cost Assessment</div>
      <div class="meta-row">
        <div class="meta-item">
          <span class="meta-label">Generated</span>
          <span class="meta-value">${dateStr} at ${timeStr}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Active Period</span>
          <span class="meta-value">${timeOfDay.charAt(0).toUpperCase() + timeOfDay.slice(1)}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Pixels Selected</span>
          <span class="meta-value">${selectedPixels.length} (${totalArea.toLocaleString()} m²)</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Interventions</span>
          <span class="meta-value">${activeInterventions.length} Applied</span>
        </div>
      </div>
    </div>

    <div class="content">

      <!-- KPI Summary -->
      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Avg ΔT (${timeOfDay})</div>
          <div class="kpi-value cool">${signFormat(avgDelta)}°</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Total Area</div>
          <div class="kpi-value">${totalArea.toLocaleString()}<span class="kpi-unit"> m²</span></div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Total Est. Cost</div>
          <div class="kpi-value">${formatCurrency(totalCost)}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Cost-Effectiveness</div>
          <div class="kpi-value">${costEffectiveness ? formatCurrency(costEffectiveness) : "—"}<span class="kpi-unit"> /°C</span></div>
        </div>
      </div>

      <!-- Before / After -->
      <div class="section">
        <div class="section-title">Temperature Anomaly — Before & After</div>
        <table>
          <thead>
            <tr>
              <th>Time of Day</th>
              <th>Before (°C)</th>
              <th>After (°C)</th>
              <th>Change (ΔT)</th>
            </tr>
          </thead>
          <tbody>
            ${timeRows}
          </tbody>
        </table>
      </div>

      <!-- Per-Pixel Breakdown -->
      <div class="section">
        <div class="section-title">Per-Pixel Breakdown (${timeOfDay})</div>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Latitude</th>
              <th>Longitude</th>
              <th>Original</th>
              <th>Predicted</th>
              <th>ΔT</th>
            </tr>
          </thead>
          <tbody>
            ${perPixelRows}
          </tbody>
        </table>
      </div>

      <!-- Interventions Applied -->
      <div class="section">
        <div class="section-title">Interventions Applied</div>
        <table>
          <thead>
            <tr>
              <th>Intervention</th>
              <th>Description</th>
              <th>Affected Area</th>
              <th>Unit Cost</th>
              <th>Subtotal</th>
            </tr>
          </thead>
          <tbody>
            ${interventionRows}
            <tr style="border-top: 2px solid rgba(255,255,255,0.15);">
              <td colspan="4" style="font-weight:600; text-align:right;">Total Estimated Project Cost</td>
              <td style="font-weight:700; font-size:15px;">${formatCurrency(totalCost)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Recommendations -->
      <div class="section">
        <div class="section-title">Recommendations</div>
        <div class="rec-box">
          <div class="rec-title">Key Findings</div>
          <div class="rec-text">
            The simulation of <strong>${activeInterventions.length} intervention${activeInterventions.length > 1 ? "s" : ""}</strong> 
            across <strong>${selectedPixels.length} pixel${selectedPixels.length > 1 ? "s" : ""}</strong> 
            in <strong>${communityName}</strong> projects a mean temperature reduction of 
            <strong>${signFormat(avgDelta)}°C</strong> during the <strong>${timeOfDay}</strong> period.
          </div>
        </div>
        ${avgDelta < 0 ? `
        <div class="rec-box" style="margin-top:12px; background: rgba(99, 179, 237, 0.08); border-color: rgba(99, 179, 237, 0.2);">
          <div class="rec-title" style="color: #63b3ed;">Budget Analysis</div>
          <div class="rec-text">
            The total estimated project cost is <strong>${formatCurrency(totalCost)}</strong> 
            covering <strong>${totalArea.toLocaleString()} m²</strong> of urban area.
            ${costEffectiveness ? `At a cost-effectiveness ratio of <strong>${formatCurrency(costEffectiveness)} per °C</strong> of cooling, this represents a ${costEffectiveness < 500000 ? "highly competitive" : costEffectiveness < 2000000 ? "reasonable" : "substantial"} investment in urban heat mitigation.` : ""}
          </div>
        </div>
        ` : ""}
      </div>

    </div>

    <div class="footer">
      <span>Dubai Urban Heat Island Analysis Platform</span>
      <span>Generated ${dateStr}</span>
    </div>
  </div>

  <button class="print-btn no-print" onclick="window.print()">🖨️ Save as PDF</button>
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
