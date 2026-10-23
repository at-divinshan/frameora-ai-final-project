const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validateEmail(email) {
  if (!email.trim()) return "Email address is required.";
  if (!EMAIL_PATTERN.test(email.trim())) {
    return "Enter a valid email address.";
  }
  return "";
}

export function validatePassword(password) {
  if (!password) return "Password is required.";
  if (password.length < 8) {
    return "Password must contain at least 8 characters.";
  }
  return "";
}

export function validateLogin(values) {
  const errors = {};

  const emailError = validateEmail(values.email);
  if (emailError) errors.email = emailError;

  if (!values.password) {
    errors.password = "Password is required.";
  }

  return errors;
}

export function validateRegister(values) {
  const errors = {};

  if (!values.name.trim()) {
    errors.name = "Full name is required.";
  } else if (values.name.trim().length < 2) {
    errors.name = "Name must contain at least 2 characters.";
  } else if (values.name.trim().length > 100) {
    errors.name = "Name cannot exceed 100 characters.";
  }

  const emailError = validateEmail(values.email);
  if (emailError) errors.email = emailError;

  const passwordError = validatePassword(values.password);
  if (passwordError) errors.password = passwordError;

  if (!values.confirmPassword) {
    errors.confirmPassword = "Please confirm your password.";
  } else if (values.password !== values.confirmPassword) {
    errors.confirmPassword = "Passwords do not match.";
  }

  if (!["user", "owner"].includes(values.role)) {
    errors.role = "Please select an account type.";
  }

  if (!values.acceptTerms) {
    errors.acceptTerms = "You must accept the terms to continue.";
  }

  return errors;
}