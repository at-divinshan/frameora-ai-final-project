export const OWNER_PREFERENCE_MODES = [
  ['background_mode', 'Background Variation', ['same', 'different', 'custom']],
  ['pose_mode', 'Pose Variation', ['high', 'natural', 'custom']],
  ['camera_angle_mode', 'Camera Angles', ['mixed', 'eye', 'cinematic', 'custom']],
  ['outfit_mode', 'Outfit Variation', ['same', 'different', 'custom']],
];
export const OWNER_PREFERENCE_TEXT = [
  ['dress_colors', 'Dress Colors', 200],
  ['outfit_details', 'Outfit Details', 1000],
  ['additional_instructions', 'Additional Custom Instructions', 2000],
];
export const DEFAULT_OWNER_PREFERENCES = Object.freeze({
  background_mode: 'same', pose_mode: 'natural', camera_angle_mode: 'mixed', outfit_mode: 'same',
  dress_colors: '', outfit_details: '', additional_instructions: '',
});
export function normalizeOwnerPreferences(values = {}) {
  return Object.fromEntries(Object.entries(DEFAULT_OWNER_PREFERENCES).map(([key, fallback]) =>
    [key, typeof values[key] === 'string' ? values[key].trim() : fallback]));
}
export function validateOwnerPreferences(values) {
  const errors = {};
  for (const [key, label, options] of OWNER_PREFERENCE_MODES) {
    if (!options.includes(values[key])) errors[key] = `Choose a supported ${label.toLowerCase()} option.`;
  }
  for (const [key, label, limit] of OWNER_PREFERENCE_TEXT) {
    if (typeof values[key] !== 'string' || Array.from(values[key]).length > limit) errors[key] = `${label} must be ${limit} characters or fewer.`;
  }
  const custom = OWNER_PREFERENCE_MODES.slice(0, 3).filter(([key]) => values[key] === 'custom').map(([, label]) => label.toLowerCase());
  if (custom.length && !values.additional_instructions?.trim()) errors.additional_instructions = `Describe your custom ${custom.join(', ')} in Additional Custom Instructions.`;
  if (values.outfit_mode === 'custom' && !values.outfit_details?.trim()) errors.outfit_details = 'Add Outfit Details when using a custom outfit.';
  return errors;
}
