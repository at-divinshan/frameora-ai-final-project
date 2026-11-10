import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getFeedback, feedbackError } from '../../services/feedbackService';
export function selectRevision(rows, projectId, planId, feedbackId) {
  return rows.find(row => String(row.id) === String(feedbackId) && String(row.project_id) === String(projectId) && String(row.plan_id) === String(planId));
}
export default function RevisionInstructions({ projectId, planId, feedbackId, disabled, onUse }) {
  const [row, setRow] = useState(null), [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController(); setRow(null); setError('');
    if (!/^[1-9]\d*$/.test(String(projectId)) || !/^[1-9]\d*$/.test(String(feedbackId))) { setError('Revision context is unavailable. Return to the project feedback.'); return; }
    getFeedback(projectId, controller.signal).then(rows => {
      if (controller.signal.aborted) return;
      const found = selectRevision(rows, projectId, planId, feedbackId);
      if (found) setRow(found); else setError('Select the original photography plan to use this feedback.');
    }).catch(e => { if (!controller.signal.aborted) setError(feedbackError(e)); });
    return () => controller.abort();
  }, [projectId, planId, feedbackId]);
  return <section className="ai-plan-summary" aria-label="Revision feedback">
    <h2>Revision feedback</h2>
    {error ? <p role="alert">{error}</p> : row ? <><p className="feedback-text">{row.comment}</p><button type="button" className="account-secondary" disabled={disabled} onClick={() => onUse(row.comment)}>Use feedback as instructions</button></> : <p role="status">Loading feedback…</p>}
    <p className="ai-note">Review the instructions before generating. Normal credits apply. Return to the project to link and share the revised image.</p>
    {/^[1-9]\d*$/.test(String(projectId)) && <Link to={`/owner/projects/${projectId}`} className="account-secondary">Return to project feedback</Link>}
  </section>;
}
