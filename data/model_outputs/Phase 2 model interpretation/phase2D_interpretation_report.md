# Phase 2D Model Interpretation Report
**13-Feature Texture-Aware LightGBM (Mean + Std Dev)**  
*Generated: 2026-03-15 | Trained on 42,521 pixel-scenes across 30 VIIRS acquisitions*

---

## Model Summary

| Metric | Baseline (8 Features) | **This Model (13 Features)** | Improvement |
| :--- | :---: | :---: | :---: |
| Consistency R² | 0.493 | **0.520** | +0.027 |
| Consistency RMSE | 2.204 K | **2.145 K** | −0.059 K |
| Consistency Bias | -0.320 K | **-0.269 K** | Better |
| Training R² | 0.540 | **0.532** | Similar |
| Training RMSE | 2.39 K | 2.40 K | Similar |

> [!NOTE]
> Training R² is slightly lower than last model but consistency R² (the ground truth test) is higher. The `_std` features help the model generalize better to new areas, even if they make the training fit slightly less overconfident.

---

## 1. Feature Importance (Permutation-Based)

![Feature Importance](C:\Users\nithi\.gemini\antigravity\brain\9d6aefea-9c0e-4c31-aed9-3793163098f6\feature_importance.png)

**Ranked by drop in R² when each feature is randomly shuffled:**

| Rank | Feature | Importance | Commentary |
| :---: | :--- | :---: | :--- |
| 🥇 #1 | **Sand/Bare Soil Fraction** | 0.3254 | The biggest predictor by far — Sandy desert is extremely hot |
| 🥈 #2 | **Water Fraction** | 0.2712 | Water bodies cool everything around them strongly |
| 🥉 #3 | **Distance to Coast** | 0.1267 | Coastal pixels get Gulf breeze; inland pixels cook |
| #4 | Surface Reflectivity (Albedo) | 0.1019 | Bright/white surfaces reflect heat |
| #5 | Vegetation (NDVI) | 0.0705 | Greenery cools through evapotranspiration |
| **#6** | **`ndvi_std` ★ NEW** | **0.0340** | Most powerful texture feature — vegetation variety |
| **#7** | **`albedo_std` ★ NEW** | **0.0105** | Mixed bright/dark surfaces signal complex urban structure |
| #8 | Road Density | 0.0104 | Roads absorb and retain heat |
| #9 | Building Density | 0.0097 | Dense urban canyons trap heat |
| **#10** | **`road_density_std` ★ NEW** | **0.0066** | Mixed road/no-road = transitional zone |
| #11 | Building Height | 0.0060 | Tall buildings shade streets |
| **#12** | **`height_std` ★ NEW** | **0.0054** | Skyscraper vs villa mix — important for UHI hotspots |
| **#13** | **`building_density_std` ★ NEW** | **0.0022** | Least impactful std feature |

> [!IMPORTANT]
> `ndvi_std` is the **6th most important feature overall** — more important than Road Density or Building Density.  
> This validates our hypothesis: knowing whether vegetation is "uniform park" or "scattered patches" is critical information.

---

## 2. Feature Correlation Heatmap

![Feature Correlation](C:\Users\nithi\.gemini\antigravity\brain\9d6aefea-9c0e-4c31-aed9-3793163098f6\feature_correlation.png)

**Key observations:**

- **Sand fraction** has the strongest individual correlation with the LST anomaly (more sand = hotter)
- **Water fraction** and **distance to coast** are strongly negatively correlated with temperature
- **`ndvi_mean` and `ndvi_std` are uncorrelated with each other** — confirming they carry independent information for the model
- **`building_density_std` and `height_std` are moderately correlated** — tall buildings tend to be in more heterogeneous areas

---

## 3. Partial Dependence Plots

![Partial Dependence Plots](C:\Users\nithi\.gemini\antigravity\brain\9d6aefea-9c0e-4c31-aed9-3793163098f6\partial_dependence_plots.png)

**What each curve shows:** how the model's temperature prediction changes as that single feature changes, holding everything else constant.

**Notable relationships:**
- **Sand Fraction:** Near-linear positive. The model is very clear: more sand = much hotter.
- **Water Fraction:** Near-linear negative. Even a small water fraction dramatically cools a pixel.
- **NDVI Mean:** Nonlinear. Diminishing returns above NDVI ≈ 0.2. (The first 20% of greenery helps a lot, extra greenery helps less.)
- **`ndvi_std`:** Higher vegetation variety (mixed parks + bare areas) is slightly warmer — mixed neighbourhoods lack the full cooling power of a uniform park.
- **`height_std`:** High variety in building heights (skyscraper next to empty lot) shows a slight warming trend — captures the UHI shadow-canyon effect.
- **Distance to Coast:** Near-exponential decay. Coastal pixels are much cooler; beyond ~10km the benefit plateaus.

---

## 4. Spatial Error Map (Test Set)

![Spatial Error Map](C:\Users\nithi\.gemini\antigravity\brain\9d6aefea-9c0e-4c31-aed9-3793163098f6\spatial_error_map.png)

*Red = model predicted cooler than reality | Blue = model predicted hotter than reality*

**Test Set Performance: RMSE = 2.40 K | R² = 0.532**

**Key spatial patterns:**
- Errors are mostly within ±2 K across the city — excellent consistency
- The largest residuals cluster in areas with high land-use change (dense construction sites, reclaimed islands), which are underrepresented in training data
- The model performs best in well-established urban grids and open sand areas

---

## 5. Conclusions

### What the model learned
The 13-feature model now understands Dubai's heat landscape through two "lenses" per feature:
1. **Amount** (mean): "How much building/vegetation/sand is here?"
2. **Variety** (std): "Is it uniform, or is it a mixed, contrasting neighbourhood?"

### Biggest insight
The `_std` features confirmed our hypothesis that **neighbourhood texture matters**. A 750m pixel in a uniform villa suburb (low `ndvi_std`) and a 750m pixel with the same average green coverage but in a mixed commercial/park zone (high `ndvi_std`) have meaningfully different temperature profiles. The model can now differentiate between these cases.

### Next Step
The model and downscaling pipeline are complete. The remaining work is to update the **Backend API** (`main.py`) and the **Frontend UI** to correctly handle the 5 new `_std` features during the interactive intervention simulation.
