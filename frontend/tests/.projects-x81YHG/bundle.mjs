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

// src/services/projectService.js
var getProjects = (signal) => api_default.get("/owner/projects", { signal }).then((r) => r.data);
var getProject = (id, signal) => api_default.get(`/owner/projects/${id}`, { signal }).then((r) => r.data);
var createProject = (values) => api_default.post("/owner/projects", values).then((r) => r.data);
var updateProject = (id, values) => api_default.patch(`/owner/projects/${id}`, values).then((r) => r.data);
function projectError(error, action = "load") {
  const status = error.response?.status;
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You do not have permission to access this project.";
  if (status === 404) return "This project could not be found.";
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (status === 422) return "Check your project details and try again.";
  return `Unable to ${action} the project. Please try again.`;
}
var getProjectPlans = (id, signal) => api_default.get(`/owner/projects/${id}/photography-plans`, { signal }).then((r) => r.data);
var createProjectPlan = (id, values) => api_default.post(`/owner/projects/${id}/photography-plans`, values).then((r) => r.data);
var linkProjectPlan = (id, planId) => api_default.post(`/owner/projects/${id}/photography-plans/${planId}`).then((r) => r.data);
async function getProjectGenerations(id, signal) {
  const items = [];
  let before;
  do {
    const { data } = await api_default.get(`/owner/projects/${id}/ai/generations`, { signal, params: { before } });
    items.push(...data);
    if (data.length < 20) break;
    const next = data.at(-1).id;
    if (before != null && next >= before) throw new Error("Invalid gallery pagination");
    before = next;
  } while (!signal?.aborted);
  return items;
}
var eligibleProjectPlans = (plans) => plans.filter((plan) => plan.project_id == null);

// src/services/shareService.js
var getProjectShareLinks = (id, signal) => api_default.get(`/owner/projects/${id}/share-links`, { signal }).then((r) => r.data);
var createProjectShareLink = (id, values) => api_default.post(`/owner/projects/${id}/share-links`, values).then((r) => r.data);
var deactivateProjectShareLink = (id, linkId) => api_default.delete(`/owner/projects/${id}/share-links/${linkId}`);
var getSharedGallery = (token, signal) => api_default.get(`/sharing/${encodeURIComponent(token)}`, { signal }).then((r) => r.data);
var getSharedImage = (token, id, signal) => api_default.get(`/sharing/${encodeURIComponent(token)}/images/${id}`, { responseType: "blob", signal }).then((r) => r.data);
function shareLinkStatus(link, now = Date.now()) {
  if (!link.is_active) return "Inactive";
  const expiry = link.expires_at && new Date(/[Zz]|[+-]\d\d:\d\d$/.test(link.expires_at) ? link.expires_at : `${link.expires_at}Z`).getTime();
  return expiry && expiry <= now ? "Expired" : "Active";
}
async function getShareUsage(signal) {
  const projects = await getProjects(signal);
  const lists = await Promise.all(projects.map((p) => getProjectShareLinks(p.id, signal)));
  return lists.flat().filter((link) => shareLinkStatus(link) === "Active").length;
}
function sharingError(error) {
  if ([404, 410].includes(error.response?.status)) return "This share link is invalid, expired, or deactivated. Ask the studio for a new link.";
  if (error.response?.status === 403) return "You do not have access to this shared gallery.";
  return "Unable to load the shared gallery. Please try again.";
}
var publishProjectPhase = (projectId, linkId, phaseId) => api_default.put(`/owner/projects/${projectId}/share-links/${linkId}/phases/${phaseId}`).then((r) => r.data);
var getOwnerShareLinks = (projectId, before, signal) => api_default.get("/owner/share-links", { params: { project_id: projectId || void 0, before }, signal }).then((r) => r.data);
var setShareLinkActive = (projectId, linkId, isActive) => api_default.patch(`/owner/projects/${projectId}/share-links/${linkId}`, { is_active: isActive }).then((r) => r.data);
function cachedShareUrl(storage, ownerId, projectId, linkId, origin) {
  try {
    const value = JSON.parse(storage.getItem(`frameora.photoshoot.share.${ownerId}.${projectId}`))?.[linkId];
    if (typeof value !== "string") return null;
    const url = new URL(value);
    return url.origin === origin && /^\/sharing\/[A-Za-z0-9_-]{43}$/.test(url.pathname) && !url.search && !url.hash ? url.href : null;
  } catch {
    return null;
  }
}

