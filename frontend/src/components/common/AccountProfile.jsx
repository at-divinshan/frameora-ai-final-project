import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import useAuth from "../../hooks/useAuth";
import AccountLayout from "../layout/AccountLayout";
import AccountAvatar from "./AccountAvatar";
import Input from "./Input";
import Button from "./Button";
import { updateProfile, uploadProfilePicture, removeProfilePicture, profileError, profileFieldErrors } from "../../services/userService";
import { ROLE_LABELS, joinedDate, validateProfile, validatePicture } from "../../utils/profile";

export default function AccountProfile() {
  const { user, refreshProfile, refreshPicture, pictureLoading, pictureError } = useAuth();
  const [profile, setProfile] = useState(null);
  const [values, setValues] = useState({ name: "", phone: "" });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const locked = useRef(false);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    setError("");
    refreshProfile(controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      setProfile(data); setValues({ name: data.name, phone: data.phone || "" });
    }).catch((err) => { if (!controller.signal.aborted) setError(profileError(err)); });
    return () => { mounted.current = false; controller.abort(); };
  }, [refreshProfile, retry]);

  async function mutate(operation, message, picture = false) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setError(""); setNotice("");
    let saved = false;
    try {
      await operation(); saved = true;
      if (picture) refreshPicture();
      const data = await refreshProfile();
      if (mounted.current) { setProfile(data); setNotice(message); }
    } catch (err) {
      if (mounted.current) {
        setError(saved ? "Your change was saved, but account details could not refresh. Please reload this page." : profileError(err));
        if (!saved) setErrors(profileFieldErrors(err));
      }
    } finally { locked.current = false; if (mounted.current) setBusy(false); }
  }
  function save(event) {
    event.preventDefault();
    const validation = validateProfile(values); setErrors(validation);
    if (!Object.keys(validation).length) mutate(() => updateProfile(values), "Profile saved.");
  }
  function upload(event) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    const invalid = validatePicture(file);
    if (invalid) { setError(invalid); setNotice(""); return; }
    mutate(() => uploadProfilePicture(file), "Profile picture saved.", true);
  }
  return <AccountLayout title="Profile">
    <div className="account-heading"><div><h1>Profile</h1><p>Manage your personal information.</p></div><Link to={`/${user.role}/settings`}>Settings</Link></div>
    {error && <div role="alert" className="account-error">{error}{!profile && <button onClick={() => setRetry(retry + 1)}>Try again</button>}</div>}
    {notice && <p role="status" className="account-notice">{notice}</p>}
    {!profile ? !error && <p role="status">Loading profile…</p> : <div className="account-grid">
      <section className="account-card"><h2>Personal details</h2><form onSubmit={save} noValidate>
        <Input id="profile-name" label="Name" value={values.name} maxLength={100} autoComplete="name" disabled={busy} error={errors.name} onChange={(e) => setValues({ ...values, name: e.target.value })} />
        <Input id="profile-phone" label="Phone (optional)" type="tel" value={values.phone} maxLength={20} autoComplete="tel" disabled={busy} error={errors.phone} onChange={(e) => setValues({ ...values, phone: e.target.value })} />
        <Button type="submit" loading={busy}>Save changes</Button>
      </form></section>
      <section className="account-card"><h2>Profile picture</h2><AccountAvatar className="account-picture" />
        {pictureLoading && <p role="status">Loading picture…</p>}
        {pictureError && <p role="alert">Picture unavailable. <button onClick={refreshPicture}>Retry</button></p>}
        {!profile.profile_image && !pictureLoading && <p>No profile picture yet.</p>}
        <p>JPEG or PNG, up to 5 MiB and 16 megapixels. Images are resized to fit 512 × 512 pixels.</p>
        <label className="account-upload">{profile.profile_image ? "Change picture" : "Upload picture"}<input aria-label="Upload profile picture" type="file" accept="image/jpeg,image/png" disabled={busy} onChange={upload} /></label>
        <button className="account-secondary" disabled={busy || !profile.profile_image} onClick={() => mutate(removeProfilePicture, "Profile picture removed.", true)}>Remove picture</button>
      </section>
      <section className="account-card account-wide"><h2>Account information</h2><p>These account details are read-only.</p><dl className="account-details">
        {[["Email", profile.email], ["Role", ROLE_LABELS[profile.role]], ["Verification", profile.is_verified ? "Verified" : "Not verified"], ["Joined", joinedDate(profile.created_at)], ["Account ID", profile.id], ["Sign-in methods", [profile.has_password && "Password", profile.role !== "admin" && profile.google_linked && "Google"].filter(Boolean).join(" · ") || "Not available"]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl></section>
    </div>}
  </AccountLayout>;
}
