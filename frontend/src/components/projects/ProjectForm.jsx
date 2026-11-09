import { useRef, useState } from 'react';
import Input from '../common/Input';
import Button from '../common/Button';
import { projectError } from '../../services/projectService';

export const projectFields = [
  ['project_title', 'Project title', 150],
  ['customer_name', 'Customer name', 100],
  ['customer_contact', 'Customer contact', 100],
  ['event_type', 'Event type', 100],
  ['shooting_date', 'Shooting date', null, 'date'],
  ['shoot_location', 'Location', 255],
];

export function projectValues(values) {
  return Object.fromEntries([...projectFields.map(([key]) => key), 'requirements']
    .map(key => [key, values[key]?.trim() || null]));
}

export default function ProjectForm({ project = {}, onSubmit, disabled = false, editing = false }) {
  const [values, setValues] = useState(() => Object.fromEntries(
    [...projectFields.map(([key]) => key), 'requirements'].map(key => [key, project[key] || ''])));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const change = e => setValues(v => ({ ...v, [e.target.name]: e.target.value }));
  async function submit(e) {
    e.preventDefault();
    if (disabled || pending.current) return;
    const payload = projectValues(values);
    if (!payload.customer_name) { setError('Customer name is required.'); return; }
    if (new TextEncoder().encode(payload.requirements || '').length > 65535) {
      setError('Requirements are too long. Please shorten them.'); return;
    }
    pending.current = true; setBusy(true); setError('');
    try { await onSubmit(payload); }
    catch (err) { setError(projectError(err, 'save')); }
    finally { pending.current = false; setBusy(false); }
  }
  return <form onSubmit={submit} className="customer-project-form">
    {error && <div className="account-error" role="alert">{error}</div>}
    <fieldset disabled={disabled || busy}>
      <div className="account-grid">{projectFields.map(([key, label, maxLength, type]) =>
        <Input key={key} id={key} name={key} label={label} type={type || 'text'} maxLength={maxLength || undefined}
          required={key === 'customer_name'} value={values[key]} onChange={change} />)}</div>
      <div className="form-field"><label htmlFor="requirements">Requirements</label>
        <textarea id="requirements" name="requirements" value={values.requirements} onChange={change} rows={6} /></div>
      <Button type="submit" loading={busy} disabled={disabled}>{editing ? 'Save Changes' : 'Create Project'}</Button>
    </fieldset>
  </form>;
}