// src/utils/shareReturn.js
function safeShareReturn(value) {
  return typeof value === "string" && /^\/sharing\/[A-Za-z0-9_-]+$/.test(value) ? value : null;
}
function shareReturnFromSearch(search) {
  return safeShareReturn(new URLSearchParams(search).get("returnTo"));
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

// src/utils/ownerLimits.js
var limitLabel = (limit) => limit === null ? "Unlimited" : Number.isInteger(limit) && limit >= 0 ? limit : "Unavailable";

// src/components/projects/ProjectWorkspace.jsx
import { useEffect as useEffect6, useRef as useRef5, useState as useState7 } from "react";
import { Link as Link2 } from "react-router-dom";

// src/components/ai/ProjectFolders.jsx
import { useEffect, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";

// src/hooks/useAuth.js
import { useContext } from "react";

// src/context/AuthContext.jsx
import { createContext, useCallback, useEffect as useEffect2, useRef, useState as useState2 } from "react";
import { jsx as jsx2 } from "react/jsx-runtime";
var AuthContext = createContext(null);

// src/components/photography/PlanForm.jsx
import { useState as useState4 } from "react";
import { ArrowRight } from "lucide-react";

// src/components/common/Button.jsx
import { jsx as jsx3 } from "react/jsx-runtime";
function Button({
  children,
  type = "button",
  loading = false,
  disabled = false,
  className = "",
  ...props
}) {
  return /* @__PURE__ */ jsx3(
    "button",
    {
      type,
      disabled: disabled || loading,
      className: `gradient-button ${className}`,
      ...props,
      children: loading ? "Please wait..." : children
    }
  );
}

// src/components/common/Input.jsx
import { useState as useState3 } from "react";
import { Eye, EyeOff } from "lucide-react";
import { jsx as jsx4, jsxs as jsxs2 } from "react/jsx-runtime";
function Input({
  label,
  id,
  type = "text",
  error,
  icon,
  ...props
}) {
  const [showPassword, setShowPassword] = useState3(false);
  const isPassword = type === "password";
  return /* @__PURE__ */ jsxs2("div", { className: "form-field", children: [
    /* @__PURE__ */ jsx4("label", { htmlFor: id, children: label }),
    /* @__PURE__ */ jsxs2("div", { className: `input-wrapper ${error ? "has-error" : ""}`, children: [
      icon && /* @__PURE__ */ jsx4("span", { className: "input-icon", "aria-hidden": "true", children: icon }),
      /* @__PURE__ */ jsx4(
        "input",
        {
          id,
          type: isPassword && showPassword ? "text" : type,
          "aria-invalid": Boolean(error),
          "aria-describedby": error ? `${id}-error` : void 0,
          ...props
        }
      ),
      isPassword && /* @__PURE__ */ jsx4(
        "button",
        {
          type: "button",
          className: "password-toggle",
          onClick: () => setShowPassword(!showPassword),
          "aria-label": showPassword ? "Hide password" : "Show password",
          children: showPassword ? /* @__PURE__ */ jsx4(EyeOff, { size: 19 }) : /* @__PURE__ */ jsx4(Eye, { size: 19 })
        }
      )
    ] }),
    error && /* @__PURE__ */ jsx4("span", { className: "field-error", id: `${id}-error`, role: "alert", children: error })
  ] });
}

// src/components/photography/PlanForm.jsx
import { jsx as jsx5, jsxs as jsxs3 } from "react/jsx-runtime";

// src/components/photography/PlanCard.jsx
import { useEffect as useEffect4, useRef as useRef3, useState as useState5 } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, MapPin, Pencil, Sparkles, Trash2, Users } from "lucide-react";

// src/components/photography/PlanDeleteDialog.jsx
import { useEffect as useEffect3, useRef as useRef2 } from "react";
import { jsx as jsx6, jsxs as jsxs4 } from "react/jsx-runtime";

// src/components/photography/PlanCard.jsx
import { jsx as jsx7, jsxs as jsxs5 } from "react/jsx-runtime";
var preferenceLabels = [
  ["photography_style", "Photography Style"],
  ["lighting_preference", "Lighting"],
  ["pose_preference", "Pose"],
  ["camera_angle_preference", "Camera Angle"],
  ["outfit_color", "Outfit Color"],
  ["clothing_style", "Clothing Style"],
  ["outfit_details", "Outfit Details"],
  ["extra_instructions", "Extra Instructions"]
];
function preferenceEntries(value) {
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      return [];
    }
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  const entries = preferenceLabels.flatMap(([key, label]) => {
    const item = Object.hasOwn(value, key) ? value[key] : null;
    if (typeof item !== "string" && typeof item !== "number" && typeof item !== "boolean") return [];
    const text = String(item).trim();
    return text ? [[key, label, text]] : [];
  });
  const equipment = value.equipment;
  if (equipment && typeof equipment === "object" && !Array.isArray(equipment)) {
    const parts = [];
    if (typeof equipment.device_type === "string") parts.push(equipment.device_type);
    if (typeof equipment.camera_model === "string" && equipment.camera_model.trim()) parts.push(equipment.camera_model.trim());
    if (typeof equipment.lens === "string" && equipment.lens.trim()) parts.push(`Lens: ${equipment.lens.trim()}`);
    if (typeof equipment.additional_equipment === "string" && equipment.additional_equipment.trim()) {
      parts.push(`Additional equipment: ${equipment.additional_equipment.trim()}`);
    }
    if (parts.length) entries.push(["equipment", "Photography Equipment", parts.join(" \xB7 ")]);
  }
  return entries;
}

