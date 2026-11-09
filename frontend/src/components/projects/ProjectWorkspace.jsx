import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import useAuth from '../../hooks/useAuth';
import PlanForm from '../photography/PlanForm';
import { preferenceEntries } from '../photography/PlanCard';
import GeneratedImageCard from '../ai/GeneratedImageCard';
import { getOwnerPhotographyPlans, getOwnerEntitlements, getOwnerGeneratedImage } from '../../services/ownerAiService';
import { createProjectPlan, getProjectPlans, linkProjectPlan, getProjectGenerations, eligibleProjectPlans, projectError } from '../../services/projectService';
import { createProjectShareLink, deactivateProjectShareLink, getProjectShareLinks, getShareUsage, shareLinkStatus } from '../../services/shareService';
import { isOwnerGalleryBatch, OWNER_GENERATION_CONTRACT } from '../../config/ownerGeneration';
import { utcDate, watchSubscriptionRefresh } from '../../utils/subscription';
import '../../styles/ai.css';

export function LinkedProjectPlan({ plan, editable, projectId }) {
  return <details className="project-linked-plan">
    <summary>Open plan #{plan.id} · {plan.photography_type} · {plan.environment}</summary>
    <dl className="account-details">
      <div><dt>People</dt><dd>{plan.people_count}</dd></div>
      <div><dt>Location</dt><dd>{plan.location || 'Not provided'}</dd></div>
      <div><dt>Shoot date/time</dt><dd>{plan.shoot_datetime?.replace('T', ' ') || 'Not scheduled'}</dd></div>
      {preferenceEntries(plan.preferences).map(([key, label, value]) => <div key={key}><dt>{label}</dt><dd className="studio-description">{value}</dd></div>)}
    </dl>
    {editable && <Link className="account-secondary" to={`/owner/ai/generate?project=${projectId}&plan=${plan.id}`}>Generate {OWNER_GENERATION_CONTRACT.batchSize} images / {OWNER_GENERATION_CONTRACT.batchCost} credits</Link>}
  </details>;
}

