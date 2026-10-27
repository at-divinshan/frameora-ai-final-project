import { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import Login from "./Login";
import LoginForm from "../../components/auth/LoginForm";
import Input from "../../components/common/Input";
import Button from "../../components/common/Button";
import useAuth from "../../hooks/useAuth";
import { googleErrorMessage, startGoogle } from "../../services/googleAuthService";
import { dashboardRoute } from "../../utils/constants";

export default function GoogleLink() {
  const { user, loading } = useAuth();
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  useEffect(() => {
    const reset = () => { pending.current = false; setBusy(false); setPassword(""); };
    window.addEventListener("pageshow", reset);
    return () => window.removeEventListener("pageshow", reset);
  }, []);
  if (loading) return <Login><p role="status">Verifying your session...</p></Login>;
  if (!user) return <Login><p className="form-success">Sign in with your existing password before linking Google.</p><LoginForm redirectTo="/auth/google/link" /></Login>;
  if (user.role === "admin") return <Navigate to={dashboardRoute(user.role)} replace />;
  async function submit(event) {
    event.preventDefault();
    if (pending.current || !consent || !password) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try { await startGoogle({ link: true, password, userId: user.id }); }
    catch (failure) { setError(googleErrorMessage(failure)); pending.current = false; setBusy(false); }
    finally { setPassword(""); }
  }
  return <Login>
    <div className="form-heading"><h1>Link Google Account</h1><p>Keep your existing Frameora account</p></div>
    <p className="google-account-summary">Signed in as {user.email}</p>
    {error && <div className="form-alert" role="alert">{error}</div>}
    <form onSubmit={submit}>
      <Input id="google-link-password" name="password" label="Current password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} maxLength={128} required />
      <label className="terms-checkbox"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} required />I want to link my selected Google account to this Frameora account.</label>
      <Button type="submit" loading={busy} className="full-width">Choose Google Account</Button>
    </form>
    <p className="auth-switch"><Link to={dashboardRoute(user.role)}>Back to dashboard</Link></p>
  </Login>;
}
