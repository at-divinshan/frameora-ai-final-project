// <define:import.meta.env>
var define_import_meta_env_default = {};

// src/data/exploreSamples.js
var exploreSamples = [
  {
    id: "birthday-01",
    category: "Birthday",
    title: "Lavender Garden Birthday",
    people: 1,
    environment: "Outdoor",
    pose: "Stand at a gentle three-quarter angle, hold a small bouquet at waist level and look back toward the camera.",
    background: "Garden birthday setup with lavender and white balloons, a cake table and warm string lights.",
    camera: "Eye-level waist-up portrait with the decorated table to one side.",
    lighting: "Soft late-afternoon daylight with warm fairy-light accents.",
    style: "Natural",
    lightingPreference: "Golden Hour",
    posePreference: "Natural",
    angle: "Eye Level",
    clothing: "Formal",
    colors: "Lavender",
    outfit: "Lavender puff-sleeve dress and a small white-flower bouquet.",
    instructions: "Keep the balloon arch and cake softly recognizable behind the subject; retain a relaxed smile and gentle garden depth."
  },
  {
    id: "birthday-02",
    category: "Birthday",
    title: "Relaxed Birthday Picnic",
    people: 1,
    environment: "Outdoor",
    pose: "Sit on a picnic blanket with one knee raised, rest a forearm on that knee and look slightly off-camera.",
    background: "Garden picnic with a low wooden cake display, wrapped gifts, purple balloons and a glowing birthday sign.",
    camera: "Eye-level seated portrait, wide enough to include the picnic decorations.",
    lighting: "Warm late-afternoon garden light and soft decorative bulbs.",
    style: "Natural",
    lightingPreference: "Golden Hour",
    posePreference: "Candid",
    angle: "Eye Level",
    clothing: "Casual",
    colors: "White and beige",
    outfit: "Open-collar white shirt, beige trousers and clean white sneakers.",
    instructions: "Keep the seated pose relaxed and include gifts and cake beside the subject without obscuring their hands."
  },
  {
    id: "prewedding-01",
    category: "Pre-wedding",
    title: "Under the Floral Arch",
    people: 2,
    environment: "Outdoor",
    pose: "Stand close together beneath the flowers; one partner gently holds the other at the waist while they turn toward each other.",
    background: "Leafy garden wedding arch with pale flowers and flowing white fabric.",
    camera: "Eye-level medium couple portrait, framing the embrace and bouquet.",
    lighting: "Warm sunlight filtered through garden foliage.",
    style: "Cinematic",
    lightingPreference: "Golden Hour",
    posePreference: "Natural",
    angle: "Eye Level",
    clothing: "Formal",
    colors: "Cream and ivory",
    outfit: "Light cream suit and ivory lace dress with a pale pink-and-white bouquet.",
    instructions: "Keep both faces visible in a natural affectionate glance, and retain the soft floral arch around the couple."
  },
  {
    id: "graduation-01",
    category: "Graduation",
    title: "A Proud Campus Moment",
    people: 1,
    environment: "Outdoor",
    pose: "Stand upright, lightly touch the mortarboard tassel with one hand and hold the rolled diploma in the other.",
    background: "Green campus lawn with leafy trees and a softly blurred building.",
    camera: "Eye-level medium portrait with space above the graduation cap.",
    lighting: "Soft daylight through trees with a warm edge on the hair.",
    style: "Natural",
    lightingPreference: "Natural Light",
    posePreference: "Formal",
    angle: "Eye Level",
    clothing: "Formal",
    colors: "Black and purple",
    outfit: "Black graduation gown and cap with a purple stole, holding a rolled diploma.",
    instructions: "Keep the cap, tassel, stole and diploma clearly visible; use a proud relaxed smile and gentle background blur."
  },
  {
    id: "portrait-01",
    category: "Portrait",
    title: "Warm Lounge Portrait",
    people: 1,
    environment: "Indoor",
    pose: "Recline comfortably in an armchair with one elbow supported and the hand resting loosely near the temple.",
    background: "Dark lounge with a glowing round lamp, shelves and trailing green plants.",
    camera: "Eye-level seated medium portrait at a slight diagonal.",
    lighting: "Warm side lighting with a visible amber practical lamp and soft shadows.",
    style: "Cinematic",
    lightingPreference: "Low Light",
    posePreference: "Natural",
    angle: "Eye Level",
    clothing: "Casual",
    colors: "Black and beige",
    outfit: "Black open-collar shirt, beige trousers and a wristwatch.",
    instructions: "Preserve the relaxed hand position and warm moody atmosphere while keeping the eyes and face clearly lit."
  },
  {
    id: "outdoor-01",
    category: "Outdoor",
    title: "A Walk Through the Garden",
    people: 1,
    environment: "Outdoor",
    pose: "Pause mid-walk, hold a backpack strap with one hand, keep the other hand near the pocket and glance toward the flowers.",
    background: "Tree-lined garden walkway bordered by hedges and bright pink flowers.",
    camera: "Eye-level three-quarter portrait with the path receding behind the subject.",
    lighting: "Soft sun filtered through trees with warm highlights.",
    style: "Natural",
    lightingPreference: "Natural Light",
    posePreference: "Candid",
    angle: "Eye Level",
    clothing: "Casual",
    colors: "Olive, white and beige",
    outfit: "Olive overshirt over a white T-shirt, light beige trousers and a backpack.",
    instructions: "Include the flowering branch near the frame edge and use the walkway as a gentle leading line."
  },
  {
    id: "traditional-01",
    category: "Traditional",
    title: "Maroon and Gold Courtyard",
    people: 1,
    environment: "Outdoor",
    pose: "Stand at a slight angle, raise one hand lightly toward the hair and rest the other near the waist, looking off-camera.",
    background: "Traditional courtyard with carved columns, marigold garlands and a brass lamp.",
    camera: "Eye-level waist-up portrait with the architectural detail at one side.",
    lighting: "Warm natural side light filtered through courtyard foliage.",
    style: "Traditional",
    lightingPreference: "Golden Hour",
    posePreference: "Natural",
    angle: "Eye Level",
    clothing: "Traditional",
    colors: "Maroon and gold",
    outfit: "Maroon sari with ornate gold borders, gold jewelry and white flowers in the hair.",
    instructions: "Keep sari folds, gold border and floral hair decoration detailed without overpowering the face; preserve the courtyard atmosphere."
  },
  {
    id: "fashion-01",
    category: "Fashion",
    title: "Black Denim Street Style",
    people: 1,
    environment: "Outdoor",
    pose: "Lean casually against the wall with hands near the pockets and turn the face slightly toward the light.",
    background: "Pale exterior wall beside dark window frames and leafy plants.",
    camera: "Eye-level three-quarter fashion portrait with a slight diagonal body angle.",
    lighting: "Dappled daylight casting soft leaf shadows on the wall.",
    style: "Natural",
    lightingPreference: "Natural Light",
    posePreference: "Natural",
    angle: "Eye Level",
    clothing: "Streetwear",
    colors: "Black and white",
    outfit: "Black denim jacket over a white T-shirt, dark trousers, sunglasses and a chain necklace.",
    instructions: "Emphasize the relaxed silhouette, jacket texture and clean wall composition; retain natural leaf shadows."
  },
  {
    id: "friends-01",
    category: "Friends",
    title: "Together on the Garden Steps",
    people: 5,
    environment: "Outdoor",
    pose: "Arrange five friends at two heights on low steps, leaning toward each other with relaxed arms and playful smiles.",
    background: "Garden or campus steps surrounded by trees, lawn and a softly blurred building.",
    camera: "Eye-level group portrait with everyone close together and all five faces visible.",
    lighting: "Soft warm daylight under leafy trees.",
    style: "Natural",
    lightingPreference: "Natural Light",
    posePreference: "Candid",
    angle: "Eye Level",
    clothing: "Casual",
    colors: "White, black, blue and muted green",
    outfit: "Coordinated casual shirts and tops with jeans or light trousers; avoid matching uniforms.",
    instructions: "Keep exactly five people in a friendly staggered arrangement. Avoid overlapping faces and preserve individual hands and natural expressions."
  },
  // Missing from the supplied folder: do not invent image-specific metadata.
  { id: "beach-01", category: "Beach", title: "Beach inspiration", available: false, reason: "Original image awaiting restoration and content review." }
].map((sample) => ({ ...sample, image: `/images/explore/${sample.id}.png`, available: sample.available !== false }));
function getExploreSample(id) {
  return exploreSamples.find((s) => s.id === id && s.available) || null;
}

