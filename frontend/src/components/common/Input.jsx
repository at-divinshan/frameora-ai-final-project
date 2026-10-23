
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

export default function Input({
  label,
  id,
  type = "text",
  error,
  icon,
  ...props
}) {
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === "password";

  return (
    <div className="form-field">
      <label htmlFor={id}>{label}</label>

      <div className={`input-wrapper ${error ? "has-error" : ""}`}>
        {icon && <span className="input-icon" aria-hidden="true">{icon}</span>}
        <input
          id={id}
          type={isPassword && showPassword ? "text" : type}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          {...props}
        />

        {isPassword && (
          <button
            type="button"
            className="password-toggle"
            onClick={() => setShowPassword(!showPassword)}
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? <EyeOff size={19} /> : <Eye size={19} />}
          </button>
        )}
      </div>

      {error && (
        <span className="field-error" id={`${id}-error`} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
