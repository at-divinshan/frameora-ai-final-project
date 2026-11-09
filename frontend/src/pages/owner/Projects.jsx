import { Link } from 'react-router-dom';
import AccountLayout from '../../components/layout/AccountLayout';
import ProjectUsage from '../../components/projects/ProjectUsage';
import useCustomerProjects from '../../hooks/useCustomerProjects';

export default function Projects() {
  const { data, error, refresh } = useCustomerProjects();
  const canCreate = data?.projects.length < data?.plan?.max_projects;
  return <AccountLayout><section className="customer-project-page">
    <header className="account-heading"><div><h1>Photoshoots</h1><p>Manage your customers and upcoming shoots.</p></div>
      {canCreate && <Link className="owner-gradient-button" to="/owner/projects/create">Create Photoshoot</Link>}</header>
    {error && <div className="account-error" role="alert">{error}<button className="account-secondary" onClick={refresh}>Retry</button></div>}
    {!data && !error && <p role="status">Loading customer projects…</p>}
    {data && <><ProjectUsage {...data} />
      {data.projects.length === 0 ? <div className="owner-empty-state"><h2>No photoshoots yet</h2><p>Create your first photoshoot, generate images, and share them with your customer.</p></div>
        : <div className="account-grid">{data.projects.map(project => <article className="account-card" key={project.id}>
          <h2>{project.project_title || project.customer_name}</h2><span>{project.is_editable ? 'Editable' : 'Read-only'}</span>
          <dl className="account-details"><div><dt>Customer</dt><dd>{project.customer_name}</dd></div>
            <div><dt>Event type</dt><dd>{project.event_type || 'Not provided'}</dd></div>
            <div><dt>Shooting date</dt><dd>{project.shooting_date || 'Not scheduled'}</dd></div>
            <div><dt>Location</dt><dd>{project.shoot_location || 'Not provided'}</dd></div></dl>
          <Link className="account-secondary" to={`/owner/projects/${project.id}`}>Open Photoshoot</Link>
        </article>)}</div>}</>}
  </section></AccountLayout>;
}
