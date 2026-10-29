export const ROLE_LABELS = Object.freeze({ user: "Normal User", owner: "Studio Owner", admin: "Admin" });

export function validateProfile({ name, phone }) {
  const errors = {};
  const trimmed = name.trim();
  if (trimmed.length < 2 || trimmed.length > 100 || /\p{C}/u.test(trimmed)) {
    errors.name = "Enter a name with 2–100 characters, without control characters.";
  }
  const value = phone.trim();
  const digits = value.replace(/[^0-9]/g, "").length;
  if (value && (value.length > 20 || !/^\+?[0-9 ()-]+$/.test(value) || digits < 7 || digits > 15)) {
    errors.phone = "Use 7–15 digits, optionally with +, spaces, parentheses or hyphens.";
  }
  return errors;
}

export function validatePicture(file) {
  if (!file || !["image/jpeg", "image/png"].includes(file.type)) return "Choose a JPEG or PNG image.";
  if (!file.size || file.size > 5 * 1024 * 1024) return "Choose a non-empty image no larger than 5 MiB.";
  return "";
}

export function joinedDate(value) {
  // MySQL's existing timestamp is timezone-naive; display its recorded calendar date.
  const date = value?.match(/^\d{4}-\d{2}-\d{2}/)?.[0];
  return date || "Not available";
}
