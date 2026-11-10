import { useEffect, useState } from 'react';
import { Link, useLocation, useOutletContext } from 'react-router-dom';
import { ArrowRight, ClipboardList, FolderOpen, Gem, Link2, Plus, Sparkles } from 'lucide-react';
import useAuth from '../../hooks/useAuth';
import AccountLayout from '../../components/layout/AccountLayout';
import { getPlans } from '../../services/ownerService';
import { getOwnerEntitlements } from '../../services/ownerAiService';
import { ownerError, utcDate, watchSubscriptionRefresh } from '../../utils/subscription';
import { ownerBatchContractMatches, OWNER_GENERATION_CONTRACT } from '../../config/ownerGeneration';

export default function Dashboard() {
  const { user } = useAuth();
  const { onboarding } = useOutletContext();
  const { state } = useLocation();
  const [data, setData] = useState(null), [error, setError] = useState(''), [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setData(null); setError('');
    Promise.all([getPlans(), getOwnerEntitlements()]).then(([plans, entitlement]) => {
      if (active) setData({ entitlement, plan: plans.find(p => p.code === entitlement.plan) });
    }).catch(e => { if (active) setError(ownerError(e, 'Unable to load subscription information.')); });
    return () => { active = false; };
  }, [retry, user?.id]);
  useEffect(() => watchSubscriptionRefresh(data?.entitlement.period_end, () => setRetry(n => n + 1)), [data]);
  const metrics = [
    { label: 'Active Projects', icon: ClipboardList, color: 'cyan', value: 'Unavailable' },
    { label: 'Active Share Links', icon: Link2, color: 'orange', value: 'Unavailable' },
    { label: 'Credits Left', icon: Gem, color: 'pink', value: data?.entitlement.status === 'active' ? data.entitlement.remaining_credits : 'Unavailable' },
  ];
  const generationContractMismatch = data && !ownerBatchContractMatches(data.entitlement);
  return <AccountLayout>
    <section className="owner-welcome" aria-labelledby="owner-welcome-heading"><div>
      <p className="owner-welcome-eyebrow">Welcome Back,</p><h1 id="owner-welcome-heading">{user?.name}! <span aria-hidden="true">👋</span></h1>
      <p className="owner-welcome-description">{onboarding.studio?.studio_name || 'Your studio'} · Manage your studio and subscription.</p>
    </div>{generationContractMismatch
      ? <button className="owner-gradient-button owner-new-project" type="button" disabled title="Generation is unavailable until the backend contract is updated">Generation unavailable</button>
      : <Link className="owner-gradient-button owner-new-project" to="/owner/ai/generate"><Plus size={17} />Generate Images</Link>}</section>
    {state?.planActivated && <div className="account-notice" role="status">Your subscription is ready.</div>}
    <section className="owner-metrics" aria-label="Studio overview">{metrics.map(({ label, icon: Icon, color, value }) => <div className="owner-metric" key={label}><span className={`owner-metric-icon owner-metric-icon-${color}`}><Icon size={22} /></span><div><span className="owner-metric-value">{value}</span><span className="owner-metric-label">{label}</span></div></div>)}</section>
    <section className="account-card"><h2>Subscription</h2>
      {!data && !error && <p role="status">Loading subscription…</p>}
      {error && <div className="account-error" role="alert">{error}<button className="account-secondary" onClick={() => setRetry(n => n + 1)}>Retry</button></div>}
      {data && (data.entitlement.status === 'active' ? <><h3>{data.plan?.name || data.entitlement.plan}</h3>
        <p>{data.entitlement.remaining_credits} available credits · each image batch costs {data.entitlement.batch_cost} credits.</p>
        <p>{data.entitlement.plan === 'trial' ? 'Trial expires' : 'Plan or credit period ends'}: {utcDate(data.entitlement.subscription_end || data.entitlement.period_end)}</p>
        <p>Plan limits: {data.entitlement.max_projects} editable projects · {data.entitlement.max_share_links} active share links.</p>
        {data.entitlement.previous_subscription_expired && <p role="status">Your previous plan expired; Free Basic is active. Credits do not carry over.</p>}
        {data.entitlement.reason === 'insufficient_credits' && <p role="status">At least {data.entitlement.batch_cost} credits are needed for another batch.</p>}
        {generationContractMismatch
          ? <p role="status">Image generation is temporarily unavailable while the frontend and backend batch contracts are being aligned.</p>
          : <Link className="account-secondary" to="/owner/ai/generate">Generate {OWNER_GENERATION_CONTRACT.batchSize} images</Link>}
        <Link className="account-secondary" to="/owner/ai/gallery">View studio gallery</Link>
      </> : <><p>{data.entitlement.reason === 'paid_activation_disabled'
        ? 'Paid Pro is not enabled for AI generation yet.'
        : 'No spendable owner plan is available. Open Subscription to review your options.'}</p></>)}
      <Link className="account-secondary" to="/owner/subscription">Manage subscription</Link>
    </section>
    <section className="owner-projects account-card" aria-labelledby="owner-projects-heading"><h2 id="owner-projects-heading">Photoshoots</h2>
      <p>Create a photoshoot, generate {OWNER_GENERATION_CONTRACT.batchSize} images, and share them with your customer.</p>
      <Link className="owner-gradient-button" to="/owner/projects/create">Create Photoshoot</Link>
      <Link className="account-secondary" to="/owner/projects">Open Photoshoots <ArrowRight size={16} /></Link></section>
  </AccountLayout>;
}
