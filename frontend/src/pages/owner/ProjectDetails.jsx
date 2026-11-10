import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import AccountLayout from '../../components/layout/AccountLayout';
import ProjectFeedback from '../../components/projects/ProjectFeedback';
import ProjectWorkspace from '../../components/projects/ProjectWorkspace';
import ProjectForm, { projectFields } from '../../components/projects/ProjectForm';
import { getProject, updateProject, projectError } from '../../services/projectService';
import { watchSubscriptionRefresh } from '../../utils/subscription';

export default function ProjectDetails() {
  const { projectId } = useParams();
  const { state } = useLocation();
  const [project, setProject] = useState(null), [error, setError] = useState('');
  const [editing, setEditing] = useState(false), [success, setSuccess] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setProject(null); setError(''); setEditing(false);
    getProject(projectId, controller.signal).then(p => { if (!controller.signal.aborted) setProject(p); })
      .catch(e => { if (!controller.signal.aborted) setError(projectError(e)); });
    return () => controller.abort();
  }, [projectId, revision]);
  useEffect(() => watchSubscriptionRefresh(null, () => {
    // Refresh permissions without replacing a draft being edited.
    getProject(projectId).then(p => setProject(current => current ? { ...current, is_editable: p.is_editable } : current)).catch(() => {});
  }), [projectId]);
  async function save(values) {
    try {
      const saved = await updateProject(projectId, values);
      setProject(saved); setEditing(false); setSuccess('Project updated successfully.');
    } catch (e) {
      if (e.response?.status === 409) {
        setEditing(false); setError(projectError(e, 'save'));
        try { setProject(await getProject(projectId)); } catch { setProject(null); }
      }
      throw e;
    }
  }
  return <AccountLayout><section className="customer-project-page">
    <header className="account-heading"><div><h1>Photoshoot</h1><p>Review and update your customer’s shoot.</p></div><Link className="account-secondary" to="/owner/projects">All Photoshoots</Link></header>
    {state?.photoshootReady && <div className="account-notice" role="status">Your images are ready. Preview the gallery below, then share with your customer.</div>}
    {(success || state?.projectCreated) && <div className="account-notice" role="status">{success || 'Project created successfully.'}</div>}
    {error && <div className="account-error" role="alert">{error}<button className="account-secondary" onClick={() => setRevision(n => n + 1)}>Reload project</button></div>}
    {!project && !error && <p role="status">Loading project…</p>}
    {project && <div className="account-card">
      {!project.is_editable && <div className="account-notice" role="status">This project is read-only under your current plan. You can still view all its details. <Link to="/owner/subscription">Manage subscription</Link></div>}
      {editing && project.is_editable ? <><ProjectForm project={project} editing onSubmit={save} /><button className="account-secondary" onClick={() => setEditing(false)}>Cancel editing</button></>
        : <><h2>{project.project_title || project.customer_name}</h2><dl className="account-details">
          {projectFields.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{project[key] || 'Not provided'}</dd></div>)}
          <div className="account-wide"><dt>Requirements</dt><dd className="studio-description">{project.requirements || 'Not provided'}</dd></div></dl>
          {project.is_editable && <button className="owner-gradient-button" onClick={() => { setEditing(true); setSuccess(''); }}>Edit Details</button>}</>}
    </div>}
    {project && <ProjectWorkspace key={project.id} project={project} onRestriction={() => getProject(projectId).then(setProject).catch(() => setProject(current => current ? { ...current, is_editable: false } : current))} />}
    {project && <ProjectFeedback key={`feedback-${project.id}`} projectId={project.id} />}
  </section></AccountLayout>;
}
