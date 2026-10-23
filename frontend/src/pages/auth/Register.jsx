import { Moon, Sun } from "lucide-react";
import RegisterForm from "../../components/auth/RegisterForm";
import FrameoraLogo from "../../components/common/FrameoraLogo";
import useTheme from "../../hooks/useTheme";

export default function Register() {
  const { theme, toggleTheme } = useTheme();

  return (
    <main className={`auth-page reference-auth mountain-${theme}`}>
        <button
          type="button"
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle color theme"
        >
          {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
        </button>
      <section className="auth-visual">
        <div className="auth-identity">
          <FrameoraLogo className="auth-brand" />
          <p>AI Photography<br />Planning Platform</p>
          <span className="brand-divider" aria-hidden="true" />
          <p className="brand-tagline">Plan. Create. Inspire<br />with AI.</p>
        </div>
      </section>

      <section className="auth-form-section">


        <div className="auth-form-container">
          <FrameoraLogo className="mobile-brand" />

          <RegisterForm />
        </div>
      </section>
    </main>
  );
}