// src/components/ai/GeneratedImageCard.jsx
import { useEffect as useEffect5, useRef as useRef4, useState as useState6 } from "react";
import { Fragment, jsx as jsx8, jsxs as jsxs6 } from "react/jsx-runtime";

// src/components/projects/ProjectWorkspace.jsx
import { Fragment as Fragment2, jsx as jsx9, jsxs as jsxs7 } from "react/jsx-runtime";
function LinkedProjectPlan({ plan, editable, projectId }) {
  return /* @__PURE__ */ jsxs7("details", { className: "project-linked-plan", children: [
    /* @__PURE__ */ jsxs7("summary", { children: [
      "Open plan #",
      plan.id,
      " \xB7 ",
      plan.photography_type,
      " \xB7 ",
      plan.environment
    ] }),
    /* @__PURE__ */ jsxs7("dl", { className: "account-details", children: [
      /* @__PURE__ */ jsxs7("div", { children: [
        /* @__PURE__ */ jsx9("dt", { children: "People" }),
        /* @__PURE__ */ jsx9("dd", { children: plan.people_count })
      ] }),
      /* @__PURE__ */ jsxs7("div", { children: [
        /* @__PURE__ */ jsx9("dt", { children: "Location" }),
        /* @__PURE__ */ jsx9("dd", { children: plan.location || "Not provided" })
      ] }),
      /* @__PURE__ */ jsxs7("div", { children: [
        /* @__PURE__ */ jsx9("dt", { children: "Shoot date/time" }),
        /* @__PURE__ */ jsx9("dd", { children: plan.shoot_datetime?.replace("T", " ") || "Not scheduled" })
      ] }),
      preferenceEntries(plan.preferences).map(([key, label, value]) => /* @__PURE__ */ jsxs7("div", { children: [
        /* @__PURE__ */ jsx9("dt", { children: label }),
        /* @__PURE__ */ jsx9("dd", { className: "studio-description", children: value })
      ] }, key))
    ] }),
    editable && /* @__PURE__ */ jsxs7(Link2, { className: "account-secondary", to: `/owner/ai/generate?project=${projectId}&plan=${plan.id}`, children: [
      "Generate ",
      OWNER_GENERATION_CONTRACT.batchSize,
      " images / ",
      OWNER_GENERATION_CONTRACT.batchCost,
      " credits"
    ] })
  ] });
}

