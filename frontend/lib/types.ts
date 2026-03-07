export type TimeOfDay = "morning" | "afternoon" | "night";

export interface CommunityProperties {
  id: string;
  COMM_NUM: number;
  CNAME_E: string;
  population: number;
  area_km2: number;
  pop_density: number;

  anomaly_morning_mean: number;
  anomaly_morning_median: number;
  anomaly_morning_std: number;
  anomaly_morning_min: number;
  anomaly_morning_max: number;
  anomaly_morning_count: number;
  anomaly_morning_extreme_pct: number;

  anomaly_afternoon_mean: number;
  anomaly_afternoon_median: number;
  anomaly_afternoon_std: number;
  anomaly_afternoon_min: number;
  anomaly_afternoon_max: number;
  anomaly_afternoon_count: number;
  anomaly_afternoon_extreme_pct: number;

  anomaly_night_mean: number;
  anomaly_night_median: number;
  anomaly_night_std: number;
  anomaly_night_min: number;
  anomaly_night_max: number;
  anomaly_night_count: number;
  anomaly_night_extreme_pct: number;

  diurnal_range_mean: number;
  diurnal_range_std: number;

  ndvi_mean: number;
  green_fraction: number;
  albedo_mean: number;
  building_density_mean: number;
  building_height_mean: number;
  road_density_mean: number;
  sand_fraction_mean: number;
  water_fraction_mean: number;
  dist_to_coast_mean: number;

  // Computed client-side
  hvi?: number;
  priorityExposure?: boolean;
  [key: string]: any;
}

export interface CommunityFeature {
  type: "Feature";
  id?: number | string;
  geometry: any;
  properties: CommunityProperties;
}

export interface CommunityFeatureCollection {
  type: "FeatureCollection";
  features: CommunityFeature[];
  global_feature_ranges?: Record<string, [number, number]>;
}
