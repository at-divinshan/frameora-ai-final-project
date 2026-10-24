import api from "./api";

export const AUTH_STORAGE_KEY = "frameora.auth";

export function authFieldErrors(failure) {
  const detail = failure.response?.data?.detail;
  if (!Array.isArray(detail)) return {};
  const names = { confirm_password: "confirmPassword", accept_terms: "acceptTerms" };
  const allowed = ["name", "email", "password", "confirmPassword", "acceptTerms", "role"];
  return Object.fromEntries(detail.flatMap((item) => {
    const key = item.loc?.[item.loc.length - 1];
    const field = names[key] || key;
    return allowed.includes(field) && typeof item.msg === "string" ? [[field, item.msg]] : [];
  }));
}

export function clearStoredSession() {
  for (const storage of ["localStorage", "sessionStorage"]) {
    try { window[storage].removeItem(AUTH_STORAGE_KEY); } catch { /* Storage may be disabled. */ }
  }
}

export function readStoredSession() {
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY) || window.sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw);
    if (typeof session.accessToken !== "string" || !Number.isFinite(session.expiresAt) || session.expiresAt <= Date.now()) {
      clearStoredSession();
      return null;
    }
    return session;
  } catch {
    clearStoredSession();
    return null;
  }
}

export function storeSession(data, remember) {
  const session = {
    accessToken: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  };
  clearStoredSession();
  const storage = remember ? window.localStorage : window.sessionStorage;
  storage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  return session;
}

export async function getCurrentUser(signal) {
  const response = await api.get("/auth/me", { signal });
  return response.data;
}

export async function loginUser(data) {
  const response = await api.post("/auth/login", data);
  return response.data;
}

export async function registerUser(data) {
  const response = await api.post("/auth/register", data);
  return response.data;
}

export async function requestPasswordReset(email) {
  const response = await api.post("/auth/forgot-password", {
    email,
  });
  return response.data;
}
