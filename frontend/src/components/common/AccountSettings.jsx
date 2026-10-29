import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import useAuth from "../../hooks/useAuth";
import useTheme from "../../hooks/useTheme";
import AccountLayout from "../layout/AccountLayout";
import Button from "./Button";
import { getPrivacy, updatePrivacy, profileError } from "../../services/userService";

export default function AccountSettings() {
  const { user, refreshProfile } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [profile, setProfile] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const locked = useRef(false);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController(); setError("");
    Promise.all([refreshProfile(controller.signal), getPrivacy(controller.signal)]).then(([account, privacy]) => {
      if (!controller.signal.aborted) { setProfile(account); setPreferences(privacy); }
    }).catch((err) => { if (!controller.signal.aborted) setError(profileError(err)); });
    return () => { mounted.current = false; controller.abort(); };
  }, [refreshProfile, retry]);
  async function save(event) {
    event.preventDefault(); if (locked.current) return;
    locked.current = true; setBusy(true); setError(""); setNotice("");
    try {
      const data = await updatePrivacy(preferences, user.role);
      if (mounted.current) { setPreferences(data); setNotice("Privacy settings saved."); }
    } catch (err) { if (mounted.current) setError(profileError(err)); }
    finally { locked.current = false; if (mounted.current) setBusy(false); }
  }
  return <AccountLayout title="Settings">
    <div className="account-heading"><div><h1>Settings</h1><p>Manage privacy, appearance and account security.</p></div><Link to={`/${user.role}/profile`}>Profile</Link></div>
    {error && <div role="alert" className="account-error">{error}{!preferences && <button onClick={() => setRetry(retry + 1)}>Try again</button>}</div>}
    {notice && <p role="status" className="account-notice">{notice}</p>}
    <div className="account-grid">
      <section className="account-card"><h2>Privacy</h2>{!preferences ? !error && <p role="status">Loading privacy settings…</p> : <form onSubmit={save}>
        {[["profile_visibility", "Profile visibility"], ["photography_plans_default", "Photography plan default"], ["ai_images_default", "AI-generated image default"]].map(([key, label]) => <div className="form-field" key={key}><label htmlFor={key}>{label}</label><select id={key} value={key === "profile_visibility" && user.role === "admin" ? "private" : preferences[key]} disabled={busy || (key === "profile_visibility" && user.role === "admin")} onChange={(e) => setPreferences({ ...preferences, [key]: e.target.value })}><option value="private">Private</option><option value="public">Public</option></select></div>)}
        <p>{user.role === "admin" ? "Admin profiles and pictures always remain private." : "Public profiles expose only your display name and profile picture."}</p>
        <p>Plan and image preferences are defaults for future content features. Saving does not publish existing content or create sharing links.</p>
        <Button type="submit" loading={busy}>Save privacy settings</Button>
      </form>}</section>
      <section className="account-card"><h2>Appearance</h2><p>Current theme: {theme === "dark" ? "Dark" : "Light"}</p><button className="account-secondary" onClick={toggleTheme}>Switch to {theme === "dark" ? "light" : "dark"} mode</button></section>
      <section className="account-card account-wide"><h2>Account security</h2>{!profile ? <p>Account security details are unavailable until your account loads.</p> : <>
        <AccountSecurity profile={profile} />
      </>}</section>
    </div>
  </AccountLayout>;
}

export function AccountSecurity({ profile }) {
  return <>
        {profile.has_password ? <><h3>Password</h3><p>Secure password changes are not available yet. Continue using your existing password to sign in.</p><Button disabled>Change password — unavailable</Button></> : profile.role !== "admin" ? <><h3>Set a password</h3><p>Password setup is not available yet. Once enabled, fresh Google identity verification will be required.</p><Button disabled>Verify with Google and set password — unavailable</Button></> : <p>Password management is not available yet.</p>}
        {profile.role !== "admin" && <div className="account-security-method"><h3>Google account</h3>{profile.google_linked ? <p>Google is connected to your account.</p> : profile.has_password ? <><p>Link explicitly using your current password and consent. Your account role stays the same.</p><Link className="account-secondary" to="/auth/google/link">Link Google account</Link></> : <p>Google linking is unavailable for this account.</p>}</div>}
  </>;
}
