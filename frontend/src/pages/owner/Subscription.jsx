import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import AccountLayout from '../../components/layout/AccountLayout';
import Button from '../../components/common/Button';
import { getPlans, getSubscription, activatePlan, getOnboarding } from '../../services/ownerService';
import { activationDisabled, activationConfirmed, ownerError, utcDate } from '../../utils/subscription';

export function PlanCards({ plans, status, busy, activate }) {
  return <div className="studio-plan-grid">{plans.map(plan => <section className={`account-card studio-plan studio-plan-${plan.code}`} key={plan.code}>
    <h2>{plan.name}</h2>{status.plan === plan.code && <span className="studio-plan-badge">Current plan</span>}
    <p className="studio-plan-price">{plan.currency} {Number(plan.price).toLocaleString()}{plan.code === 'pro' ? '/month' : ''}</p>
    <ul><li>{plan.credits} credits {plan.credit_period === 'trial_total' ? 'total' : 'per month'}</li>
      <li>{plan.max_projects} active/editable projects</li><li>{plan.max_share_links} active share links</li>
      <li>{plan.trial_days ? `${plan.trial_days} days · one trial per Studio Owner lifetime` : plan.code === 'basic' ? 'Free ongoing' : 'Monthly subscription'}</li>
      <li>{plan.code === 'trial' ? 'Trial credits expire at the end of the trial.' : 'Credits renew on your plan anniversary, with no carryover.'}</li></ul>
    {plan.code === 'pro' && <p>Payment and activation are unavailable until verified payment integration is ready.</p>}
    {plan.code === 'trial' && !status.trial_available && <p>Your lifetime trial has already been used.</p>}
    <Button disabled={Boolean(busy) || activationDisabled(plan, status)} loading={busy === plan.code} onClick={() => activate(plan.code)}>
      {plan.code === 'pro' ? 'Paid activation unavailable' : status.plan === plan.code ? 'Current plan' : plan.code === 'trial' ? 'Start Free Trial' : 'Choose Free Basic'}
    </Button>
  </section>)}</div>;
}
export default function Subscription() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const { updateOnboarding } = useOutletContext();
  const [data, setData] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState('');
  const [retry, setRetry] = useState(0), [success, setSuccess] = useState('');
  const keys = useRef({}), submitting = useRef(false);
  useEffect(() => {
    let active = true; setData(null); setError('');
    Promise.all([getPlans(), getSubscription()]).then(([plans, status]) => { if (active) setData({ plans, status }); })
      .catch(e => { if (active) setError(ownerError(e, 'Unable to load subscription options.')); });
    return () => { active = false; };
  }, [retry]);
  async function activate(plan) {
    if (submitting.current) return;
    submitting.current = true; setBusy(plan); setError('');
    try {
      // Retain this key on any failure, including a lost response after commit.
      keys.current[plan] ||= crypto.randomUUID();
      await activatePlan(plan, keys.current[plan]);
      const [status, onboarding] = await Promise.all([getSubscription(), getOnboarding('activation-confirmation')]);
      if (!activationConfirmed(status, onboarding)) throw new Error('Activation not confirmed');
      updateOnboarding(onboarding); setSuccess('Your plan is ready.');
      navigate('/owner/dashboard', { replace: true, state: { planActivated: true } });
    } catch (e) { setError(ownerError(e, 'Unable to confirm activation. Retry safely with the same request.')); }
    finally { submitting.current = false; setBusy(''); }
  }
  return <AccountLayout><header className="account-heading"><div><h1>Choose your studio plan</h1><p>Start with Free Basic or explicitly activate your one-time Free Trial.</p></div></header>
    {state?.studioSaved && <div className="account-notice" role="status">Studio details saved successfully.</div>}
    {success && <p role="status">{success}</p>}
    {error && <div className="account-error" role="alert">{error}<button className="account-secondary" disabled={Boolean(busy)} onClick={() => setRetry(n => n + 1)}>Reload options</button></div>}
    {!data && !error && <p role="status">Loading plans and current subscription…</p>}
    {data && <><PlanCards {...data} busy={busy} activate={activate} />
      {data.status.period_end && <p>Current credit period ends: {utcDate(data.status.period_end)}. Unused credits do not carry over.</p>}</>}
  </AccountLayout>;
}
