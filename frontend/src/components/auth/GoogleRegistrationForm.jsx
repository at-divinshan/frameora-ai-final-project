import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Button from "../common/Button";
import Input from "../common/Input";
import useAuth from "../../hooks/useAuth";
import { clearGoogleFlow, googleErrorMessage, readGoogleFlow, registerGoogle } from "../../services/googleAuthService";
import { dashboardRoute } from "../../utils/constants";

export default function GoogleRegistrationForm() {
  const [values, setValues] = useState({ name: "", role: "", accept_terms: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const { googleAuthenticate } = useAuth();
  const navigate = useNavigate();
  function change(event) {
    const { name, value, checked, type } = event.target;
    setValues((previous) => ({ ...previous, [name]: type === "checkbox" ? checked : value }));
    setError("");
  }
  async function submit(event) {
    event.preventDefault();
    if (pending.current) return;
    const flow = readGoogleFlow();
    if (!flow || flow.stage !== "registration") { setError("Registration has expired. Please start again."); return; }
    if (values.name.trim().length < 2 || !["user", "owner"].includes(values.role) || !values.accept_terms) {
      setError("Enter your name, select an account type and accept the terms."); return;
    }
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      const user = await googleAuthenticate(() => registerGoogle({ ...values, name: values.name.trim() }), flow.remember);
      clearGoogleFlow();
      navigate(dashboardRoute(user.role), { replace: true });
    } catch (failure) { setError(googleErrorMessage(failure)); }
    finally { pending.current = false; setBusy(false); }
  }
  return <>
    <div className="form-heading"><h1>Complete Your Account</h1><p>Choose how you’ll use Frameora AI</p></div>
    {error && <div className="form-alert" role="alert">{error}</div>}
    <form onSubmit={submit}>
      <Input id="google-name" name="name" label="Full Name" autoComplete="name" value={values.name} onChange={change} minLength={2} maxLength={100} required />
      <div className="form-field">
        <label htmlFor="google-role">Account type</label>
        <select id="google-role" name="role" value={values.role} onChange={change} required>
          <option value="" disabled>Select account type</option>
          <option value="user">Normal User</option><option value="owner">Studio Owner</option>
        </select>
      </div>
      <label className="terms-checkbox"><input name="accept_terms" type="checkbox" checked={values.accept_terms} onChange={change} required />I accept the terms and conditions.</label>
      <Button type="submit" loading={busy} className="full-width">Create Account</Button>
    </form>
  </>;
}
