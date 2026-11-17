// <define:import.meta.env>
var define_import_meta_env_default = {};

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

// src/services/feedbackService.js
var getComments = (token, id, signal) => api_default.get(`/sharing/${encodeURIComponent(token)}/images/${id}/comments`, { signal }).then((r) => r.data);
var addComment = (token, id, data) => api_default.post(`/sharing/${encodeURIComponent(token)}/images/${id}/comments`, data).then((r) => r.data);
var getFeedback = (project, signal) => api_default.get(`/owner/projects/${project}/feedback`, { signal }).then((r) => r.data);
var updateFeedback = (project, id, data) => api_default.patch(`/owner/projects/${project}/feedback/${id}`, data).then((r) => r.data);
function feedbackError(error) {
  const status = error.response?.status;
  if (status === 503) return "Comments are not available yet. Please try again later.";
  if (status === 404) return "This image or share link is no longer available.";
  if (status === 401) return "Please sign in again.";
  if (status === 422) return "Enter a comment of 1\u20132,000 characters without control characters.";
  if (status === 409) return "The submission could not be confirmed. Retry your unchanged comment.";
  return "Unable to save or load feedback. Please try again.";
}

// src/components/ai/RevisionInstructions.jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Fragment, jsx, jsxs } from "react/jsx-runtime";
function selectRevision(rows, projectId, planId, feedbackId) {
  return rows.find((row) => String(row.id) === String(feedbackId) && String(row.project_id) === String(projectId) && String(row.plan_id) === String(planId));
}

// src/config/ownerPreferences.js
var OWNER_PREFERENCE_MODES = [
  ["background_mode", "Background Variation", ["same", "different", "custom"]],
  ["pose_mode", "Pose Variation", ["high", "natural", "custom"]],
  ["camera_angle_mode", "Camera Angles", ["mixed", "eye", "cinematic", "custom"]],
  ["outfit_mode", "Outfit Variation", ["same", "different", "custom"]]
];
var OWNER_PREFERENCE_TEXT = [
  ["dress_colors", "Dress Colors", 200],
  ["outfit_details", "Outfit Details", 1e3],
  ["additional_instructions", "Additional Custom Instructions", 2e3]
];
var DEFAULT_OWNER_PREFERENCES = Object.freeze({
  background_mode: "same",
  pose_mode: "natural",
  camera_angle_mode: "mixed",
  outfit_mode: "same",
  dress_colors: "",
  outfit_details: "",
  additional_instructions: ""
});
function normalizeOwnerPreferences(values = {}) {
  return Object.fromEntries(Object.entries(DEFAULT_OWNER_PREFERENCES).map(([key, fallback]) => [key, typeof values[key] === "string" ? values[key].trim() : fallback]));
}
function validateOwnerPreferences(values) {
  const errors = {};
  for (const [key, label, options] of OWNER_PREFERENCE_MODES) {
    if (!options.includes(values[key])) errors[key] = `Choose a supported ${label.toLowerCase()} option.`;
  }
  for (const [key, label, limit] of OWNER_PREFERENCE_TEXT) {
    if (typeof values[key] !== "string" || Array.from(values[key]).length > limit) errors[key] = `${label} must be ${limit} characters or fewer.`;
  }
  const custom = OWNER_PREFERENCE_MODES.slice(0, 3).filter(([key]) => values[key] === "custom").map(([, label]) => label.toLowerCase());
  if (custom.length && !values.additional_instructions?.trim()) errors.additional_instructions = `Describe your custom ${custom.join(", ")} in Additional Custom Instructions.`;
  if (values.outfit_mode === "custom" && !values.outfit_details?.trim()) errors.outfit_details = "Add Outfit Details when using a custom outfit.";
  return errors;
}

// ../owner-generation.config.json
var owner_generation_config_default = {
  studioOwnerBatchSize: 2
};

// src/config/ownerGeneration.js
var batchSize = owner_generation_config_default.studioOwnerBatchSize ?? 8;
if (![2, 8].includes(batchSize)) throw new Error("studioOwnerBatchSize must be 2 or 8");
var OWNER_GENERATION_CONTRACT = Object.freeze({
  batchSize,
  batchCost: batchSize,
  requestTimeoutMs: 13e5
});
var LEGACY_OWNER_CONTRACT = Object.freeze({
  batchSize: 4,
  batchCost: 4
});
var LEGACY_OWNER_BATCH_SIZES = Object.freeze([2, 4, 8]);

