import api from "./api";

const FLOW_KEY = "frameora.google.flow";
let completion;

// This is navigation metadata only. Authentication remains in backend HttpOnly cookies.
export function readGoogleFlow() {
  try {
    const value = JSON.parse(sessionStorage.getItem(FLOW_KEY));
    if (!value || !["login", "link"].includes(value.mode) || !Number.isFinite(value.expiresAt) || value.expiresAt <= Date.now()) return null;
    return value;
  } catch { return null; }
}

export function clearGoogleFlow() {
  try { sessionStorage.removeItem(FLOW_KEY); } catch { /* No authentication data stored here. */ }
  completion = undefined;
}

function saveFlow(value) {
  sessionStorage.setItem(FLOW_KEY, JSON.stringify(value));
}

export function markGoogleRegistration() {
  const flow = readGoogleFlow();
  if (!flow || flow.mode !== "login") throw new Error("Google flow expired.");
  saveFlow({ ...flow, stage: "registration", expiresAt: Date.now() + 600000 });
}

export function googleErrorMessage(error) {
  switch (error.response?.status) {
    case 401: return "Unable to verify your account. Check your password or sign in again.";
    case 403: return "Google sign-in is not available for this account or browser origin.";
    case 409: return "This account cannot be created or linked. Sign in with your existing account and link Google explicitly.";
    case 422: return "Check your name, account type and required consent, then try again.";
    case 429: return "Too many attempts. Please wait a few minutes before trying again.";
    case 503: return "Google sign-in is currently unavailable. You can still use email and password.";
    default: return "Google sign-in could not be completed or has expired. Please start again.";
  }
}

export async function startGoogle({ remember = false, link = false, password, userId } = {}) {
  clearGoogleFlow();
  // Verify storage before starting a browser-bound transaction. Never store passwords/tokens here.
  const flow = { mode: link ? "link" : "login", remember, userId: link ? userId : undefined, stage: "pending", expiresAt: Date.now() + 300000 };
  saveFlow(flow);
  try {
    const path = link ? "/auth/google/link/start" : "/auth/google/start";
    const body = link ? { password, consent: true } : { remember_me: remember };
    const { data } = await api.post(path, body, { withCredentials: true });
    const url = new URL(data.authorization_url);
    if (url.origin !== "https://accounts.google.com" || url.pathname !== "/o/oauth2/v2/auth" || url.username || url.password) {
      throw new Error("Invalid authorization destination.");
    }
    window.location.assign(url.href);
  } catch (error) {
    clearGoogleFlow();
    throw error;
  }
}

export function completeGoogle() {
  // React StrictMode may subscribe twice. Never repeat a single-use completion POST.
  if (!completion) completion = api.post("/auth/google/complete", {}, { withCredentials: true }).then(({ data }) => data);
  return completion;
}

export async function registerGoogle(values) {
  const { data } = await api.post("/auth/google/register", values, { withCredentials: true });
  return data;
}

export async function completeGoogleLink() {
  const { data } = await api.post("/auth/google/link/complete", { consent: true }, { withCredentials: true });
  if (data.status !== "linked") throw new Error("Linking did not complete.");
  return data;
}
