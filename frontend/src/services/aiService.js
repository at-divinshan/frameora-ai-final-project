import api from "./api";

export async function getFreeGenerationEligibility() {
  const { data } = await api.get("/ai/free-generation/eligibility");
  return data;
}
export async function generateImages({ planId, description = "", reference, backgroundReference }) {
  const body = new FormData();
  body.append("plan_id", planId);
  body.append("description", description);
  if (reference) body.append("reference", reference);
  if (backgroundReference) body.append("background_reference", backgroundReference);
  const { data } = await api.post("/ai/generations", body, {
    headers: { "Content-Type": undefined },
    // Four sequential provider calls; no automatic retries for this mutation.
    timeout: 1300000,
  });
  return data;
}

export async function getGenerations(signal, before) {
  const { data } = await api.get("/ai/generations", { signal, params: { before } });
  return data;
}

export async function getGeneratedImage(id, signal) {
  const { data } = await api.get(`/ai/images/${id}`, { responseType: "blob", signal });
  return data;
}

export function generationError(error) {
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : "Unable to confirm generation. Check your gallery before trying again.";
}
