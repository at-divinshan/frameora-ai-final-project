import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Input from "../common/Input";
import Button from "../common/Button";
import { registerUser } from "../../services/authService";
import { validateRegister } from "../../utils/validators";

export default function RegisterForm() {
  const navigate = useNavigate();
  const [values, setValues] = useState({ name: "", email: "", password: "", confirmPassword: "", role: "user", acceptTerms: false });
  const [errors, setErrors] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  function change(event) {
    const { name, value, type, checked } = event.target;
    setValues((current) => ({ ...current, [name]: type === "checkbox" ? checked : value }));
    setErrors((current) => ({ ...current, [name]: "" }));
    setError("");
  }
  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    const nextErrors = validateRegister(values);
    setErrors(nextErrors);
    setError("");
    if (Object.keys(nextErrors).length) return;
    setLoading(true);
    try {
      await registerUser({ name: values.name.trim(), email: values.email.trim(), password: values.password, role: values.role });
      navigate("/login", { replace: true, state: { message: "Account created. Sign in to continue." } });
    } catch (failure) {
      const detail = failure.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to create your account. Please try again.");
    } finally {
      setLoading(false);
    }
  }
  return (
    <>
      <div className="form-heading"><h1>Create Your Account</h1><p>Join Frameora AI</p></div>
      {error && <div className="form-alert" role="alert">{error}</div>}
      <form onSubmit={submit} noValidate>
        <Input id="register-name" name="name" label="Full Name" autoComplete="name" value={values.name} onChange={change} error={errors.name} />
        <Input id="register-email" name="email" label="Email address" type="email" autoComplete="email" placeholder="you@example.com" value={values.email} onChange={change} error={errors.email} />
        <Input id="register-password" name="password" label="Password" type="password" autoComplete="new-password" value={values.password} onChange={change} error={errors.password} />
        <Input id="register-confirm" name="confirmPassword" label="Confirm Password" type="password" autoComplete="new-password" value={values.confirmPassword} onChange={change} error={errors.confirmPassword} />
        <div className="form-field">
          <label htmlFor="register-role">Account type</label>
          <select id="register-role" name="role" value={values.role} onChange={change}><option value="user">User</option><option value="owner">Studio Owner</option></select>
          {errors.role && <span className="field-error" role="alert">{errors.role}</span>}
        </div>
        <label className="terms-checkbox"><input name="acceptTerms" type="checkbox" checked={values.acceptTerms} onChange={change} />I accept the terms and conditions.</label>
        {errors.acceptTerms && <p className="field-error" role="alert">{errors.acceptTerms}</p>}
        <Button type="submit" loading={loading} className="full-width">Register</Button>
      </form>
      <p className="auth-switch">Already have an account? <Link to="/login">Login</Link></p>
    </>
  );
}
