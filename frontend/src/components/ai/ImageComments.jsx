import { useEffect, useRef, useState } from 'react';
import { addComment, getComments, feedbackError } from '../../services/feedbackService';
import '../../styles/image-feedback.css';
export function CommentHistory({ comments }) {
  return comments.map(row => <article key={row.id}><p className="feedback-text">{row.comment}</p><small>{row.status.replace('_', ' ')} · <time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time></small></article>);
}
export default function ImageComments({ token, imageId }) {
  const [comments, setComments] = useState([]), [draft, setDraft] = useState('');
  const [open, setOpen] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [success, setSuccess] = useState('');
  const [revision, setRevision] = useState(0);
  const request = useRef(null), submitting = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    setComments([]); setError('');
    getComments(token, imageId, controller.signal).then(rows => { if (!controller.signal.aborted) setComments(rows); })
      .catch(e => { if (!controller.signal.aborted) setError(feedbackError(e)); });
    return () => controller.abort();
  }, [token, imageId, revision]);
  async function submit(event) {
    event.preventDefault();
    if (submitting.current || !draft.trim()) return;
    submitting.current = true; setBusy(true); setError(''); setSuccess('');
    const comment = draft.trim();
    if (!request.current || request.current.comment !== comment) request.current = { comment, request_key: crypto.randomUUID() };
    try {
      const saved = await addComment(token, imageId, request.current);
      setComments(rows => [...rows.filter(row => row.id !== saved.id), saved]);
      setDraft(''); request.current = null; setOpen(false); setSuccess('Comment sent to the studio.');
    } catch (e) { setError(feedbackError(e)); }
    finally { submitting.current = false; setBusy(false); }
  }
  return <section className="image-feedback" aria-label="Your image comments">
    <h3>Your feedback</h3>
    <CommentHistory comments={comments} />
    {success && <p role="status">{success}</p>}
    {error && <p role="alert">{error} <button type="button" className="account-secondary" onClick={() => setRevision(n => n + 1)}>Reload comments</button></p>}
    {open ? <form onSubmit={submit}><label htmlFor={`comment-${imageId}`}>Request a change</label><textarea id={`comment-${imageId}`} maxLength={2000} required disabled={busy} value={draft} onChange={e => setDraft(e.target.value)} />
      <button className="owner-gradient-button" disabled={busy || !draft.trim()}>{busy ? 'Sending…' : 'Submit Comment'}</button> <button type="button" className="account-secondary" disabled={busy} onClick={() => setOpen(false)}>Cancel</button></form>
      : <button className="account-secondary" onClick={() => { setOpen(true); setSuccess(''); }}>Add Comment</button>}
  </section>;
}
