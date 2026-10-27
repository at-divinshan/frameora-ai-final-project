import axios from "axios";

const api = axios.create({
  baseURL:
    import.meta.env.VITE_API_URL || "http://localhost:8000",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

let accessToken = null;
let unauthorizedHandler = null;

export function setAccessToken(token) {
  accessToken = token;
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      error.config?.headers?.Authorization === `Bearer ${accessToken}` &&
      error.config?.url !== "/auth/login" &&
      error.config?.url !== "/auth/google/link/start"
    ) {
      unauthorizedHandler?.();
    }
    return Promise.reject(error);
  }
);

export default api;
