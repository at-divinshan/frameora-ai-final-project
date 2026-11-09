import { OWNER_GENERATION_CONTRACT } from '../../config/ownerGeneration';
import { OWNER_PREFERENCE_MODES, OWNER_PREFERENCE_TEXT } from '../../config/ownerPreferences';

export default function OwnerCustomization({ values, onChange, errors = {}, disabled = false }) {
  return <fieldset disabled={disabled} className="owner-customization">
    <legend>Customize your {OWNER_GENERATION_CONTRACT.batchSize} images</legend>
    <div className="account-grid">{OWNER_PREFERENCE_MODES.map(([key, label, options]) => <div className="form-field" key={key}>
      <label htmlFor={`owner-${key}`}>{label}</label>
      <select id={`owner-${key}`} name={key} value={values[key]} onChange={onChange} required aria-invalid={Boolean(errors[key])} aria-describedby={errors[key] ? `owner-${key}-error` : undefined}>
        {options.map(value => <option key={value} value={value}>{value === 'eye' ? 'Eye level' : value[0].toUpperCase() + value.slice(1)}</option>)}
      </select>
      {errors[key] && <p id={`owner-${key}-error`} role="alert">{errors[key]}</p>}
    </div>)}</div>
    {OWNER_PREFERENCE_TEXT.map(([key, label, limit]) => {
      const required = key === 'outfit_details' ? values.outfit_mode === 'custom' : key === 'additional_instructions' && ['background_mode', 'pose_mode', 'camera_angle_mode'].some(mode => values[mode] === 'custom');
      return <div className="form-field" key={key}>
        <label htmlFor={`owner-${key}`}>{label} ({required ? 'required for custom selections' : 'optional'})</label>
        <textarea id={`owner-${key}`} name={key} rows={key === 'dress_colors' ? 2 : 3} maxLength={limit} required={Boolean(required)} value={values[key]} onChange={onChange}
          aria-invalid={Boolean(errors[key])} aria-describedby={errors[key] ? `owner-${key}-error` : undefined} />
        {errors[key] && <p id={`owner-${key}-error`} role="alert">{errors[key]}</p>}
      </div>;
    })}
  </fieldset>;
}
