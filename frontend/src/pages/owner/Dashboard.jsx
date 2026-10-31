import { useEffect, useState } from 'react';
import { Link, useLocation, useOutletContext } from 'react-router-dom';
import { ArrowRight, ClipboardList, FolderOpen, Gem, Link2, Plus, Sparkles } from 'lucide-react';
import useAuth from '../../hooks/useAuth';
import AccountLayout from '../../components/layout/AccountLayout';
import StudioPhoto from '../../components/common/StudioPhoto';
import { getPlans, getSubscription } from '../../services/ownerService';
import { ownerError, utcDate, watchSubscriptionRefresh } from '../../utils/subscription';

export function StudioDetails({ studio }) {
  return <section className="account-card"><h2>{studio?.studio_name || 'Studio details unavailable'}</h2>
    {studio && <><dl className="account-details"><div><dt>Studio phone</dt><dd>{studio.studio_phone || 'Not provided'}</dd></div>
      <div><dt>Address</dt><dd>{studio.studio_address || 'Not provided'}{studio.studio_city ? `, ${studio.studio_city}` : ''}</dd></div></dl>
      {studio.studio_description && <p className="studio-description">{studio.studio_description}</p>}</>}
    <Link className="account-secondary" to="/owner/studio-setup">Edit studio profile</Link>
  </section>;
}
export default function Dashboard() {
  const { user } = useAuth();
  const { onboarding } = useOutletContext();
  const { state } = useLocation();
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setData(null); setError('');
    Promise.all([getPlans(), getSubscription()]).then(([plans, status]) => {
      if (active) setData({ status, plan: plans.find(p => p.code === status.plan) });
    }).catch(e => { if (active) setError(ownerError(e, 'Unable to load subscription information.')); });
    return () => { active = false; };
  }, [retry, user?.id]);
  useEffect(() => watchSubscriptionRefresh(data?.status.period_end, () => setRetry(n => n + 1)), [data]);
  const metrics = [
    { label: 'Active Projects', icon: ClipboardList, color: 'cyan', value: 'Unavailable' },
    { label: 'Active Share Links', icon: Link2, color: 'orange', value: 'Unavailable' },
    { label: 'Credits Left', icon: Gem, color: 'pink', value: data?.status.plan ? data.status.remaining_credits : 'Unavailable' },
  ];
  return <AccountLayout>
    <section className="owner-welcome" aria-labelledby="owner-welcome-heading"><div>
      <p className="owner-welcome-eyebrow">Welcome Back,</p><h1 id="owner-welcome-heading">{user?.name}! <span aria-hidden="true">👋</span></h1>
      <p className="owner-welcome-description">{onboarding.studio?.studio_name || 'Your studio'} · Manage your studio and subscription.</p>
    </div><button className="owner-gradient-button owner-new-project" disabled title="Project creation — coming soon"><Plus size={17} />New Project</button></section>
    {state?.planActivated && <div className="account-notice" role="status">Your subscription is ready.</div>}
    <div className="account-grid"><StudioDetails studio={onboarding.studio} /><StudioPhoto /></div>
    <section className="owner-metrics" aria-label="Studio overview">{metrics.map(({ label, icon: Icon, color, value }) => <div className="owner-metric" key={label}><span className={`owner-metric-icon owner-metric-icon-${color}`}><Icon size={22} /></span><div><span className="owner-metric-value">{value}</span><span className="owner-metric-label">{label}</span></div></div>)}</section>
    <section className="account-card"><h2>Subscription</h2>
      {!data && !error && <p role="status">Loading subscription…</p>}
      {error && <div className="account-error" role="alert">{error}<button className="account-secondary" onClick={() => setRetry(n => n + 1)}>Retry</button></div>}
      {data && (data.plan ? <><h3>{data.plan.name}</h3><p>{data.status.remaining_credits} credits remaining</p>
        <p>{data.status.plan === 'trial' ? 'Trial expires' : 'Credit period ends'}: {utcDate(data.status.period_end)}</p>
        <p>Plan limits: {data.plan.max_projects} active/editable projects · {data.plan.max_share_links} active share links.</p>
        <p>Project and share-link usage counts are not available yet.</p></> : <p>No usable subscription was returned. Open Subscription to choose a plan.</p>)}
      <Link className="account-secondary" to="/owner/subscription">Manage subscription</Link>
    </section>
    <section className="owner-projects" aria-labelledby="owner-projects-heading"><div className="owner-section-heading"><h2 id="owner-projects-heading">Recent Customer Projects</h2><button className="owner-view-all" disabled title="Customer projects — coming soon">View All <ArrowRight size={16} /></button></div>
      <div className="owner-empty-state"><FolderOpen size={32} /><p>Customer projects are not available yet.</p><span>Your recent projects will appear here when available.</span></div>
      <p className="owner-data-note"><Sparkles size={14} />Project and share-link features are coming soon.</p></section>
  </AccountLayout>;
}