// src/components/projects/ProjectForm.jsx
import { useRef as useRef6, useState as useState8 } from "react";
import { jsx as jsx10, jsxs as jsxs8 } from "react/jsx-runtime";
var projectFields = [
  ["project_title", "Project title", 150],
  ["customer_name", "Customer name", 100],
  ["customer_contact", "Customer contact", 100],
  ["event_type", "Event type", 100],
  ["shooting_date", "Shooting date", null, "date"],
  ["shoot_location", "Location", 255]
];
function projectValues(values) {
  return Object.fromEntries([...projectFields.map(([key]) => key), "requirements"].map((key) => [key, values[key]?.trim() || null]));
}
function ProjectForm({ project = {}, onSubmit, disabled = false, editing = false }) {
  const [values, setValues] = useState8(() => Object.fromEntries(
    [...projectFields.map(([key]) => key), "requirements"].map((key) => [key, project[key] || ""])
  ));
  const [error, setError] = useState8("");
  const [busy, setBusy] = useState8(false);
  const pending = useRef6(false);
  const change = (e) => setValues((v) => ({ ...v, [e.target.name]: e.target.value }));
  async function submit(e) {
    e.preventDefault();
    if (disabled || pending.current) return;
    const payload = projectValues(values);
    if (!payload.customer_name) {
      setError("Customer name is required.");
      return;
    }
    if (new TextEncoder().encode(payload.requirements || "").length > 65535) {
      setError("Requirements are too long. Please shorten them.");
      return;
    }
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await onSubmit(payload);
    } catch (err) {
      setError(projectError(err, "save"));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  }
  return /* @__PURE__ */ jsxs8("form", { onSubmit: submit, className: "customer-project-form", children: [
    error && /* @__PURE__ */ jsx10("div", { className: "account-error", role: "alert", children: error }),
    /* @__PURE__ */ jsxs8("fieldset", { disabled: disabled || busy, children: [
      /* @__PURE__ */ jsx10("div", { className: "account-grid", children: projectFields.map(([key, label, maxLength, type]) => /* @__PURE__ */ jsx10(
        Input,
        {
          id: key,
          name: key,
          label,
          type: type || "text",
          maxLength: maxLength || void 0,
          required: key === "customer_name",
          value: values[key],
          onChange: change
        },
        key
      )) }),
      /* @__PURE__ */ jsxs8("div", { className: "form-field", children: [
        /* @__PURE__ */ jsx10("label", { htmlFor: "requirements", children: "Requirements" }),
        /* @__PURE__ */ jsx10("textarea", { id: "requirements", name: "requirements", value: values.requirements, onChange: change, rows: 6 })
      ] }),
      /* @__PURE__ */ jsx10(Button, { type: "submit", loading: busy, disabled, children: editing ? "Save Changes" : "Create Project" })
    ] })
  ] });
}

// src/components/projects/ProjectUsage.jsx
import { Link as Link3 } from "react-router-dom";
import { jsx as jsx11, jsxs as jsxs9 } from "react/jsx-runtime";
function ProjectUsage({ projects, plan }) {
  const limit = plan?.max_projects;
  return /* @__PURE__ */ jsxs9("section", { className: "account-notice", "aria-label": "Project usage", children: [
    /* @__PURE__ */ jsxs9("strong", { children: [
      plan?.name || "Subscription",
      " \xB7 ",
      projects.length,
      " projects / ",
      limitLabel(limit),
      " limit"
    ] }),
    /* @__PURE__ */ jsxs9("p", { children: [
      projects.filter((p) => p.is_editable).length,
      " editable \xB7 ",
      projects.filter((p) => !p.is_editable).length,
      " read-only"
    ] }),
    Number.isInteger(limit) && projects.length >= limit && /* @__PURE__ */ jsx11("p", { children: "Your project limit has been reached. Existing projects remain available to view." }),
    /* @__PURE__ */ jsx11(Link3, { className: "account-secondary", to: "/owner/subscription", children: "Manage subscription" })
  ] });
}
export {
  LinkedProjectPlan,
  ProjectForm,
  ProjectUsage,
  api_default as api,
  cachedShareUrl,
  createProject,
  createProjectPlan,
  createProjectShareLink,
  deactivateProjectShareLink,
  eligibleProjectPlans,
  generateOwnerImages,
  getOwnerShareLinks,
  getProject,
  getProjectGenerations,
  getProjectPlans,
  getProjectShareLinks,
  getProjects,
  getShareUsage,
  getSharedGallery,
  getSharedImage,
  linkProjectPlan,
  projectError,
  projectValues,
  publishProjectPhase,
  safeShareReturn,
  setShareLinkActive,
  shareLinkStatus,
  shareReturnFromSearch,
  sharingError,
  updateProject
};
