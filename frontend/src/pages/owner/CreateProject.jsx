import { OWNER_GENERATION_CONTRACT } from '../../config/ownerGeneration';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AccountLayout from '../../components/layout/AccountLayout';
import ImageUploader from '../../components/ai/ImageUploader';
import ProjectUsage from '../../components/projects/ProjectUsage';
import PhotoshootForm, { initialPhotoshoot, photoshootPayloads, validatePhotoshoot } from '../../components/projects/PhotoshootForm';
import useCustomerProjects from '../../hooks/useCustomerProjects';
import useAuth from '../../hooks/useAuth';
import { savePhotoshoot } from '../../services/photoshootService';
import { projectError } from '../../services/projectService';
import OwnerAIGenerator from './AIGenerator';

function readDraft(key) {
  try { const draft = JSON.parse(sessionStorage.getItem(key)); return draft?.values && draft?.progress ? { ...draft, values: { ...initialPhotoshoot, ...draft.values, customization: { ...initialPhotoshoot.customization, ...draft.values.customization } } } : null; } catch { return null; }
}
export default function CreateProject() {
  const { user } = useAuth();
  const key = `frameora.photoshoot.draft.${user.id}`;
  const [draft, setDraft] = useState(() => readDraft(key) || { values: initialPhotoshoot, progress: {} });
  const [reference, setReference] = useState(null), [errors, setErrors] = useState({});
  const [error, setError] = useState(''), [storageError, setStorageError] = useState('');
  const [busy, setBusy] = useState(false), [generating, setGenerating] = useState(false);
  const pending = useRef(false);
  const navigate = useNavigate();
  const { data, error: loadError, refresh } = useCustomerProjects();
  useEffect(() => {
    try { sessionStorage.setItem(key, JSON.stringify(draft)); setStorageError(''); }
    catch { setStorageError('Draft storage is unavailable. Enable browser session storage before saving so your progress can be recovered.'); }
  }, [draft, key]);
  function change(event) {
    const { name, value } = event.target;
    setDraft(current => ({ ...current, values: name in current.values.customization
      ? { ...current.values, customization: { ...current.values.customization, [name]: value } }
      : { ...current.values, [name]: value } }));
    setErrors(current => ({ ...current, [name]: '' }));
  }
  function chooseReference(file) {
    if (file && (file.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type))) {
      setError('Choose a JPEG, PNG or WebP reference photo up to 5 MiB.'); return;
    }
    setReference(file || null);
    setDraft(current => ({ ...current, referenceName: file?.name || null }));
    setError('');
  }
  const needsReference = Boolean(draft.referenceName && !reference);
  async function submit(event) {
    event.preventDefault();
    if (pending.current || storageError) return;
    const intent = event.nativeEvent.submitter?.value;
    if (intent === 'generate' && needsReference) { setError('Reselect your reference photo, or remove it, before generating.'); return; }
    const nextErrors = validatePhotoshoot(draft.values);
    setErrors(nextErrors); setError('');
    if (Object.keys(nextErrors).length) { setError('Check the highlighted fields before saving.'); return; }
    pending.current = true; setBusy(true);
    const payloads = photoshootPayloads(draft.values);
    try {
      const progress = await savePhotoshoot(draft.progress, payloads.project, payloads.plan, next => {
        const updated = { ...draft, progress: next };
        setDraft(updated);
        sessionStorage.setItem(key, JSON.stringify(updated));
      });
      setDraft(current => ({ ...current, progress }));
      if (intent === 'generate') setGenerating(true);
      refresh();
    } catch (e) { setError(e.response ? projectError(e, 'save') : e.message || 'Saving could not be confirmed. Check the previous save before trying again.'); }
    finally { pending.current = false; setBusy(false); }
  }
  const saved = Boolean(draft.progress.planId);
  return <AccountLayout><section className="customer-project-page photoshoot-page">
    <header className="account-heading"><div><h1>{saved ? 'Your Photoshoot' : 'Create Photoshoot'}</h1><p>Customer details, shoot planning and image choices in one place.</p></div><Link className="account-secondary" to="/owner/projects">All Photoshoots</Link></header>
    <ol className="photoshoot-steps" aria-label="Photoshoot workflow"><li>Create Photoshoot</li><li>Generate {OWNER_GENERATION_CONTRACT.batchSize} Images</li><li>Gallery</li><li>Share with Customer</li></ol>
    {storageError && <div className="account-error" role="alert">{storageError}</div>}
    {error && <div className="account-error" role="alert">{error}</div>}
    {Object.values(errors).filter(Boolean).length > 0 && <ul className="account-error" aria-label="Fields to check">{[...new Set(Object.values(errors).filter(Boolean))].map(message => <li key={message}>{message}</li>)}</ul>}
    {draft.progress.projectId && !saved && <div className="account-notice" role="status">Customer and event saved. Continue below to save the linked plan. <Link to={`/owner/projects/${draft.progress.projectId}`}>Open saved project</Link></div>}
    {needsReference && <div className="account-notice" role="status">Reselect {draft.referenceName} before generation; reference photos cannot be restored after a reload. <button type="button" className="account-secondary" onClick={() => chooseReference(null)}>Continue without reference</button></div>}
    {loadError && <div className="account-error" role="alert">{loadError}<button className="account-secondary" onClick={refresh}>Retry usage check</button></div>}
    {!data && !loadError && <p role="status">Checking your project allowance…</p>}
    {data && !saved && <ProjectUsage {...data} />}
    {saved ? generating ? <OwnerAIGenerator photoshoot={{ planId: draft.progress.planId, preferences: draft.values.customization, reference,
      onCompleted: () => navigate(`/owner/projects/${draft.progress.projectId}#gallery`, { replace: true, state: { photoshootReady: true } }) }} />
      : <section className="account-card"><h2>{draft.values.project_title || draft.values.customer_name}</h2><p role="status">Photoshoot saved. Your customer details, linked plan and customization are ready.</p>
        <ImageUploader onChange={chooseReference} />
        {reference && <p>Reference photo ready: {reference.name}</p>}
        <div className="photoshoot-actions"><button className="owner-gradient-button" disabled={needsReference} onClick={() => setGenerating(true)}>Generate {OWNER_GENERATION_CONTRACT.batchSize} Images</button><Link className="account-secondary" to={`/owner/projects/${draft.progress.projectId}#gallery`}>Open Photoshoot &amp; Gallery</Link>
        <button className="account-secondary" onClick={() => { setDraft({ values: initialPhotoshoot, progress: {} }); setReference(null); setErrors({}); setError(''); }}>Create Another Photoshoot</button></div></section>
      : <PhotoshootForm values={draft.values} progress={draft.progress} errors={errors} busy={busy || Boolean(storageError)} onChange={change} onSubmit={submit}
          onReference={chooseReference}
          referenceName={reference?.name || draft.referenceName} canCreate={Boolean(data && data.projects.length < data.plan?.max_projects)} />}
  </section></AccountLayout>;
}
