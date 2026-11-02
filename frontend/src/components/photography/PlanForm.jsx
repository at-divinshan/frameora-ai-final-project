import { useState } from "react";
import { ArrowRight } from "lucide-react";
import Button from "../common/Button";
import Input from "../common/Input";

const initialValues = {
  photography_type: "",
  people_count: "1",
  environment: "",
  location: "",
  shoot_datetime: "",
  photography_style: "",
  lighting_preference: "",
  pose_preference: "",
  camera_angle_preference: "",
  outfit_color: "",
};

const preferenceFields = [
  ["photography_style", "Photography Style", ["Cinematic", "Natural", "Traditional", "Creative"]],
  ["lighting_preference", "Lighting Preference", ["Natural Light", "Golden Hour", "Studio Light", "Low Light"]],
  ["pose_preference", "Pose Preference", ["Natural", "Candid", "Formal", "Creative"]],
  ["camera_angle_preference", "Camera Angle Preference", ["Eye Level", "Low Angle", "High Angle", "Side Angle"]],
];

export function buildPlanPreferences(values) {
  const preferences = {};
  for (const [field] of preferenceFields) {
    const value = values[field]?.trim();
    if (value) preferences[field] = value;
  }
  const outfitColor = values.outfit_color?.trim();
  if (outfitColor) preferences.outfit_color = outfitColor;
  return Object.keys(preferences).length ? preferences : null;
}

export function validatePhotographyPlanForm(values) {
  const errors = {};
  const type = values.photography_type.trim();
  const environment = values.environment.trim();
  const location = values.location.trim();
  if (!type) errors.photography_type = "Photography type is required.";
  else if (type.length > 50) errors.photography_type = "Use 50 characters or fewer.";
  if (!/^(?:[1-9]|10)$/.test(values.people_count)) errors.people_count = "Choose 1 to 10 people.";
  if (!environment) errors.environment = "Environment is required.";
  else if (environment.length > 20) errors.environment = "Use 20 characters or fewer.";
  if (location.length > 255) errors.location = "Use 255 characters or fewer.";
  return errors;
}

function errorText(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).filter(Boolean).join(" ");
  return "Unable to create your plan. Please try again.";
}

export default function PlanForm({ onSubmit, submitting = false, submitError = "" }) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");

  function change(event) {
    const { name, value } = event.target;
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: "" }));
    setFormError("");
  }

  async function submit(event) {
    event.preventDefault();
    const nextErrors = validatePhotographyPlanForm(values);
    setErrors(nextErrors);
    setFormError("");
    if (Object.keys(nextErrors).length) return;

    try {
      await onSubmit({
        photography_type: values.photography_type.trim(),
        people_count: Number(values.people_count),
        environment: values.environment.trim(),
        location: values.location.trim() || null,
        shoot_datetime: values.shoot_datetime || null,
        preferences: buildPlanPreferences(values),
      });
    } catch (error) {
      setFormError(errorText(error));
    }
  }

  return (
    <form className="user-plan-form" onSubmit={submit} noValidate>
      {formError && <p className="user-plan-message is-error" role="alert">{formError}</p>}
      {submitError && <p className="user-plan-message is-error" role="alert">{submitError}</p>}
      <Input
        id="photography_type"
        name="photography_type"
        label="Photography Type"
        value={values.photography_type}
        onChange={change}
        maxLength={50}
        required
        error={errors.photography_type}
      />
      <div className="form-field">
        <label htmlFor="people_count">Number of People</label>
        <div className={`input-wrapper${errors.people_count ? " has-error" : ""}`}>
          <select className="user-plan-select" id="people_count" name="people_count" value={values.people_count} onChange={change} required aria-invalid={Boolean(errors.people_count)} aria-describedby={errors.people_count ? "people_count-error" : undefined}>
            {Array.from({ length: 10 }, (_, index) => index + 1).map((count) => (
              <option key={count} value={count}>{count}</option>
            ))}
          </select>
        </div>
        {errors.people_count && <span className="field-error" id="people_count-error" role="alert">{errors.people_count}</span>}
      </div>
      <Input
        id="environment"
        name="environment"
        label="Environment"
        value={values.environment}
        onChange={change}
        maxLength={20}
        required
        error={errors.environment}
      />
      {preferenceFields.map(([name, label, options]) => (
        <div className="form-field" key={name}>
          <label htmlFor={name}>{label} (optional)</label>
          <div className="input-wrapper">
            <select className="user-plan-select" id={name} name={name} value={values[name]} onChange={change}>
              <option value="">Select a preference</option>
              {options.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
          </div>
        </div>
      ))}
      <Input
        id="outfit_color"
        name="outfit_color"
        label="Outfit Color (optional)"
        value={values.outfit_color}
        onChange={change}
        maxLength={50}
      />
      <Input
        id="location"
        name="location"
        label="Location (optional)"
        value={values.location}
        onChange={change}
        maxLength={255}
        error={errors.location}
      />
      <Input
        id="shoot_datetime"
        name="shoot_datetime"
        label="Shoot Date & Time (optional)"
        type="datetime-local"
        value={values.shoot_datetime}
        onChange={change}
      />
      <Button type="submit" className="user-dashboard-create-button" loading={submitting} disabled={submitting}>
        Create Plan <ArrowRight size={17} aria-hidden="true" />
      </Button>
    </form>
  );
}