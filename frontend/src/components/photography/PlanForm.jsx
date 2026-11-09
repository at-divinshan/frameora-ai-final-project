import { useState } from "react";
import { ArrowRight } from "lucide-react";
import Button from "../common/Button";
import Input from "../common/Input";
import { getPlanErrorMessage } from "../../services/planService";

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
  clothing_style: "",
  outfit_details: "",
  extra_instructions: "",
  equipment_device_type: "",
  equipment_camera_model: "",
  equipment_lens: "",
  equipment_additional_equipment: "",
};

const preferenceFields = [
  ["clothing_style", "Clothing Style", ["Casual", "Formal", "Traditional", "Streetwear", "Other"]],
  ["photography_style", "Photography Style", ["Cinematic", "Natural", "Traditional", "Creative"]],
  ["lighting_preference", "Lighting Preference", ["Natural Light", "Golden Hour", "Studio Light", "Low Light"]],
  ["pose_preference", "Pose Preference", ["Natural", "Candid", "Formal", "Creative"]],
  ["camera_angle_preference", "Camera Angle Preference", ["Eye Level", "Low Angle", "High Angle", "Side Angle"]],
];

export function buildPlanPreferences(values) {
  const preferences = {};
  for (const [field] of preferenceFields) {
    const value = values[field]?.trim();
    preferences[field] = value || null;
  }
  for (const field of ["outfit_details", "extra_instructions"]) {
    preferences[field] = values[field]?.trim() || null;
  }
  const outfitColor = values.outfit_color?.trim();
  preferences.outfit_color = outfitColor || null;
  preferences.equipment = {
    device_type: values.equipment_device_type || null,
    camera_model: values.equipment_camera_model?.trim() || null,
    lens: values.equipment_lens?.trim() || null,
    additional_equipment: values.equipment_additional_equipment?.trim() || null,
  };
  return preferences;
}

export function mapPlanToFormValues(plan) {
  let preferences = plan.preferences;
  if (typeof preferences === "string") {
    try { preferences = JSON.parse(preferences); } catch { preferences = null; }
  }
  if (!preferences || typeof preferences !== "object" || Array.isArray(preferences)) preferences = {};
  const formValues = { ...initialValues };
  for (const key of ["photography_style", "lighting_preference", "pose_preference", "camera_angle_preference", "outfit_color", "clothing_style", "outfit_details", "extra_instructions"]) {
    formValues[key] = typeof preferences[key] === "string" ? preferences[key] : "";
  }
  const equipment = preferences.equipment && typeof preferences.equipment === "object" && !Array.isArray(preferences.equipment)
    ? preferences.equipment
    : {};
  formValues.equipment_device_type = ["Smartphone", "DSLR", "Mirrorless", "Other"].includes(equipment.device_type)
    ? equipment.device_type
    : "";
  formValues.equipment_camera_model = typeof equipment.camera_model === "string" ? equipment.camera_model : "";
  formValues.equipment_lens = typeof equipment.lens === "string" ? equipment.lens : "";
  formValues.equipment_additional_equipment = typeof equipment.additional_equipment === "string"
    ? equipment.additional_equipment
    : "";
  formValues.photography_type = plan.photography_type || "";
  formValues.people_count = String(plan.people_count || 1);
  formValues.environment = plan.environment || "";
  formValues.location = plan.location || "";
  formValues.shoot_datetime = typeof plan.shoot_datetime === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(plan.shoot_datetime)
    ? plan.shoot_datetime.slice(0, 16)
    : "";
  return formValues;
}

