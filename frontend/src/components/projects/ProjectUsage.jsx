import { Link } from 'react-router-dom';
export default function ProjectUsage({ projects, plan }) {
  const limit = plan?.max_projects;
  return <section className="account-notice" aria-label="Project usage">
    <strong>{plan?.name || 'Subscription'} · {projects.length} projects / {limit ?? 'unavailable'} limit</strong>
    <p>{projects.filter(p => p.is_editable).length} editable · {projects.filter(p => !p.is_editable).length} read-only</p>
    {Number.isInteger(limit) && projects.length >= limit && <p>Your project limit has been reached. Existing projects remain available to view.</p>}
    <Link className="account-secondary" to="/owner/subscription">Manage subscription</Link>
  </section>;
}
