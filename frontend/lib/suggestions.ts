import {
  FeatureVector,
  InterventionId,
  InterventionParams,
  INTERVENTION_TEMPLATES,
  getConflicts,
} from "./interventions";

export interface Suggestion {
  templateId: InterventionId;
  name: string;
  icon: string;
  deltaT: number;
  predictedAnomaly: number;
  params?: InterventionParams;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Generates smart suggestions by simulating each applicable intervention.
 */
export async function suggestInterventions(
  originalFeaturesBatch: FeatureVector[],
  currentAnomalies: { morning: number; afternoon: number; night: number },
  timeOfDay: "morning" | "afternoon" | "night",
  activeInterventions: InterventionId[]
): Promise<Suggestion[]> {
  // 1. Find all candidate templates that can be applied and don't conflict
  // We check canApply against ALL pixels to ensure the intervention is valid for the entire selected region
  const candidates = INTERVENTION_TEMPLATES.filter((template) => {
    // If any single pixel in the selection doesn't support this intervention, discard the template
    const isValidForAll = originalFeaturesBatch.every(pixelFeatures => template.canApply(pixelFeatures));
    if (!isValidForAll) return false;
    
    if (activeInterventions.includes(template.id)) return false; // Don't suggest if already active
    if (getConflicts(activeInterventions, template.id).length > 0) return false;
    return true;
  });

  if (candidates.length === 0) return [];

  // 2. Simulate each candidate via the backend batch API
  const simulationPromises = candidates.map(async (template) => {
    // Determine default params if needed (e.g., Construct Building)
    let params: InterventionParams | undefined;
    // The deafult ones are passed first to see the intervntion suggestions
    if (template.id === "construct_building") {
      params = { buildingDensity: 0.5, height: 10 };
    }

    // Dry-run the intervention to get the modified feature vectors
    const modifiedFeaturesBatch = originalFeaturesBatch.map(f => template.apply(f, params));

    try {
      const response = await fetch(`${API_BASE_URL}/api/predict-batch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ pixels: modifiedFeaturesBatch }),
      });

      if (!response.ok) {
        console.error(`Prediction failed for ${template.id}:`, await response.text());
        return null;
      }

      const data = await response.json();
      const newAnomaly = data.predicted_anomalies[timeOfDay];
      const deltaT = newAnomaly - currentAnomalies[timeOfDay];

      return {
        templateId: template.id,
        name: template.name,
        icon: template.icon,
        deltaT,
        predictedAnomaly: newAnomaly,
        params,
      } as Suggestion;
    } catch (error) {
      console.error(`Error simulating ${template.id}:`, error);
      return null;
    }
  });

  // 3. Wait for all simulations to finish
  const results = await Promise.all(simulationPromises);

  // 4. Filter out failures and sort by cooling impact (most negative deltaT first)
  const validSuggestions = results.filter((r): r is Suggestion => r !== null);
  
  validSuggestions.sort((a, b) => a.deltaT - b.deltaT);

  // 5. Return top 3
  return validSuggestions.slice(0, 3);
}
