import { createContext, useCallback, useEffect, useRef, useState } from "react";
import { setAccessToken, setUnauthorizedHandler } from "../services/api";
import {
  AUTH_STORAGE_KEY, clearStoredSession, getCurrentUser, loginUser,
  readStoredSession, storeSession,
} from "../services/authService";
import { clearGoogleFlow } from "../services/googleAuthService";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [authError, setAuthError] = useState("");
  const revision = useRef(0);

  const logout = useCallback((message = "") => {
    revision.current += 1;
    clearStoredSession();
    clearGoogleFlow();
    setAccessToken(null);
    setSession(null);
    setUser(null);
    setAuthError(typeof message === "string" ? message : "");
    setLoading(false);
  }, []);

  useEffect(() => {
    let controller;
    async function restore() {
      controller?.abort();
      controller = new AbortController();
      const currentRevision = ++revision.current;
      const saved = readStoredSession();
      setAccessToken(saved?.accessToken || null);
      setUser(null);
      setSession(null);
      setAuthError("");
      if (!saved) { setLoading(false); return; }
      setLoading(true);
      try {
        const currentUser = await getCurrentUser(controller.signal);
        if (currentRevision !== revision.current) return;
        setUser(currentUser);
        setSession(saved);
      } catch (error) {
        if (currentRevision !== revision.current) return;
        if (error.response?.status === 401) {
          logout("Your session has expired. Please sign in again.");
        } else {
          setAccessToken(null);
          setAuthError("Unable to verify your session. Please try signing in again.");
        }
      } finally {
        if (currentRevision === revision.current) setLoading(false);
      }
    }
    setUnauthorizedHandler(() => logout("Your session has expired. Please sign in again."));
    restore();
    function syncSession(event) {
      if (event.key === AUTH_STORAGE_KEY || event.key === null) restore();
    }
    window.addEventListener("storage", syncSession);
    return () => {
      revision.current += 1;
      controller?.abort();
      setUnauthorizedHandler(null);
      window.removeEventListener("storage", syncSession);
    };
  }, [logout]);

  useEffect(() => {
    if (!session) return;
    const expire = () => logout("Your session has expired. Please sign in again.");
    let timer;
    function scheduleExpiry() {
      const remaining = session.expiresAt - Date.now();
      if (remaining <= 0) { expire(); return; }
      // Browsers limit individual timer delays to a signed 32-bit integer.
      timer = window.setTimeout(scheduleExpiry, Math.min(remaining, 2147483647));
    }
    scheduleExpiry();
    const checkExpiry = () => { if (Date.now() >= session.expiresAt) expire(); };
    window.addEventListener("focus", checkExpiry);
    return () => { window.clearTimeout(timer); window.removeEventListener("focus", checkExpiry); };
  }, [session, logout]);

  async function login(values) {
    const currentRevision = ++revision.current;
    const data = await loginUser(values);
    if (currentRevision !== revision.current) throw new Error("Sign-in was cancelled.");
    const saved = storeSession(data, values.remember_me);
    setAccessToken(saved.accessToken);
    setSession(saved);
    setUser(data.user);
    setAuthError("");
    setLoading(false);
    return data.user;
  }

  const googleAuthenticate = useCallback(async (request, remember = false) => {
    const currentRevision = ++revision.current;
    const data = await request();
    if (currentRevision !== revision.current) throw new Error("Sign-in was cancelled.");
    if (data.status === "registration_required") return data;
    if (!data.user || !["user", "owner"].includes(data.user.role) ||
        typeof data.access_token !== "string" || !data.access_token ||
        !Number.isFinite(data.expires_in) || data.expires_in <= 0) {
      throw new Error("Invalid Google authentication response.");
    }
    const saved = storeSession(data, remember === true);
    setAccessToken(saved.accessToken);
    setSession(saved);
    setUser(data.user);
    setAuthError("");
    setLoading(false);
    return data.user;
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, authError, login, logout, googleAuthenticate }}>
      {children}
    </AuthContext.Provider>
  );
}
