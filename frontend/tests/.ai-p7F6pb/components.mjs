// <define:import.meta.env>
var define_import_meta_env_default = { VITE_API_URL: "http://localhost:8000" };

// src/components/ai/ImageUploader.jsx
import { useEffect, useRef, useState } from "react";
import { jsx, jsxs } from "react/jsx-runtime";
function ImageUploader({ onChange, disabled, value, id = "reference", background = false }) {
  const input = useRef(null);
  const [localFile, setLocalFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const file = value === void 0 ? localFile : value;
  useEffect(() => {
    if (!file) {
      setPreview(null);
      if (input.current) input.current.value = "";
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function change(next) {
    if (next && (next.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(next.type))) {
      setError("Choose a JPEG, PNG or WebP image of at most 5 MiB.");
      if (input.current) input.current.value = "";
      return;
    }
    setError("");
    setLocalFile(next);
    onChange(next);
  }
  return /* @__PURE__ */ jsxs("div", { className: "form-field", children: [
    /* @__PURE__ */ jsxs("label", { htmlFor: id, children: [
      background ? "Background Reference Image" : "Person Reference Image",
      " (optional)"
    ] }),
    /* @__PURE__ */ jsx("input", { ref: input, id, type: "file", accept: "image/jpeg,image/png,image/webp", disabled, onChange: (event) => change(event.target.files?.[0] || null) }),
    /* @__PURE__ */ jsxs("small", { children: [
      "JPEG, PNG or WebP, up to 5 MiB. ",
      background ? "Guides the scene; exact background reproduction is not guaranteed." : "A clear photo helps guide appearance; exact facial consistency is not guaranteed."
    ] }),
    error && /* @__PURE__ */ jsx("p", { role: "alert", children: error }),
    preview && /* @__PURE__ */ jsx("img", { src: preview, alt: background ? "Background reference preview" : "Person reference preview", style: { display: "block", maxWidth: "100%", width: 240, maxHeight: 160, objectFit: "contain" } }),
    file && /* @__PURE__ */ jsxs("button", { type: "button", className: "account-secondary", disabled, onClick: () => change(null), children: [
      "Remove ",
      background ? "background" : "person",
      " image"
    ] })
  ] });
}

// src/components/ai/GenerationLoader.jsx
import { LoaderCircle } from "lucide-react";
import { jsx as jsx2, jsxs as jsxs2 } from "react/jsx-runtime";
function GenerationLoader({ imageCount = 4, message }) {
  const statusMessage = message ?? (imageCount === 4 ? "This can take several minutes. Your free request is used only when all four images are saved." : `This can take several minutes. The batch is complete only when all ${imageCount} images are saved.`);
  return /* @__PURE__ */ jsxs2("section", { className: "ai-generation-loader", "aria-busy": "true", "aria-label": "Generating images", children: [
    /* @__PURE__ */ jsxs2("div", { className: "ai-loading-status", role: "status", "aria-live": "polite", children: [
      /* @__PURE__ */ jsx2(LoaderCircle, { className: "ai-spinner", size: 24, "aria-hidden": "true" }),
      /* @__PURE__ */ jsxs2("div", { children: [
        /* @__PURE__ */ jsxs2("strong", { children: [
          "Creating ",
          imageCount,
          " photography concepts\u2026"
        ] }),
        /* @__PURE__ */ jsx2("p", { children: statusMessage })
      ] })
    ] }),
    /* @__PURE__ */ jsx2("div", { className: "ai-image-grid", "aria-hidden": "true", children: Array.from({ length: imageCount }, (_, index) => /* @__PURE__ */ jsxs2("div", { className: "ai-image-card ai-skeleton-card", children: [
      /* @__PURE__ */ jsx2("div", { className: "ai-skeleton ai-skeleton-preview" }),
      /* @__PURE__ */ jsxs2("div", { className: "ai-skeleton-copy", children: [
        /* @__PURE__ */ jsx2("div", { className: "ai-skeleton" }),
        /* @__PURE__ */ jsx2("div", { className: "ai-skeleton" })
      ] })
    ] }, index)) })
  ] });
}

// src/components/ai/GeneratedImageCard.jsx
import { useEffect as useEffect2, useRef as useRef2, useState as useState2 } from "react";

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

// src/services/aiService.js
async function getGeneratedImage(id, signal) {
  const { data } = await api_default.get(`/ai/images/${id}`, { responseType: "blob", signal });
  return data;
}

// src/components/ai/GeneratedImageCard.jsx
import { Fragment, jsx as jsx3, jsxs as jsxs3 } from "react/jsx-runtime";
function GeneratedImageCard({ image, index, loadImage = getGeneratedImage, enablePreview = false, allowDownload = true }) {
  const preview = useRef2(null);
  const [url, setUrl] = useState2("");
  const [error, setError] = useState2(false);
  const [attempt, setAttempt] = useState2(0);
  useEffect2(() => {
    const controller = new AbortController();
    let objectUrl;
    setUrl("");
    setError(false);
    loadImage(image.id, controller.signal).then((blob) => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch(() => {
      if (!controller.signal.aborted) setError(true);
    });
    return () => {
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [image.id, attempt, loadImage]);
  const setup = image.guidance?.camera_setup;
  return /* @__PURE__ */ jsxs3("figure", { className: "ai-image-card", children: [
    url ? enablePreview ? /* @__PURE__ */ jsxs3(Fragment, { children: [
      /* @__PURE__ */ jsxs3("button", { className: "owner-image-preview", type: "button", onClick: () => preview.current?.showModal(), "aria-label": `Preview image ${index + 1}`, children: [
        /* @__PURE__ */ jsx3("img", { src: url, alt: `Generated photography concept ${index + 1}` }),
        /* @__PURE__ */ jsx3("span", { children: "Preview image" })
      ] }),
      /* @__PURE__ */ jsxs3("dialog", { ref: preview, className: "owner-image-dialog", "aria-label": `Image ${index + 1} preview`, onClick: (event) => {
        if (event.target === event.currentTarget) preview.current.close();
      }, children: [
        /* @__PURE__ */ jsx3("button", { autoFocus: true, className: "account-secondary", type: "button", onClick: () => preview.current.close(), children: "Close preview" }),
        /* @__PURE__ */ jsx3("img", { src: url, alt: `Generated photography concept ${index + 1}` })
      ] })
    ] }) : /* @__PURE__ */ jsx3("img", { src: url, alt: `Generated photography concept ${index + 1}` }) : error ? /* @__PURE__ */ jsxs3("p", { role: "alert", children: [
      "Image could not load. ",
      /* @__PURE__ */ jsx3("button", { type: "button", onClick: () => setAttempt(attempt + 1), children: "Retry" })
    ] }) : /* @__PURE__ */ jsx3("p", { role: "status", children: "Loading image\u2026" }),
    /* @__PURE__ */ jsxs3("figcaption", { children: [
      /* @__PURE__ */ jsx3("div", { className: "ai-image-heading", children: /* @__PURE__ */ jsx3("h3", { children: image.guidance?.pose_name || `Image ${index + 1}` }) }),
      image.guidance ? /* @__PURE__ */ jsxs3(Fragment, { children: [
        /* @__PURE__ */ jsxs3("dl", { className: "user-plan-preference-list", children: [
          /* @__PURE__ */ jsxs3("div", { children: [
            /* @__PURE__ */ jsx3("dt", { children: "Camera angle" }),
            /* @__PURE__ */ jsx3("dd", { children: image.guidance.camera_angle })
          ] }),
          setup && /* @__PURE__ */ jsxs3("div", { children: [
            /* @__PURE__ */ jsx3("dt", { children: "Camera distance" }),
            /* @__PURE__ */ jsx3("dd", { children: setup.camera_distance })
          ] }),
          /* @__PURE__ */ jsxs3("div", { children: [
            /* @__PURE__ */ jsx3("dt", { children: "Shot type" }),
            /* @__PURE__ */ jsx3("dd", { children: image.guidance.shot_type })
          ] }),
          /* @__PURE__ */ jsxs3("div", { children: [
            /* @__PURE__ */ jsx3("dt", { children: "Camera position" }),
            /* @__PURE__ */ jsx3("dd", { children: image.guidance.camera_position })
          ] })
        ] }),
        setup ? /* @__PURE__ */ jsxs3("details", { className: "ai-camera-guide", children: [
          /* @__PURE__ */ jsxs3("summary", { children: [
            "Camera Setup Guide ",
            /* @__PURE__ */ jsxs3("span", { children: [
              setup.steps.length,
              " practical steps"
            ] })
          ] }),
          /* @__PURE__ */ jsx3("dl", { className: "user-plan-preference-list", children: [
            ["Camera height", setup.camera_height],
            ["Camera direction and tilt", setup.camera_direction_and_tilt],
            ["Suggested lens or smartphone zoom", setup.suggested_lens_or_zoom],
            ["Lighting direction", setup.lighting_direction],
            ["Subject position", setup.subject_position]
          ].map(([label, value]) => /* @__PURE__ */ jsxs3("div", { children: [
            /* @__PURE__ */ jsx3("dt", { children: label }),
            /* @__PURE__ */ jsx3("dd", { children: value })
          ] }, label)) }),
          /* @__PURE__ */ jsx3("ol", { children: setup.steps.map((step, stepIndex) => /* @__PURE__ */ jsx3("li", { children: step }, stepIndex)) })
        ] }) : /* @__PURE__ */ jsxs3(Fragment, { children: [
          /* @__PURE__ */ jsx3("p", { children: image.guidance.instructions }),
          /* @__PURE__ */ jsx3("p", { className: "ai-note", children: "A detailed camera setup guide was not saved for this older image." })
        ] }),
        /* @__PURE__ */ jsx3("p", { className: "ai-note", children: "Planned photography guidance used for generation. The image has not been visually verified." })
      ] }) : /* @__PURE__ */ jsx3("p", { className: "ai-note", children: "Photography guidance was not saved for this older image." }),
      url && allowDownload && /* @__PURE__ */ jsx3("a", { className: "user-dashboard-create-button ai-download", href: url, download: `frameora-${image.id}.png`, children: "Download Image" })
    ] })
  ] });
}
export {
  GeneratedImageCard as Card,
  GenerationLoader as Loader,
  ImageUploader as Uploader
};