export function validatePhotographyPlanForm(values) {
  const errors = {};
  const type = values.photography_type.trim();
  const environment = values.environment.trim();
  const location = values.location.trim();
  const cameraModel = values.equipment_camera_model?.trim() || "";
  const lens = values.equipment_lens?.trim() || "";
  const additionalEquipment = values.equipment_additional_equipment?.trim() || "";
  if (!type) errors.photography_type = "Photography type is required.";
  else if (type.length > 50) errors.photography_type = "Use 50 characters or fewer.";
  if (!/^(?:[1-9]|10)$/.test(values.people_count)) errors.people_count = "Choose 1 to 10 people.";
  if (!environment) errors.environment = "Environment is required.";
  else if (environment.length > 20) errors.environment = "Use 20 characters or fewer.";
  if (location.length > 255) errors.location = "Use 255 characters or fewer.";
  if (values.equipment_device_type && !["Smartphone", "DSLR", "Mirrorless", "Other"].includes(values.equipment_device_type)) {
    errors.equipment_device_type = "Choose a supported device type.";
  }
  if (cameraModel.length > 100) errors.equipment_camera_model = "Use 100 characters or fewer.";
  if (lens.length > 100) errors.equipment_lens = "Use 100 characters or fewer.";
  if (additionalEquipment.length > 300) errors.equipment_additional_equipment = "Use 300 characters or fewer.";
  for (const [field, limit] of [["outfit_details", 1000], ["extra_instructions", 2000]]) {
    if ((values[field]?.trim().length || 0) > limit) errors[field] = `Use ${limit} characters or fewer.`;
  }
  return errors;
}

export default function PlanForm({
  onSubmit,
  submitting = false,
  submitError = "",
  initialValues: providedValues,
  submitLabel = "Create Plan",
}) {
  const [values, setValues] = useState(() => ({ ...initialValues, ...providedValues }));
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
      setFormError(getPlanErrorMessage(error));
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
      {[ ["outfit_details", "Outfit Details", 1000, "Describe clothing, colors and accessories…"],
         ["extra_instructions", "Extra Instructions", 2000, "Any additional photography preferences…"] ].map(([name, label, limit, placeholder]) => (
        <div className="form-field" key={name}>
          <label htmlFor={name}>{label} (optional)</label>
          <textarea className="user-plan-textarea" id={name} name={name} rows={3} maxLength={limit}
            value={values[name]} onChange={change} placeholder={placeholder}
            aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? `${name}-error` : undefined} />
          {errors[name] && <span className="field-error" id={`${name}-error`} role="alert">{errors[name]}</span>}
        </div>
      ))}
      <fieldset className="user-plan-equipment">
        <legend>Photography Equipment (Optional)</legend>
        <p>Tell us what you have available. Professional camera equipment is not required.</p>
        <div className="form-field">
          <label htmlFor="equipment_device_type">Device Type (optional)</label>
          <div className={`input-wrapper${errors.equipment_device_type ? " has-error" : ""}`}>
            <select
              className="user-plan-select"
              id="equipment_device_type"
              name="equipment_device_type"
              value={values.equipment_device_type}
              onChange={change}
              aria-invalid={Boolean(errors.equipment_device_type)}
              aria-describedby={errors.equipment_device_type ? "equipment_device_type-error" : undefined}
            >
              <option value="">Select a device type</option>
              {["Smartphone", "DSLR", "Mirrorless", "Other"].map((deviceType) => (
                <option key={deviceType} value={deviceType}>{deviceType}</option>
              ))}
            </select>
          </div>
          {errors.equipment_device_type && <span className="field-error" id="equipment_device_type-error" role="alert">{errors.equipment_device_type}</span>}
        </div>
        <Input
          id="equipment_camera_model"
          name="equipment_camera_model"
          label="Camera / Device Model (optional)"
          value={values.equipment_camera_model}
          onChange={change}
          maxLength={100}
          error={errors.equipment_camera_model}
        />
        <Input
          id="equipment_lens"
          name="equipment_lens"
          label="Lens (optional)"
          value={values.equipment_lens}
          onChange={change}
          maxLength={100}
          error={errors.equipment_lens}
        />
        <Input
          id="equipment_additional_equipment"
          name="equipment_additional_equipment"
          label="Additional Equipment (optional)"
          value={values.equipment_additional_equipment}
          onChange={change}
          maxLength={300}
          error={errors.equipment_additional_equipment}
        />
      </fieldset>
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
        {submitLabel} <ArrowRight size={17} aria-hidden="true" />
      </Button>
    </form>
  );
}