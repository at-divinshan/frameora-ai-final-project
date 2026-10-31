import StudioPhoto from '../../components/common/StudioPhoto';
import { useContext, useEffect, useRef, useState } from 'react';
import { UNSAFE_NavigationContext, useNavigate, useOutletContext } from 'react-router-dom';
import AccountLayout from '../../components/layout/AccountLayout';
import Input from '../../components/common/Input';
import Button from '../../components/common/Button';
import { saveStudio } from '../../services/ownerService';
import { guardStudioNavigation, studioPhotoNotice, studioSaveDestination, validateStudio } from '../../utils/onboarding';

const fields = [['studio_name', 'Studio name', 150], ['studio_phone', 'Studio phone', 20], ['studio_address', 'Studio address', 255], ['studio_city', 'City', 100], ['studio_description', 'Description (optional)', 2000]];
export async function saveStudioDetails(values, updateOnboarding) {
  const saved = await saveStudio(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, value.trim() || null])));
  updateOnboarding(saved);
  return saved;
}

export default function StudioSetup() {
  const { onboarding, updateOnboarding } = useOutletContext();
  const navigate = useNavigate();
  const { navigator } = useContext(UNSAFE_NavigationContext);
  const [photo, setPhoto] = useState({ busy: false, pending: false });
  const photoRef = useRef(photo);
  const operation = useRef(false);
  const editing = onboarding.onboarding_status === 'completed';
  function photoChanged(next) {
    photoRef.current = typeof next === 'function' ? next(photoRef.current) : next;
    setPhoto(photoRef.current);
  }
  useEffect(() => guardStudioNavigation(navigator, window,
    () => Boolean(studioPhotoNotice(photoRef.current)),
    () => setError(studioPhotoNotice(photoRef.current))), [navigator]);
  const [values, setValues] = useState(Object.fromEntries(fields.map(([key]) => [key, onboarding.studio?.[key] || ''])));
  const [errors, setErrors] = useState({});
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [detailsSaved, setDetailsSaved] = useState(Boolean(onboarding.studio));
  async function prepareUpload() {
    const validation = validateStudio(values); setErrors(validation);
    if (Object.keys(validation).length) { setError('Complete the required studio details before uploading.'); return false; }
    await saveStudioDetails(values, updateOnboarding);
    setDetailsSaved(true); return true;
  }
  async function submit(event) {
    event.preventDefault();
    if (operation.current) return;
    const notice = studioPhotoNotice(photoRef.current);
    if (notice) { setError(notice); return; }
    const validation = validateStudio(values);
    setErrors(validation); setError(''); setSuccess('');
    if (Object.keys(validation).length) return;
    operation.current = true; setSaving(true);
    try {
      const saved = await saveStudioDetails(values, updateOnboarding);
      setSuccess('Studio details saved successfully.');
      navigate(studioSaveDestination(saved.onboarding_status), { replace: true, state: { studioSaved: true } });
    } catch (failure) {
      const detail = failure.response?.data?.detail;
      if (Array.isArray(detail)) setErrors(Object.fromEntries(detail.filter(e => fields.some(([key]) => key === e.loc?.at(-1))).map(e => [e.loc.at(-1), e.msg])));
      setError(typeof detail === 'string' ? detail : 'Unable to save studio details. Please check your entries and try again.');
    } finally { operation.current = false; setSaving(false); }
  }
  return <AccountLayout><header className="account-heading"><div><h1>{editing ? 'Edit your studio' : 'Set up your studio'}</h1><p>{editing ? 'Update your studio details.' : 'Add your studio details to continue to subscription selection.'}</p></div></header>
    {error && <div className="account-error" role="alert">{error}</div>}
    {success && <div className="account-notice" role="status">{success}</div>}
    <form className="account-card" onSubmit={submit} noValidate aria-busy={saving}>
      <div className="account-grid">{fields.filter(([key]) => key !== 'studio_description').map(([key, label, max]) => <Input key={key} id={key} label={label} value={values[key]} maxLength={max} required type={key === 'studio_phone' ? 'tel' : 'text'} disabled={saving || photo.busy} error={errors[key]} onChange={e => { setValues(v => ({ ...v, [key]: e.target.value })); setErrors(current => ({ ...current, [key]: '' })); }} />)}
        <div className="form-field account-wide">
          <label htmlFor="studio_description">Description (optional)</label>
          <textarea id="studio_description" value={values.studio_description} maxLength={2000} disabled={saving || photo.busy} aria-invalid={Boolean(errors.studio_description)} aria-describedby={errors.studio_description ? 'studio_description-error' : undefined} onChange={e => { setValues(v => ({ ...v, studio_description: e.target.value })); setErrors(current => ({ ...current, studio_description: '' })); }} />
          {errors.studio_description && <span className="field-error" id="studio_description-error" role="alert">{errors.studio_description}</span>}
        </div>
      </div>
      {studioPhotoNotice(photo) && <p role="status">{studioPhotoNotice(photo)}</p>}
      <Button type="submit" loading={saving} disabled={photo.busy || photo.pending}>{editing ? 'Save changes' : 'Save and continue'}</Button>
    </form><StudioPhoto editable saved={detailsSaved} prepareUpload={prepareUpload} disabled={saving} onStateChange={photoChanged} /></AccountLayout>;
}
