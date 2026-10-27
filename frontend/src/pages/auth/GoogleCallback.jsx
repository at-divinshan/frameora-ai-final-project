import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Login from "./Login";
import Button from "../../components/common/Button";
import GoogleRegistrationForm from "../../components/auth/GoogleRegistrationForm";
import useAuth from "../../hooks/useAuth";
import { clearGoogleFlow, completeGoogle, completeGoogleLink, googleErrorMessage, markGoogleRegistration, readGoogleFlow } from "../../services/googleAuthService";
import { dashboardRoute } from "../../utils/constants";

const CALLBACK_ERRORS = {
  "#google-cancelled": "Google sign-in was cancelled. Your account has not been changed.",
  "#google-conflict": "This account cannot be registered or linked. Sign in to your existing account and link Google explicitly.",
  "#google-error": "Google sign-in failed or expired. Please start again.",
};

export default function GoogleCallback() {
  const { user, loading, googleAuthenticate } = useAuth();
  const navigate = useNavigate();
  const [arrival] = useState(() => ({
    error: CALLBACK_ERRORS[window.location.hash] || (window.location.hash || window.location.search ? "Invalid Google return. Please start again." : ""),
  }));
  const [view, setView] = useState("waiting");
  const [error, setError] = useState("");
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);

  useEffect(() => {
    // The backend handles Google's code. Never read tokens/codes from this URL.
    window.history.replaceState(window.history.state, "", window.location.pathname);
    if (loading) return;
    let active = true;
    const flow = readGoogleFlow();
    if (arrival.error) {
      setError(arrival.error);
      setView("error"); clearGoogleFlow(); return;
    }
    if (!flow) { setError("This Google sign-in has expired or was opened in another browser. Please start again."); setView("error"); return; }
    if (flow.mode === "link") { setView("link"); return; }
    if (flow.stage === "registration") { setView("register"); return; }
    googleAuthenticate(completeGoogle, flow.remember).then((result) => {
      if (!active) return;
      if (result.status === "registration_required") {
        markGoogleRegistration(); setView("register");
      } else {
        clearGoogleFlow(); navigate(dashboardRoute(result.role), { replace: true });
      }
    }).catch((failure) => {
      if (active) { setError(googleErrorMessage(failure)); setView("error"); clearGoogleFlow(); }
    });
    return () => { active = false; };
  }, [loading, googleAuthenticate, navigate, arrival]);

  async function link(event) {
    event.preventDefault();
    if (pending.current || !consent) return;
    const flow = readGoogleFlow();
    if (!flow || flow.mode !== "link" || !user || flow.userId !== user.id || user.role === "admin") {
      setError("Sign in again and restart linking from your existing account."); return;
    }
    pending.current = true; setBusy(true); setError("");
    try {
      await completeGoogleLink();
      clearGoogleFlow(); setView("linked");
    } catch (failure) { setError(googleErrorMessage(failure)); setView("error"); clearGoogleFlow(); }
    finally { pending.current = false; setBusy(false); }
  }
  const returnPath = user ? dashboardRoute(user.role) : "/login";
  const flow = readGoogleFlow();
  const canLink = user && user.role !== "admin" && flow?.mode === "link" && flow.userId === user.id;
  return <Login>
    {view === "waiting" && <p role="status">Completing Google sign-in...</p>}
    {view === "register" && <GoogleRegistrationForm />}
    {view === "link" && <>
      <div className="form-heading"><h1>Confirm Google Link</h1><p>Your existing role and account will stay the same.</p></div>
      {canLink ? <form onSubmit={link}>
        <p className="google-account-summary">Link your selected Google account to {user.email}.</p>
        <label className="terms-checkbox"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} required />I confirm that I want to link these accounts.</label>
        <Button type="submit" loading={busy} className="full-width">Confirm Link</Button>
      </form> : <p className="form-alert" role="alert">Your original sign-in session is unavailable. Please sign in and restart linking.</p>}
    </>}
    {view === "linked" && <div className="form-success" role="status">Your Google account is linked. You can now use either sign-in method.</div>}
    {error && <div className="form-alert" role="alert">{error}</div>}
    {view !== "waiting" && <p className="auth-switch"><Link to={returnPath} onClick={clearGoogleFlow}>{user ? "Back to dashboard" : "Back to login"}</Link></p>}
    {(view === "error" || view === "link") && <p className="auth-switch"><Link to="/auth/google/link" onClick={clearGoogleFlow}>Sign in or restart account linking</Link></p>}
  </Login>;
}
