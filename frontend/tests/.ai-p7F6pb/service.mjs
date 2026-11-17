// <define:import.meta.env>
var define_import_meta_env_default = { VITE_API_URL: "http://localhost:8000" };

// src/services/api.js
import axios from "axios";
var api = axios.create({
  baseURL: define_import_meta_env_default.VITE_API_URL || "http://localhost:8000",
  timeout: 3e4,
  headers: {
    "Content-Type": "application/json"
  }
});
var accessToken = null;
var unauthorizedHandler = null;
function setAccessToken(token) {
  accessToken = token;
}
api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && error.config?.headers?.Authorization === `Bearer ${accessToken}` && error.config?.url !== "/auth/login" && error.config?.url !== "/auth/google/link/start") {
      unauthorizedHandler?.();
    }
    return Promise.reject(error);
  }
);
var api_default = api;

// src/services/aiService.js
async function getFreeGenerationEligibility() {
  const { data } = await api_default.get("/ai/free-generation/eligibility");
  let paid = null;
  try {
    paid = (await api_default.get("/user/payments/subscription")).data;
  } catch (error) {
    if (error.response?.status !== 503) throw error;
  }
  return { ...data, paid, generation_available: paid?.plan && paid.plan !== "free" ? paid.paid_generation_available : data.free_request_available };
}
async function generateImages({ planId, description = "", reference, backgroundReference, idempotencyKey }) {
  const body = new FormData();
  body.append("plan_id", planId);
  body.append("description", description);
  if (idempotencyKey) body.append("idempotency_key", idempotencyKey);
  if (reference) body.append("reference", reference);
  if (backgroundReference) body.append("background_reference", backgroundReference);
  const { data } = await api_default.post("/ai/generations", body, {
    headers: { "Content-Type": void 0 },
    // Four sequential provider calls; no automatic retries for this mutation.
    timeout: 13e5
  });
  return data;
}
async function getGenerations(signal, before) {
  const { data } = await api_default.get("/ai/generations", { signal, params: { before } });
  return data;
}
async function getGeneratedImage(id, signal) {
  const { data } = await api_default.get(`/ai/images/${id}`, { responseType: "blob", signal });
  return data;
}
function generationError(error) {
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : "Unable to confirm generation. Check your gallery before trying again.";
}
export {
  api_default as api,
  generateImages,
  generationError,
  getFreeGenerationEligibility,
  getGeneratedImage,
  getGenerations,
  setAccessToken
};