export default function ProjectWorkspace({ project, onRestriction }) {
  const { user } = useAuth();
  const shareStorageKey = `frameora.photoshoot.share.${user.id}.${project.id}`;
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [revision, setRevision] = useState(0), [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false), [planId, setPlanId] = useState('');
  const [generationId, setGenerationId] = useState(''), [expiresAt, setExpiresAt] = useState('');
  const [createdLinks, setCreatedLinks] = useState(() => { try { return JSON.parse(sessionStorage.getItem(shareStorageKey)) || {}; } catch { return {}; } }), [notice, setNotice] = useState('');
  const [usage, setUsage] = useState(null), [usageError, setUsageError] = useState('');
  const pending = useRef(false);
  useEffect(() => { try { sessionStorage.setItem(shareStorageKey, JSON.stringify(createdLinks)); } catch { /* The URL remains available in this view. */ } }, [createdLinks, shareStorageKey]);
  const refresh = () => setRevision(n => n + 1);
  useEffect(() => {
    const controller = new AbortController();
    setUsageError(''); setUsage(null);
    Promise.all([getProjectPlans(project.id, controller.signal), getOwnerPhotographyPlans(controller.signal),
      getProjectGenerations(project.id, controller.signal), getProjectShareLinks(project.id, controller.signal), getOwnerEntitlements()])
      .then(([plans, allPlans, generations, links, entitlement]) => {
        if (!controller.signal.aborted) setData({ plans, eligible: eligibleProjectPlans(allPlans), generations, links, entitlement });
      }).catch(e => { if (!controller.signal.aborted) { setData(null); setError(projectError(e)); } });
    getShareUsage(controller.signal).then(count => { if (!controller.signal.aborted) setUsage(count); })
      .catch(() => { if (!controller.signal.aborted) setUsageError('Share-link usage is unavailable. Refresh before creating a link.'); });
    return () => controller.abort();
  }, [project.id, revision]);
  useEffect(() => watchSubscriptionRefresh(data?.entitlement.period_end, () => { refresh(); onRestriction(); }), [data?.entitlement.period_end]);
  async function mutate(action) {
    if (pending.current || !project.is_editable) return;
    pending.current = true; setBusy(true); setError(''); setNotice('');
    try { await action(); refresh(); }
    catch (e) { setError(projectError(e, 'save')); if (e.response?.status === 409) { onRestriction(); refresh(); } throw e; }
    finally { pending.current = false; setBusy(false); }
  }
  async function createPlan(values) {
    await mutate(async () => { await createProjectPlan(project.id, values); setShowForm(false); setNotice('Photography plan created and linked.'); });
  }
  async function createShare(event) {
    event.preventDefault();
    if (!complete.some(g => String(g.id) === generationId) || usage == null || usage >= data.entitlement.max_share_links) return;
    await mutate(async () => {
      const links = await getProjectShareLinks(project.id);
      const existing = links.find(link => String(link.generation_id) === generationId && shareLinkStatus(link) === 'Active');
      if (existing) {
        setData(current => ({ ...current, links }));
        setNotice('This image batch already has an active share link. Copy it below, or deactivate it before creating a replacement.');
        return;
      }
      const created = await createProjectShareLink(project.id, { generation_id: Number(generationId), expires_at: expiresAt ? new Date(expiresAt).toISOString() : null });
      setCreatedLinks(previous => ({ ...previous, [created.id]: `${window.location.origin}/sharing/${encodeURIComponent(created.token)}` }));
      setNotice('Share link ready. Copy it below and send it to your customer. They will need to sign in.');
    }).catch(() => {});
  }
  async function copy(url) {
    try { await navigator.clipboard.writeText(url); setNotice('Share URL copied.'); }
    catch { setNotice('Clipboard access is unavailable. Select and copy the URL below.'); }
  }
  const complete = data?.generations.filter(g => g.status === 'completed' && isOwnerGalleryBatch(g.images, OWNER_GENERATION_CONTRACT, g.charged_credits)) || [];
  return <div className="project-workspace">
    <button className="account-secondary" disabled={busy} onClick={refresh}>Refresh plans, images and links</button>
    {error && <div className="account-error" role="alert">{error}</div>}
    {notice && <div className="account-notice" role="status">{notice}</div>}
    {!data && !error && <p role="status">Loading project plans, images and share links…</p>}
    {data && <>
      <section id="gallery" className="account-card ai-page"><h2>Photoshoot Gallery</h2>
        {project.is_editable && data.plans.length > 0 && <p>Generate a batch from the saved plan, then preview and share your images here.</p>}
        {!data.generations.length && <p>No images yet. Your saved photoshoot is ready for generation.</p>}
        {project.is_editable && data.plans.length > 0 && <Link className="owner-gradient-button" to={`/owner/ai/generate?project=${project.id}&plan=${data.plans[0].id}`}>Generate {OWNER_GENERATION_CONTRACT.batchSize} Images</Link>}
        {data.generations.map(g => <div className="ai-generation" key={g.id}><h3>Generation #{g.id} · Plan #{g.plan_id}</h3><p>{g.images.length} images · {g.charged_credits} credits charged</p>
          {complete.some(item => item.id === g.id) ? <div className="ai-image-grid">{g.images.map((image, index) => <GeneratedImageCard key={image.id} image={image} index={index} loadImage={getOwnerGeneratedImage} enablePreview />)}</div>
            : <p>{g.status === 'owner_reserved' ? 'Generation in progress. Check its status in the studio gallery.' : g.status === 'failed' ? 'Generation failed. Check the studio gallery for details.' : 'This image batch is incomplete and cannot be displayed or shared.'}</p>}
          {complete.some(item => item.id === g.id) && <button type="button" className="owner-gradient-button" onClick={() => { setGenerationId(String(g.id)); document.getElementById('share-customer')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}>Share with Customer</button>}
        </div>)}
        <Link className="account-secondary" to="/owner/ai/gallery">Open studio gallery</Link>
      </section>
      <section id="share-customer" className="account-card"><h2>Share with Customer</h2><p>Only completed image batches can be shared. Your customer signs in to view their gallery.</p>
        <p>Subscription usage: {usage ?? 'Unavailable'} / {data.entitlement.max_share_links} active share links across all projects.</p>
        {usageError && <p role="alert">{usageError}</p>}
        {usage != null && usage >= data.entitlement.max_share_links && <p>Your share-link limit has been reached.</p>}
        <Link className="account-secondary" to="/owner/subscription">Manage subscription</Link>
        {project.is_editable && <form onSubmit={createShare}>
          <div className="form-field"><label htmlFor="share-generation">Project image batch</label>
            <select id="share-generation" required value={generationId} disabled={busy} onChange={e => setGenerationId(e.target.value)}>
              <option value="">Choose a completed generation</option>{complete.map(g => <option key={g.id} value={g.id}>Generation #{g.id} · Plan #{g.plan_id}</option>)}
            </select></div>
          <div className="form-field"><label htmlFor="share-expiry">Expiration (optional, local time)</label><div className="input-wrapper"><input id="share-expiry" type="datetime-local" value={expiresAt} disabled={busy} onChange={e => setExpiresAt(e.target.value)} /></div></div>
          <button className="owner-gradient-button" disabled={busy || usage == null || usage >= data.entitlement.max_share_links || !complete.some(g => String(g.id) === generationId) || data.links.some(link => String(link.generation_id) === generationId && shareLinkStatus(link) === 'Active')}>Create Share Link</button>
        </form>}
        {!data.links.length && <p>No share links yet. Choose a completed batch to create one.</p>}
        {data.links.map(link => <article className="project-linked-plan" key={link.id}>
          <h3>Link #{link.id} · Generation #{link.generation_id}</h3>
          <p>{shareLinkStatus(link)} · Expires: {link.expires_at ? utcDate(link.expires_at) : 'Never'}</p>
          {createdLinks[link.id] && shareLinkStatus(link) === 'Active' && <><label htmlFor={`share-url-${link.id}`}>New share URL</label><div className="input-wrapper"><input id={`share-url-${link.id}`} readOnly value={createdLinks[link.id]} onFocus={e => e.target.select()} /></div><button className="owner-gradient-button" onClick={() => copy(createdLinks[link.id])}>Copy Share Link</button></>}
          {!createdLinks[link.id] && shareLinkStatus(link) === 'Active' && <p>This link’s URL is not available in this browser session. Deactivate it to create a replacement.</p>}
          {project.is_editable && link.is_active && <button className="account-secondary" disabled={busy} onClick={() => mutate(async () => { await deactivateProjectShareLink(project.id, link.id); setNotice('Share link deactivated.'); }).catch(() => {})}>Deactivate</button>}
        </article>)}
      </section>
      <details className="account-card"><summary>Photography plans &amp; advanced setup</summary>
        {!data.plans.length && <p>No photography plans linked to this project yet.</p>}
        {data.plans.map(plan => <LinkedProjectPlan key={plan.id} plan={plan} projectId={project.id} editable={project.is_editable} />)}
        {project.is_editable && <>
          <button className="account-secondary" disabled={busy} onClick={() => setShowForm(v => !v)}>{showForm ? 'Cancel new plan' : 'Create project-linked plan'}</button>
          {showForm && <PlanForm onSubmit={createPlan} submitting={busy} />}
          <form onSubmit={event => { event.preventDefault(); if (planId) mutate(async () => { await linkProjectPlan(project.id, Number(planId)); setPlanId(''); setNotice('Photography plan linked.'); }).catch(() => {}); }}>
            <div className="form-field"><label htmlFor="project-existing-plan">Link an existing studio plan</label>
              <select id="project-existing-plan" value={planId} onChange={e => setPlanId(e.target.value)} disabled={busy} required>
                <option value="">Choose an unlinked plan</option>{data.eligible.map(p => <option key={p.id} value={p.id}>#{p.id} · {p.photography_type} · {p.environment}</option>)}
              </select></div>
            {!data.eligible.length && <p>No unlinked studio plans available.</p>}
            <button className="account-secondary" disabled={busy || !data.eligible.some(p => String(p.id) === planId)}>Link Plan</button>
          </form>
        </>}
      </details>
    </>}
  </div>;
}
