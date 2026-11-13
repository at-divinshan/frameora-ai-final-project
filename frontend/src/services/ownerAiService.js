import { normalizeOwnerPreferences, validateOwnerPreferences } from "../config/ownerPreferences";
import api from "./api";
import {
  isOwnerGalleryBatch,
  OWNER_GENERATION_CONTRACT,
} from "../config/ownerGeneration";

export const getOwnerEntitlements = () =>
  api.get("/owner/entitlements").then(({ data }) => data);

export const getOwnerPhotographyPlans = (signal) =>
  api.get("/owner/photography-plans", { signal }).then(({ data }) => data);

export const createOwnerPhotographyPlan = (values) =>
  api.post("/owner/photography-plans", values).then(({ data }) => data);

export const getOwnerGenerations = () =>
  api.get("/owner/ai/generations").then(({ data }) => data);

export const getOwnerGeneration = (generationId) =>
  api.get(`/owner/ai/generations/${generationId}`).then(({ data }) => data);

export const recoverOwnerGeneration = (generationId) =>
  api.post(`/owner/ai/generations/${generationId}/recover`).then(({ data }) => data);

export async function generateOwnerImages({
  planId,
  projectId,
  description = "",
  preferences,
  reference,
  backgroundReference,
  idempotencyKey,
}) {
  const customization = normalizeOwnerPreferences(preferences);
  if (Object.keys(validateOwnerPreferences(customization)).length) throw new Error("Invalid owner customization preferences.");
  const body = new FormData();
  body.append("plan_id", String(planId));
  body.append("idempotency_key", idempotencyKey);
  body.append("description", description);
  for (const [key, value] of Object.entries(customization)) body.append(key, value);
  if (reference) body.append("reference", reference);
  if (backgroundReference) body.append("background_reference", backgroundReference);
  const { data } = await api.post(projectId ? `/owner/projects/${projectId}/ai/generations` : "/owner/ai/generations", body, {
    headers: { "Content-Type": undefined },
    timeout: OWNER_GENERATION_CONTRACT.requestTimeoutMs,
  });
  return data;
}

export async function getOwnerGeneratedImage(assetId, signal) {
  const { data } = await api.get(`/owner/ai/images/${assetId}`, {
    responseType: "blob",
    signal,
  });
  return data;
}

export function ownerGenerationError(error) {
  const status = error.response?.status;
  const detail = error.response?.data?.detail;
  const message = typeof detail === "string" ? detail : detail?.message;

  if (status === 401) return "Your session has expired. Sign in again to continue.";
  if (status === 403) return "You do not have access to this plan or generation.";
  if (status === 402 || message === "insufficient_credits") {
    return "There are not enough available credits for this image batch.";
  }
  if (status === 409) {
    if (detail?.generation_id || /already in progress|still in progress/i.test(message || "")) {
      return "This generation is already in progress. Check its status before starting another batch.";
    }
    if (message === "subscription_required") return "Choose a subscription plan before generating images.";
    if (message === "onboarding_required") return "Complete your Studio Owner setup before generating images.";
    if (message === "paid_activation_disabled") return "Paid Pro generation is unavailable until payment activation is enabled.";
    if (/different inputs/i.test(message || "")) return "This request key belongs to a different submission. Keep the original inputs for a retry.";
    if (/recovery deadline elapsed/i.test(message || "")) return "The generation is being recovered. Check its status before trying again.";
    return "This request could not continue. Check its status before starting another batch.";
  }
  if (status === 503) {
    return detail?.generation_id
      ? "The request status is uncertain. Check this generation before retrying; keep the same request."
      : "The AI service is temporarily unavailable. The request status may be uncertain; retry only with the same request.";
  }
  if (status === 422) return "Check the photography plan, customization preferences, and reference photo, then try again.";
  return "The generation could not be confirmed. Check its status before starting another batch.";
}

export function ownerGenerationStatusMessage(generation) {
  if (generation?.status === "owner_reserved") {
    return "Your image batch is in progress. Do not start another generation while it is being processed.";
  }
  if (generation?.status === "failed") {
    return "This batch failed or timed out. Its reserved credits were refunded; start a new batch only when you are ready.";
  }
  if (generation?.status === "completed" &&
      !isOwnerGalleryBatch(generation.images, OWNER_GENERATION_CONTRACT, generation.charged_credits)) {
    return "This saved batch is incomplete and is hidden for safety. Contact support before retrying.";
  }
  return "";
}
