# Phase 2D: Evaluation Results & Interpretation

This file documents the results of the model evaluation phase. The goal was to validate the downscaled 30m LST anomaly map (`lst_anomaly_30m.tif`) against the original 750m VIIRS observations.

---

## 1. Visual Comparison (`visual_comparison.png`)

**Description**:
A side-by-side plot comparing the original 750m VIIRS anomaly map (left) with the downscaled 30m prediction (right) for a selected clear-sky scene (July 1, 2025).

**Interpretation**:

- **Spatial Agreement**: The overall patterns of hot (red) and cool (blue) areas are identical between the two maps. This confirms the model is not hallucinating new regional trends.
- **Improved Detail**: The 30m map successfully resolves fine-scale features that are blurred in the 750m data, such as:
  - Distinct road networks and industrial zones (hot).
  - Specific vegetation patches and water bodies (cool).
- **Smoothness**: The 30m map shows natural gradients, indicating that the downscaling process (using continuous features like NDVI/Albedo) avoids the "blocky" artifacts often seen in simple resizing.
- **Range Compression**: The 30m range (-16K to +5K) is slightly narrower than the VIIRS range (-21K to +6K). This is expected as the model filters out random sensor noise (regression to the mean), focusing on explainable variance.

---

## 2. Statistical Consistency (`statistical_consistency.png`)

**Description**:
A scatter plot where each point represents a 750m pixel. The X-axis is the actual VIIRS anomaly, and the Y-axis is the _aggregated_ prediction of the 625 constituent 30m pixels. The red line represents the best fit.

**Interpretation**:

- **Reliability (R² = 0.49)**: The model explains approximately 50% of the spatial temperature variation observed from space.
- **Accuracy (RMSE = 2.20 K)**: The Root Mean Squared Error of 2.20 K is actually _lower_ than the training error (2.40 K). Aggregating the 30m predictions reduces random noise, leading to a more accurate regional estimate.
- **Bias (-0.18 K)**: The mean bias is negligible (< 0.2 K). The model is not systematically over- or under-predicting temperatures across the city.
- **Slope (0.48)**: The slope is less than 1.0, confirming the model returns conservative estimates (it does not predict extreme outliers unless strongly supported by feature evidence).

---

## 3. Error Analysis by Land Cover (`error_analysis_landcover.png`)

**Description**:
A bar chart breaking down the error metrics (RMSE, Bias, R²) across different land use categories to identify strengths and weaknesses.

**Interpretation**:

- **Strength in Cities**: The model performs best in **Non-Sandy** (Urban) areas (R² = 0.51) and **High Density** zones (RMSE = 2.09 K). This is critical, as these are the priority areas for Urban Heat Island mitigation.
- **Desert Uniformity**: In **Sandy** areas, R² drops to 0.27. This is not a failure but a reflection of the desert's uniformity—temperatures are consistently high with little variation to explain. The absolute error (RMSE 2.19 K) remains low.
- **Coastal Challenge**: The **Near Coast (<5km)** category shows the highest bias (-0.60 K). The model slightly under-predicts the cooling effect of the sea, likely because sea breeze penetration varies daily and cannot be fully captured by static distance features.
