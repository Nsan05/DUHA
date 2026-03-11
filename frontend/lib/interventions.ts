export type FeatureVector = Record<string, number>;

export type InterventionId =
  | "park"
  | "cool_road"
  | "cool_roof"
  | "green_roof"
  | "water_feature"
  | "construct_building";

// Optional intervention params
export interface InterventionParams {
  buildingDensity?: number;
  height?: number;
}

export interface InterventionTemplate {
  id: InterventionId;
  name: string;
  icon: string;
  description: string;
  requirementDescription: string;
  explanation: string;
  canApply: (features: FeatureVector) => boolean;
  apply: (features: FeatureVector, params?: InterventionParams) => FeatureVector;
  conflictsWith: InterventionId[];
  defaultCostPerSqM: number;
}

export const FEATURE_KEYS = [
  "ndvi_mean",
  "albedo_mean",
  "building_density_mean",
  "height_mean",
  "road_density_mean",
  "sand_mask_fraction",
  "water_mask_full_fraction",
  "dist_to_coast_m",
];

// Based on observed min/max in training rasters
export const FEATURE_RANGES: Record<string, [number, number]> = {
  ndvi_mean: [-0.3068, 0.671],
  albedo_mean: [0.0928, 1.0258],
  building_density_mean: [0, 1.0],
  height_mean: [0, 102.7687], // Min changed to 0 to support true empty sand patches
  road_density_mean: [0, 1.0],
  sand_mask_fraction: [0, 1.0], 
  water_mask_full_fraction: [0, 1.0], // Masks are 0 to 1 natively
};

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

export const INTERVENTION_TEMPLATES: InterventionTemplate[] = [
  {
    id: "park",
    name: "Park",
    icon: "🌳",
    description: "Convert sand into a vegetated park.",
    requirementDescription: "Requires 100% open sand.",
    explanation: "Replaces sand with dense vegetation, maximizing NDVI and lowering Albedo.",
    canApply: (features) => features.sand_mask_fraction === 1,
    apply: (features) => ({
      ...features,
      sand_mask_fraction: 0,
      ndvi_mean: 0.3965,
      albedo_mean: 0.3222,
    }),
    conflictsWith: ["water_feature", "construct_building"],
    defaultCostPerSqM: 200, // AED
  },
  {
    id: "cool_road",
    name: "Cool Road",
    icon: "🛣️",
    description: "Apply reflective coating to roads.",
    requirementDescription: "Requires existing roads.",
    explanation: "Increases surface albedo (reflectivity) of existing road infrastructure.",
    canApply: (features) => features.road_density_mean > 0,
    apply: (features) => ({
      ...features,
      albedo_mean: clamp(
        features.albedo_mean + features.road_density_mean * (0.7 - features.albedo_mean),
        FEATURE_RANGES.albedo_mean[0],
        FEATURE_RANGES.albedo_mean[1]
      ),
    }),
    conflictsWith: [],
    defaultCostPerSqM: 50, // AED
  },
  {
    id: "cool_roof",
    name: "Cool Roof",
    icon: "🏢",
    description: "Apply reflective coating to building roofs.",
    requirementDescription: "Requires existing buildings.",
    explanation: "Increases structural Albedo to simulate bright, sun-reflecting rooftops.",
    canApply: (features) => features.building_density_mean > 0,
    apply: (features) => ({
      ...features,
      albedo_mean: clamp(
        features.albedo_mean + features.building_density_mean * (0.8 - features.albedo_mean),
        FEATURE_RANGES.albedo_mean[0],
        FEATURE_RANGES.albedo_mean[1]
      ),
    }),
    conflictsWith: ["green_roof"],
    defaultCostPerSqM: 40, // AED
  },
  {
    id: "green_roof",
    name: "Green Roof",
    icon: "🌿",
    description: "Install extensive green roofs on buildings.",
    requirementDescription: "Requires existing buildings.",
    explanation: "Increases NDVI and slightly adjusts Albedo on building footprints to simulate rooftop vegetation.",
    canApply: (features) => features.building_density_mean > 0,
    apply: (features) => ({
      ...features,
      ndvi_mean: clamp(
        features.ndvi_mean + features.building_density_mean * (0.28 - features.ndvi_mean),
        FEATURE_RANGES.ndvi_mean[0],
        FEATURE_RANGES.ndvi_mean[1]
      ),
      albedo_mean: clamp(
        features.albedo_mean + features.building_density_mean * (0.326 - features.albedo_mean),
        FEATURE_RANGES.albedo_mean[0],
        FEATURE_RANGES.albedo_mean[1]
      ),
    }),
    conflictsWith: ["cool_roof"],
    defaultCostPerSqM: 300, // AED
  },
  {
    id: "water_feature",
    name: "Water Feature",
    icon: "💧",
    description: "Convert sand to a large water body.",
    requirementDescription: "Requires 100% open sand.",
    explanation: "Replaces sand entirely with a high thermal capacity water body.",
    canApply: (features) => features.sand_mask_fraction === 1,
    apply: (features) => ({
      ...features,
      sand_mask_fraction: 0,
      water_mask_full_fraction: 1,
      ndvi_mean: -0.018,
      albedo_mean: 0.142,
    }),
    conflictsWith: ["park", "construct_building"],
    defaultCostPerSqM: 1500, // AED
  },
  {
    id: "construct_building",
    name: "Construct Building",
    icon: "🏗️",
    description: "Construct a new dense urban block.",
    requirementDescription: "Requires 100% open sand.",
    explanation: "Replaces sand with a specified density and height of building structures.",
    canApply: (features) => features.sand_mask_fraction === 1,
    apply: (features, params) => {
      const density = params?.buildingDensity ?? 0.5;
      const hgt = params?.height ?? 10;
      return {
        ...features,
        sand_mask_fraction: 0,
        building_density_mean: density,
        height_mean: hgt,
        ndvi_mean: 0.027,
        albedo_mean: 0.425,
        road_density_mean: clamp( 
          features.road_density_mean + 0.02, // 2% of the pixel is now road once building is constructed
          FEATURE_RANGES.road_density_mean[0],
          FEATURE_RANGES.road_density_mean[1]
        ),
      };
    },
    conflictsWith: ["park", "water_feature"],
    defaultCostPerSqM: 4000, // AED
  },
];

export function validateFeatures(features: FeatureVector): {
  valid: boolean;
  errors: string[];
} {
  const errors: string[] = [];

  // For expert mode changes
  if (features.sand_mask_fraction + features.water_mask_full_fraction > 1) {
    errors.push("A pixel cannot be both sand and water");
  }

  for (const [key, [min, max]] of Object.entries(FEATURE_RANGES)) {
    if (key in features && (features[key] < min || features[key] > max)) {
      errors.push(`${key} must be between ${min} and ${max}`);
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}

// Detemrining if a new intervention conflicts with any of the active interventions
export function getConflicts(
  activeInterventions: InterventionId[],
  candidate: InterventionId
): InterventionId[] {
  // Select the template of the intervention to be added
  const template = INTERVENTION_TEMPLATES.find((t) => t.id === candidate);
  if (!template) return [];

  return activeInterventions.filter((activeId) => {
    return template.conflictsWith.includes(activeId);
  });
}