// src/services/ownerAiService.js
async function generateOwnerImages({
  planId,
  projectId,
  description = "",
  preferences,
  reference,
  backgroundReference,
  idempotencyKey
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
  const { data } = await api_default.post(projectId ? `/owner/projects/${projectId}/ai/generations` : "/owner/ai/generations", body, {
    headers: { "Content-Type": void 0 },
    timeout: OWNER_GENERATION_CONTRACT.requestTimeoutMs
  });
  return data;
}

// src/components/ai/ImageComments.jsx
import { useEffect as useEffect2, useRef, useState as useState2 } from "react";
import { jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
function CommentHistory({ comments }) {
  return comments.map((row) => /* @__PURE__ */ jsxs2("article", { children: [
    /* @__PURE__ */ jsx2("p", { className: "feedback-text", children: row.comment }),
    /* @__PURE__ */ jsxs2("small", { children: [
      row.status.replace("_", " "),
      " \xB7 ",
      /* @__PURE__ */ jsx2("time", { dateTime: row.created_at, children: new Date(row.created_at).toLocaleString() })
    ] })
  ] }, row.id));
}
function ImageComments({ token, imageId }) {
  const [comments, setComments] = useState2([]), [draft, setDraft] = useState2("");
  const [open, setOpen] = useState2(false), [busy, setBusy] = useState2(false), [error, setError] = useState2(""), [success, setSuccess] = useState2("");
  const [revision, setRevision] = useState2(0);
  const request = useRef(null), submitting = useRef(false);
  useEffect2(() => {
    const controller = new AbortController();
    setComments([]);
    setError("");
    getComments(token, imageId, controller.signal).then((rows) => {
      if (!controller.signal.aborted) setComments(rows);
    }).catch((e) => {
      if (!controller.signal.aborted) setError(feedbackError(e));
    });
    return () => controller.abort();
  }, [token, imageId, revision]);
  async function submit(event) {
    event.preventDefault();
    if (submitting.current || !draft.trim()) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setSuccess("");
    const comment = draft.trim();
    if (!request.current || request.current.comment !== comment) request.current = { comment, request_key: crypto.randomUUID() };
    try {
      const saved = await addComment(token, imageId, request.current);
      setComments((rows) => [...rows.filter((row) => row.id !== saved.id), saved]);
      setDraft("");
      request.current = null;
      setOpen(false);
      setSuccess("Comment sent to the studio.");
    } catch (e) {
      setError(feedbackError(e));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return /* @__PURE__ */ jsxs2("section", { className: "image-feedback", "aria-label": "Your image comments", children: [
    /* @__PURE__ */ jsx2("h3", { children: "Your feedback" }),
    /* @__PURE__ */ jsx2(CommentHistory, { comments }),
    success && /* @__PURE__ */ jsx2("p", { role: "status", children: success }),
    error && /* @__PURE__ */ jsxs2("p", { role: "alert", children: [
      error,
      " ",
      /* @__PURE__ */ jsx2("button", { type: "button", className: "account-secondary", onClick: () => setRevision((n) => n + 1), children: "Reload comments" })
    ] }),
    open ? /* @__PURE__ */ jsxs2("form", { onSubmit: submit, children: [
      /* @__PURE__ */ jsx2("label", { htmlFor: `comment-${imageId}`, children: "Request a change" }),
      /* @__PURE__ */ jsx2("textarea", { id: `comment-${imageId}`, maxLength: 2e3, required: true, disabled: busy, value: draft, onChange: (e) => setDraft(e.target.value) }),
      /* @__PURE__ */ jsx2("button", { className: "owner-gradient-button", disabled: busy || !draft.trim(), children: busy ? "Sending\u2026" : "Submit Comment" }),
      " ",
      /* @__PURE__ */ jsx2("button", { type: "button", className: "account-secondary", disabled: busy, onClick: () => setOpen(false), children: "Cancel" })
    ] }) : /* @__PURE__ */ jsx2("button", { className: "account-secondary", onClick: () => {
      setOpen(true);
      setSuccess("");
    }, children: "Add Comment" })
  ] });
}
export {
  CommentHistory,
  ImageComments,
  addComment,
  api_default as api,
  feedbackError,
  generateOwnerImages,
  getComments,
  getFeedback,
  selectRevision,
  updateFeedback
};
