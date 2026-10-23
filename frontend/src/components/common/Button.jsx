export default function Button({
  children,
  type = "button",
  loading = false,
  disabled = false,
  className = "",
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`gradient-button ${className}`}
      {...props}
    >
      {loading ? "Please wait..." : children}
    </button>
  );
}