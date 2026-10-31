import { useEffect, useRef, useState } from 'react';
import Button from './Button';
import { getStudioPhoto, getStudioPhotoStatus, uploadStudioPhoto, removeStudioPhoto } from '../../services/ownerService';
import { ownerError, validateStudioPhoto } from '../../utils/subscription';

export default function StudioPhoto({ editable = false, saved = true, prepareUpload, disabled = false, onStateChange }) {
  const [status, setStatus] = useState(null);
  const [url, setUrl] = useState('');
  const [file, setFile] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const operation = useRef(false);
  function report(nextFile, nextBusy) {
    onStateChange?.({ pending: Boolean(nextFile), busy: nextBusy });
  }
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true, objectUrl;
    setStatus(null); setUrl('');
    getStudioPhotoStatus().then(async value => {
      if (!active) return;
      setStatus(value);
      if (value.has_photo) {
        const blob = await getStudioPhoto();
        if (active) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); }
      }
    }).catch(e => { if (active) setError(ownerError(e, 'Unable to load studio photo.')); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [revision]);
  const [preview, setPreview] = useState('');
  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const value = URL.createObjectURL(file); setPreview(value);
    return () => URL.revokeObjectURL(value);
  }, [file]);
  async function change(remove = false) {
    if (operation.current || disabled || (!remove && !file)) return;
    operation.current = true; report(file, true);
    setBusy(true); setError(''); setNotice('');
    try {
      if (!remove && !saved && prepareUpload && !(await prepareUpload())) return;
      if (remove) await removeStudioPhoto(); else await uploadStudioPhoto(file);
      setFile(null); report(null, true); setNotice(remove ? 'Studio photo removed.' : 'Studio photo saved.'); setRevision(n => n + 1);
    } catch (e) { setError(ownerError(e, 'Unable to update studio photo.')); }
    finally { operation.current = false; setBusy(false); onStateChange?.(state => ({ ...state, busy: false })); }
  }
  return <section className="account-card studio-photo" aria-busy={busy}>
    <h2>Studio photo{editable ? ' (optional)' : ''}</h2>
    {preview || url ? <img className="studio-photo-preview" src={preview || url} alt={preview ? 'Selected studio photo preview' : 'Your studio'} /> : <p>{status ? 'No studio photo.' : 'Loading studio photo…'}</p>}
    {error && <div className="account-error" role="alert">{error}<button type="button" className="account-secondary" onClick={() => { setError(''); setRevision(n => n + 1); }}>Retry</button></div>}
    {notice && <p role="status">{notice}</p>}
    {editable && <>
      <p>JPEG, PNG or WebP · up to 5 MiB · images are stored privately.</p>
      {status && !status.available && <p role="status">Photo uploads will be available after the separate studio-photo migration is approved and applied.</p>}
      {!saved && <p>Uploading will first save the required studio details.</p>}
      <label className="account-upload">Choose studio photo<input type="file" accept="image/jpeg,image/png,image/webp" disabled={(!saved && !prepareUpload) || !status?.available || busy || disabled} onChange={e => {
        const selected = e.target.files?.[0]; if (!selected) return;
        const problem = validateStudioPhoto(selected); setError(problem); setFile(problem ? null : selected); report(problem ? null : selected, false); setNotice(''); e.target.value = '';
      }} /></label>
      <Button loading={busy} disabled={disabled || !file || (!saved && !prepareUpload) || !status?.available} onClick={() => change()}>Upload photo</Button>
      {file && <><p role="status">Selected photo is not saved yet. Upload it or discard the selection before leaving.</p><button className="account-secondary" type="button" disabled={busy || disabled} onClick={() => { setFile(null); report(null, false); setError(''); }}>Discard selection</button></>}
      {status?.has_photo && <button className="account-secondary" type="button" disabled={busy || disabled} onClick={() => change(true)}>Remove photo</button>}
    </>}
  </section>;
}
