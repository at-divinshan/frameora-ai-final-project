import { useState } from "react";
import { Mail, LockKeyhole, ArrowRight } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import Input from "../common/Input";
import Button from "../common/Button";
import useAuth from "../../hooks/useAuth";
import { dashboardRoute } from "../../utils/constants";
import { authFieldErrors } from "../../services/authService";
import { validateLogin } from "../../utils/validators";

export default function LoginForm() {
  const { login, authError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [values, setValues] = useState({ email: "", password: "" });
  const [remember, setRemember] = useState(false);
  const [errors, setErrors] = useState({});
  const [error, setError] = useState(location.state?.authError || authError || "");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  function change(event) {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: "" }));
    setError("");
    setMessage("");
  }

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    const nextErrors = validateLogin(values);
    setErrors(nextErrors);
    setError("");
    setMessage("");
    if (Object.keys(nextErrors).length) return;
    setLoading(true);
    try {
      const user = await login({ email: values.email.trim(), password: values.password, remember_me: remember });
      navigate(dashboardRoute(user.role), { replace: true });
    } catch (failure) {
      setErrors(authFieldErrors(failure));
      const detail = failure.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to sign in. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <div className="form-heading"><h1>Welcome Back</h1><p>Sign in to continue</p></div>
      {error && <div className="form-alert" role="alert">{error}</div>}
      {message && <div className="form-success" role="status">{message}</div>}
      <form onSubmit={submit} noValidate>
        <Input icon={<Mail size={22} />} id="login-email" name="email" label="Email address" type="email" autoComplete="username" placeholder="you@example.com" value={values.email} onChange={change} error={errors.email} />
        <Input icon={<LockKeyhole size={22} />} id="login-password" name="password" label="Password" type="password" autoComplete="current-password" value={values.password} onChange={change} error={errors.password} />
        <div className="form-options">
          <label className="remember-checkbox"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />Remember me</label>
          <Link to="/forgot-password">Forgot password?</Link>
        </div>
        <Button type="submit" loading={loading} className="full-width">Login <ArrowRight size={20} aria-hidden="true" /></Button>
      </form>
      <div className="auth-divider"><span>OR</span></div>
      <p className="auth-switch">Don't have an account?</p>
      <Link className="gradient-button full-width create-account" to="/register">Create Account</Link>
    </>
  );
}
