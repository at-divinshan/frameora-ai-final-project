import { useEffect, useRef, useState } from "react";
import { googleErrorMessage, startGoogle } from "../../services/googleAuthService";

export default function GoogleButton({ remember = false, disabled = false, onBusyChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  useEffect(() => {
    const reset = () => { pending.current = false; setBusy(false); onBusyChange?.(false); };
    window.addEventListener("pageshow", reset);
    return () => window.removeEventListener("pageshow", reset);
  }, [onBusyChange]);
  async function start() {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    onBusyChange?.(true);
    setError("");
    try { await startGoogle({ remember }); }
    catch (failure) { setError(googleErrorMessage(failure)); pending.current = false; setBusy(false); onBusyChange?.(false); }
  }
  return (
    <div className="google-auth-action">
      <button type="button" className="google-auth-button full-width" disabled={disabled || busy} onClick={start}>
        {busy ? "Connecting to Google..." : "Continue with Google"}
      </button>
      {error && <div className="form-alert" role="alert">{error}</div>}
    </div>
  );
}
