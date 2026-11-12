import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getFeedback, updateFeedback, feedbackError } from '../../services/feedbackService';
import { getProjectGenerations } from '../../services/projectService';
import { getOwnerGeneratedImage } from '../../services/ownerAiService';
import GeneratedImageCard from '../ai/GeneratedImageCard';
import '../../styles/image-feedback.css';
export default function ProjectFeedback({ projectId }) {
  const [rows, setRows] = useState(null), [images, setImages] = useState([]), [error, setError] = useState(''), [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setError('');
    Promise.all([getFeedback(projectId, controller.signal), getProjectGenerations(projectId, controller.signal)]).then(([feedback, generations]) => {
      if (!controller.signal.aborted) { setRows(feedback); setImages(generations.filter(g => g.status === 'completed').flatMap(g => g.images || [])); }
    }).catch(e => { if (!controller.signal.aborted) setError(feedbackError(e)); });
    return () => controller.abort();
  }, [projectId, revision]);
  async function save(id, data) {
    setBusy(true); setError(''); setSuccess('');
    try { setRows(await updateFeedback(projectId, id, data)); setSuccess('Feedback updated.'); }
    catch (e) { setError(feedbackError(e)); }
    finally { setBusy(false); }
  }
  const ids = [...new Set((rows || []).map(row => row.asset_id))];
  return <section className="account-card project-feedback"><h2>Customer Feedback</h2>
    <button className="account-secondary" disabled={busy} onClick={() => setRevision(n => n + 1)}>Refresh feedback</button>
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {!rows && !error && <p role="status">Loading feedback…</p>}{rows?.length === 0 && <p>No feedback yet.</p>}
    {ids.map(id => <section className="feedback-image-group" key={id} aria-label={`Feedback for image ${id}`}>
      <GeneratedImageCard image={images.find(image => image.id === id) || { id }} index={id - 1} loadImage={getOwnerGeneratedImage} enablePreview />
      <div>{rows.filter(row => row.asset_id === id).map(row => <article className="image-feedback" id={`feedback-${row.id}`} key={row.id}>
        <strong>{row.author_name}</strong> <time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time>
        <p className="feedback-text">{row.comment}</p>
        <label>Status<select value={row.status} disabled={busy} onChange={e => save(row.id, { status: e.target.value })}>
          <option value="pending">Pending</option><option value="in_progress">In Progress</option><option value="resolved">Resolved</option>
        </select></label>
        <Link className="account-secondary" to={`/owner/ai/generate?project=${projectId}&plan=${row.plan_id}&feedback=${row.id}`}>Create revised images</Link>
        <p className="ai-note">Load this feedback as revision instructions in the generation form. Normal plan limits and credits apply. Return here to link a revision, then share its batch using Share with Customer above.</p>
        <label>Linked revision<select value={row.revised_asset_id || ''} disabled={busy} onChange={e => save(row.id, { revised_asset_id: e.target.value ? Number(e.target.value) : null })}>
          <option value="">No revision linked</option>{images.filter(image => image.id !== id).map(image => <option key={image.id} value={image.id}>Image {image.id}</option>)}
        </select></label>
      </article>)}</div>
    </section>)}
  </section>;
}