// src/utils/exploreFlow.js
function sessionStore() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}
function validPlanId(value) {
  return /^[1-9]\d*$/.test(String(value || "")) ? String(value) : null;
}
function sceneMode(value) {
  return value === "scene" ? "scene" : "inspiration";
}
function readDraft(storage, key, defaults) {
  try {
    const saved = JSON.parse(storage.getItem(key));
    const values = { ...defaults };
    for (const name of Object.keys(defaults)) if (typeof saved?.values?.[name] === "string" && saved.values[name].length <= 2e3) values[name] = saved.values[name];
    return { values, mode: sceneMode(saved?.mode) };
  } catch {
    return { values: { ...defaults }, mode: "inspiration" };
  }
}
function writeSession(storage, key, value) {
  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
function planContextKey(userId, planId) {
  return `frameora.explore.plan.${userId}.${planId}`;
}
function readPlanContext(storage, userId, planId) {
  if (!validPlanId(planId)) return null;
  try {
    const data = JSON.parse(storage.getItem(planContextKey(userId, planId)));
    return getExploreSample(data?.sampleId) ? { sampleId: data.sampleId, mode: sceneMode(data.mode) } : null;
  } catch {
    return null;
  }
}
async function loadSampleScene(sampleId, signal, fetcher = fetch) {
  const sample = getExploreSample(sampleId);
  if (!sample) throw new Error("This sample image is unavailable.");
  const response = await fetcher(sample.image, { signal, credentials: "same-origin", redirect: "error" });
  if (!response.ok) throw new Error("The sample image could not be loaded. You can still use inspiration only.");
  const blob = await response.blob();
  if (blob.type !== "image/png" || blob.size === 0 || blob.size > 5 * 1024 * 1024) throw new Error("The sample must be a PNG image of at most 5 MiB.");
  return new File([blob], `${sample.id}.png`, { type: "image/png" });
}

// src/pages/user/Explore.jsx
import { useState as useState6 } from "react";
import { Link as Link4 } from "react-router-dom";

// src/components/layout/Navbar.jsx
import { Moon, Search, Sun } from "lucide-react";

// src/components/common/NotificationBell.jsx
import { useState as useState3 } from "react";
import { Bell } from "lucide-react";
import { Link } from "react-router-dom";

// src/hooks/useAuth.js
import { useContext } from "react";

// src/context/AuthContext.jsx
import { createContext, useCallback, useEffect, useRef, useState } from "react";

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

// src/context/AuthContext.jsx
import { jsx } from "react/jsx-runtime";
var AuthContext = createContext(null);

// src/hooks/useUnreadNotifications.js
import { useEffect as useEffect2, useRef as useRef2, useState as useState2 } from "react";

// src/components/common/NotificationBell.jsx
import { jsx as jsx2, jsxs } from "react/jsx-runtime";

// src/context/ThemeContext.jsx
import {
  createContext as createContext2,
  useContext as useContext2,
  useEffect as useEffect3,
  useState as useState4
} from "react";
import { jsx as jsx3 } from "react/jsx-runtime";
var ThemeContext = createContext2(null);

// src/components/layout/Navbar.jsx
import { Link as Link2 } from "react-router-dom";

// src/components/common/AccountAvatar.jsx
import { jsx as jsx4 } from "react/jsx-runtime";

// src/components/layout/Navbar.jsx
import { jsx as jsx5, jsxs as jsxs2 } from "react/jsx-runtime";

// src/components/layout/Sidebar.jsx
import { useState as useState5 } from "react";
import { Link as Link3, NavLink } from "react-router-dom";
import { Camera, Bell as Bell2, ClipboardList, Compass, CreditCard, Heart, House, LogOut, Menu, UserRound, Settings, X } from "lucide-react";

// src/components/common/FrameoraLogo.jsx
import { jsx as jsx6, jsxs as jsxs3 } from "react/jsx-runtime";

// src/components/layout/Sidebar.jsx
import { jsx as jsx7, jsxs as jsxs4 } from "react/jsx-runtime";

// src/components/layout/DashboardLayout.jsx
import { jsx as jsx8, jsxs as jsxs5 } from "react/jsx-runtime";

// src/pages/user/Explore.jsx
import { Fragment, jsx as jsx9, jsxs as jsxs6 } from "react/jsx-runtime";
function ExploreCard({ sample }) {
  const [failed, setFailed] = useState6(false);
  return /* @__PURE__ */ jsxs6("article", { className: "explore-card", children: [
    sample.available && !failed ? /* @__PURE__ */ jsx9("img", { src: sample.image, alt: `${sample.title}: ${sample.pose}`, loading: "lazy", width: "1536", height: "1024", onError: () => setFailed(true) }) : /* @__PURE__ */ jsx9("div", { className: "explore-missing", children: "Sample image unavailable" }),
    /* @__PURE__ */ jsxs6("div", { className: "explore-card-body", children: [
      /* @__PURE__ */ jsx9("span", { className: "explore-category", children: sample.category }),
      /* @__PURE__ */ jsx9("h2", { children: sample.title }),
      sample.available ? /* @__PURE__ */ jsxs6(Fragment, { children: [
        /* @__PURE__ */ jsx9("dl", { children: [["Pose", sample.pose], ["Background", sample.background], ["Camera angle", sample.camera], ["Lighting", sample.lighting]].map(([label, value]) => /* @__PURE__ */ jsxs6("div", { children: [
          /* @__PURE__ */ jsx9("dt", { children: label }),
          /* @__PURE__ */ jsx9("dd", { children: value })
        ] }, label)) }),
        /* @__PURE__ */ jsxs6("details", { children: [
          /* @__PURE__ */ jsx9("summary", { children: "Style & outfit details" }),
          /* @__PURE__ */ jsxs6("p", { children: [
            sample.style,
            " photography \xB7 ",
            sample.outfit
          ] }),
          /* @__PURE__ */ jsx9("p", { children: sample.instructions })
        ] }),
        /* @__PURE__ */ jsx9(Link4, { className: "user-dashboard-create-button", to: `/user/plans/create?sample=${sample.id}`, children: "Try with AI" })
      ] }) : /* @__PURE__ */ jsx9("p", { children: sample.reason })
    ] })
  ] });
}

// src/components/photography/PlanForm.jsx
import { useState as useState8 } from "react";
import { ArrowRight } from "lucide-react";

// src/components/common/Button.jsx
import { jsx as jsx10 } from "react/jsx-runtime";

// src/components/common/Input.jsx
import { useState as useState7 } from "react";
import { Eye, EyeOff } from "lucide-react";
import { jsx as jsx11, jsxs as jsxs7 } from "react/jsx-runtime";

// src/services/planService.js
async function createPlan(values) {
  const { data } = await api_default.post("/plans", values);
  return data;
}

// src/components/photography/PlanForm.jsx
import { jsx as jsx12, jsxs as jsxs8 } from "react/jsx-runtime";
var initialValues = {
  photography_type: "",
  people_count: "1",
  environment: "",
  location: "",
  shoot_datetime: "",
  photography_style: "",
  lighting_preference: "",
  pose_preference: "",
  camera_angle_preference: "",
  outfit_color: "",
  clothing_style: "",
  outfit_details: "",
  extra_instructions: "",
  equipment_device_type: "",
  equipment_camera_model: "",
  equipment_lens: "",
  equipment_additional_equipment: ""
};
var preferenceFields = [
  ["clothing_style", "Clothing Style", ["Casual", "Formal", "Traditional", "Streetwear", "Other"]],
  ["photography_style", "Photography Style", ["Cinematic", "Natural", "Traditional", "Creative"]],
  ["lighting_preference", "Lighting Preference", ["Natural Light", "Golden Hour", "Studio Light", "Low Light"]],
  ["pose_preference", "Pose Preference", ["Natural", "Candid", "Formal", "Creative"]],
  ["camera_angle_preference", "Camera Angle Preference", ["Eye Level", "Low Angle", "High Angle", "Side Angle"]]
];
function buildPlanPreferences(values) {
  const preferences = {};
  for (const [field] of preferenceFields) {
    const value = values[field]?.trim();
    preferences[field] = value || null;
  }
  for (const field of ["outfit_details", "extra_instructions"]) {
    preferences[field] = values[field]?.trim() || null;
  }
  const outfitColor = values.outfit_color?.trim();
  preferences.outfit_color = outfitColor || null;
  preferences.equipment = {
    device_type: values.equipment_device_type || null,
    camera_model: values.equipment_camera_model?.trim() || null,
    lens: values.equipment_lens?.trim() || null,
    additional_equipment: values.equipment_additional_equipment?.trim() || null
  };
  return preferences;
}
function mapPlanToFormValues(plan) {
  let preferences = plan.preferences;
  if (typeof preferences === "string") {
    try {
      preferences = JSON.parse(preferences);
    } catch {
      preferences = null;
    }
  }
  if (!preferences || typeof preferences !== "object" || Array.isArray(preferences)) preferences = {};
  const formValues = { ...initialValues };
  for (const key of ["photography_style", "lighting_preference", "pose_preference", "camera_angle_preference", "outfit_color", "clothing_style", "outfit_details", "extra_instructions"]) {
    formValues[key] = typeof preferences[key] === "string" ? preferences[key] : "";
  }
  const equipment = preferences.equipment && typeof preferences.equipment === "object" && !Array.isArray(preferences.equipment) ? preferences.equipment : {};
  formValues.equipment_device_type = ["Smartphone", "DSLR", "Mirrorless", "Other"].includes(equipment.device_type) ? equipment.device_type : "";
  formValues.equipment_camera_model = typeof equipment.camera_model === "string" ? equipment.camera_model : "";
  formValues.equipment_lens = typeof equipment.lens === "string" ? equipment.lens : "";
  formValues.equipment_additional_equipment = typeof equipment.additional_equipment === "string" ? equipment.additional_equipment : "";
  formValues.photography_type = plan.photography_type || "";
  formValues.people_count = String(plan.people_count || 1);
  formValues.environment = plan.environment || "";
  formValues.location = plan.location || "";
  formValues.shoot_datetime = typeof plan.shoot_datetime === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(plan.shoot_datetime) ? plan.shoot_datetime.slice(0, 16) : "";
  return formValues;
}
function validatePhotographyPlanForm(values) {
  const errors = {};
  const type = values.photography_type.trim();
  const environment = values.environment.trim();
  const location = values.location.trim();
  const cameraModel = values.equipment_camera_model?.trim() || "";
  const lens = values.equipment_lens?.trim() || "";
  const additionalEquipment = values.equipment_additional_equipment?.trim() || "";
  if (!type) errors.photography_type = "Photography type is required.";
  else if (type.length > 50) errors.photography_type = "Use 50 characters or fewer.";
  if (!/^(?:[1-9]|10)$/.test(values.people_count)) errors.people_count = "Choose 1 to 10 people.";
  if (!environment) errors.environment = "Environment is required.";
  else if (environment.length > 20) errors.environment = "Use 20 characters or fewer.";
  if (location.length > 255) errors.location = "Use 255 characters or fewer.";
  if (values.equipment_device_type && !["Smartphone", "DSLR", "Mirrorless", "Other"].includes(values.equipment_device_type)) {
    errors.equipment_device_type = "Choose a supported device type.";
  }
  if (cameraModel.length > 100) errors.equipment_camera_model = "Use 100 characters or fewer.";
  if (lens.length > 100) errors.equipment_lens = "Use 100 characters or fewer.";
  if (additionalEquipment.length > 300) errors.equipment_additional_equipment = "Use 300 characters or fewer.";
  for (const [field, limit] of [["outfit_details", 1e3], ["extra_instructions", 2e3]]) {
    if ((values[field]?.trim().length || 0) > limit) errors[field] = `Use ${limit} characters or fewer.`;
  }
  return errors;
}
export {
  ExploreCard,
  api_default as api,
  buildPlanPreferences,
  createPlan,
  loadSampleScene,
  mapPlanToFormValues,
  planContextKey,
  readDraft,
  readPlanContext,
  sceneMode,
  sessionStore,
  validPlanId,
  validatePhotographyPlanForm,
  writeSession
};
