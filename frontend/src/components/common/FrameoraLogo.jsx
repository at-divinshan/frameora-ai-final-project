
import useTheme from "../../hooks/useTheme";

export default function FrameoraLogo({ className = "" }) {
  const { theme } = useTheme();

  const wordmark =
    theme === "dark"
      ? "/images/logo/frameora-text-dark.png"
      : "/images/logo/frameora-text-light.png";

  return (
    <div className={`frameora-brand ${className}`}>
      <img
        src="/images/logo/logo-icon.png"
        alt=""
        className="frameora-brand-icon"
      />
      <img
        src={wordmark}
        alt="Frameora"
        className="frameora-brand-text"
      />
    </div>
  );
}
