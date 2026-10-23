import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import FrameoraLogo from "../../components/common/FrameoraLogo";
import Input from "../../components/common/Input";
import Button from "../../components/common/Button";
import { validateEmail } from "../../utils/validators";
import { requestPasswordReset } from "../../services/authService";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();

    const validationError = validateEmail(email);
    setError(validationError);
    setMessage("");

    if (validationError) return;

    setLoading(true);

    try {
      await requestPasswordReset(email.trim());
      setMessage(
        "If this email is registered, password reset instructions will be sent."
      );
    } catch {
      setError("Unable to process your request. Please try again later.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page single-auth-page">
      <section className="auth-form-section">
        <div className="auth-form-container">
          <FrameoraLogo className="mobile-brand always-visible" />

          <div className="form-heading">
            <h1>Forgot password?</h1>
            <p>
              Enter your email address to request a password reset.
            </p>
          </div>

          {message && (
            <div className="form-success" role="status">
              {message}
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate>
            <Input
              id="reset-email"
              label="Email address"
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setError("");
              }}
              error={error}
            />

            <Button type="submit" loading={loading} className="full-width">
              Request Password Reset
            </Button>
          </form>

          <p className="auth-switch">
            <Link to="/login">
              <ArrowLeft size={16} className="inline-icon" />
              Back to login
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}