import { OWNER_GENERATION_CONTRACT } from '../../config/ownerGeneration';
import Input from '../common/Input';
import OwnerCustomization from '../ai/OwnerCustomization';
import ImageUploader from '../ai/ImageUploader';
import { projectFields, projectValues } from './ProjectForm';
import { normalizeOwnerPreferences, validateOwnerPreferences, DEFAULT_OWNER_PREFERENCES } from '../../config/ownerPreferences';

export const initialPhotoshoot = {
  ...Object.fromEntries([...projectFields.map(([key]) => key), 'requirements'].map(key => [key, ''])),
  photography_type: '', people_count: '1', environment: 'Outdoor', shoot_time: '',
  photography_style: '', lighting_preference: '', equipment_device_type: '', equipment_camera_model: '', equipment_lens: '',
  customization: { ...DEFAULT_OWNER_PREFERENCES },
};
export function photoshootPayloads(values) {
  return {
    project: projectValues(values),
    plan: {
      photography_type: values.photography_type.trim(), people_count: Number(values.people_count), environment: values.environment,
      location: values.shoot_location.trim() || null,
      shoot_datetime: values.shooting_date && values.shoot_time ? `${values.shooting_date}T${values.shoot_time}:00` : null,
      preferences: { photography_style: values.photography_style || null, lighting_preference: values.lighting_preference || null,
        outfit_details: values.customization.outfit_details.trim() || null,
        extra_instructions: values.customization.additional_instructions.trim() || null,
        equipment: { device_type: values.equipment_device_type || null, camera_model: values.equipment_camera_model.trim() || null, lens: values.equipment_lens.trim() || null },
        owner_generation: normalizeOwnerPreferences(values.customization),
      },
    },
  };
}
export function validatePhotoshoot(values) {
  const errors = validateOwnerPreferences(values.customization);
  if (!values.customer_name.trim()) errors.customer_name = 'Enter the customer’s name.';
  if (!values.photography_type.trim()) errors.photography_type = 'Enter a photography type.';
  if (!/^(?:[1-9]|10)$/.test(values.people_count)) errors.people_count = 'Choose 1 to 10 people.';
  if (!['Indoor', 'Outdoor'].includes(values.environment)) errors.environment = 'Choose an environment.';
  for (const [key, , limit] of projectFields) if (limit && values[key].trim().length > limit) errors[key] = `Use ${limit} characters or fewer.`;
  for (const [key, limit] of [['photography_type', 50], ['equipment_camera_model', 100], ['equipment_lens', 100]]) if (values[key].trim().length > limit) errors[key] = `Use ${limit} characters or fewer.`;
  if (new TextEncoder().encode(values.requirements).length > 65535) errors.requirements = 'Please shorten the requirements.';
  if (values.shoot_time && !values.shooting_date) errors.shooting_date = 'Choose a shooting date when setting a time.';
  return errors;
}
export default function PhotoshootForm({ values, onChange, onSubmit, onReference, referenceName, errors, busy, progress, canCreate }) {
  const input = (key, label, maxLength, type = 'text') => <Input key={key} id={`shoot-${key}`} name={key} label={label} maxLength={maxLength || undefined} type={type}
    value={values[key]} onChange={onChange} error={errors[key]} required={['customer_name', 'photography_type'].includes(key)} />;
  const select = (key, label, options) => <div className="form-field" key={key}><label htmlFor={`shoot-${key}`}>{label}</label>
    <select id={`shoot-${key}`} name={key} value={values[key]} onChange={onChange}>{options.map(option => <option value={option} key={option}>{option || 'No preference'}</option>)}</select></div>;
  return <form className="photoshoot-form" onSubmit={onSubmit} noValidate>
    <fieldset className="account-card" disabled={busy || Boolean(progress.projectId) || Boolean(progress.pendingStep)}><legend>1. Customer &amp; event</legend>
      <div className="account-grid">{projectFields.map(([key, label, max, type]) => input(key, key === 'project_title' ? 'Photoshoot title (optional)' : label, max, type))}</div>
      <div className="form-field"><label htmlFor="shoot-requirements">Customer requirements (optional)</label><textarea id="shoot-requirements" name="requirements" value={values.requirements} onChange={onChange} rows={3} /></div>
    </fieldset>
    <fieldset className="account-card" disabled={busy || Boolean(progress.planId) || Boolean(progress.pendingStep)}><legend>2. Photography plan</legend>
      <div className="account-grid">{input('photography_type', 'Photography type', 50)}
        {select('people_count', 'Number of people', Array.from({ length: 10 }, (_, i) => String(i + 1)))}
        {select('environment', 'Environment', ['Indoor', 'Outdoor'])}{input('shoot_time', 'Shoot time (optional)', null, 'time')}
        {select('photography_style', 'Photography style (optional)', ['', 'Cinematic', 'Natural', 'Traditional', 'Creative'])}
        {select('lighting_preference', 'Lighting (optional)', ['', 'Natural Light', 'Golden Hour', 'Studio Light', 'Low Light'])}</div>
      <details><summary>Equipment (optional)</summary><div className="account-grid">
        {select('equipment_device_type', 'Device', ['', 'Smartphone', 'DSLR', 'Mirrorless', 'Other'])}
        {input('equipment_camera_model', 'Camera / device model', 100)}{input('equipment_lens', 'Lens', 100)}</div></details>
    </fieldset>
    <section className="account-card"><h2>3. Image customization</h2><p>Your choices are saved with the photography plan. Generating a complete batch uses {OWNER_GENERATION_CONTRACT.batchCost} credits.</p>
      <OwnerCustomization values={values.customization} errors={errors} disabled={busy || Boolean(progress.planId) || Boolean(progress.pendingStep)} onChange={onChange} />
      <ImageUploader disabled={busy} onChange={onReference} />
      {referenceName && <p>{referenceName} · Reference photos stay in this tab. Reselect after a reload.</p>}
    </section>
    <div className="photoshoot-actions"><button className="owner-gradient-button" name="intent" value="save" disabled={busy || (!progress.projectId && !progress.pendingStep && !canCreate)}>{busy ? 'Saving photoshoot…' : progress.pendingStep ? 'Check Previous Save' : progress.projectId ? 'Continue Saving Photoshoot' : 'Save Photoshoot'}</button>
      <button className="owner-gradient-button" name="intent" value="generate" disabled={busy || (!progress.projectId && !progress.pendingStep && !canCreate)}>Save &amp; Generate {OWNER_GENERATION_CONTRACT.batchSize} Images</button></div>
    <p className="ai-note">Saving is free. You’ll confirm the {OWNER_GENERATION_CONTRACT.batchCost}-credit charge before generation starts.</p>
  </form>;
}
