import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { getOwnerPaymentReadiness, startOwnerCheckout, ownerCheckoutAllowed } from '../../services/ownerPaymentService';
import useAuth from '../../hooks/useAuth';
import { checkoutRequestKey, clearCheckoutKey, checkoutExpired } from '../../services/paymentService';
import AccountLayout from '../../components/layout/AccountLayout';
import Button from '../../components/common/Button';
import { getPlans, getSubscription, activatePlan, getOnboarding } from '../../services/ownerService';
import { activationDisabled, activationConfirmed, ownerError, utcDate } from '../../utils/subscription';

export function PlanCards({ plans, status, readiness, busy, activate }) {
  return <div className="studio-plan-grid">{plans.map(plan => <section className={`account-card studio-plan studio-plan-${plan.code}`} key={plan.code}>
    <h2>{plan.name}</h2>{status.plan === plan.code && <span className="studio-plan-badge">Current plan</span>}
    <p className="studio-plan-price">{plan.currency} {Number(plan.price).toLocaleString()}{!['basic', 'trial'].includes(plan.code) ? '/month' : ''}</p>
    <ul><li>{plan.credits} credits {plan.credit_period === 'trial_total' ? 'total' : 'per month'}</li>
      <li>{plan.max_projects === null ? 'Unlimited' : plan.max_projects} active/editable projects</li><li>{plan.max_share_links === null ? 'Unlimited' : plan.max_share_links} active share links</li>
      <li>{plan.trial_days ? `${plan.trial_days} days · one trial per Studio Owner lifetime` : plan.code === 'basic' ? 'Free ongoing' : 'Manual monthly payment · no automatic renewal'}</li>
      <li>{plan.code === 'trial' ? 'Trial credits expire at the end of the trial.' : plan.code === 'basic' ? 'Credits renew on your plan anniversary, with no carryover.' : 'Credits are allocated per verified paid period, with no carryover.'}</li></ul>
    {!['basic', 'trial'].includes(plan.code) && <p>{readiness?.checkout_available ? 'Credits activate only after verified payment. Renew manually after your paid period ends.' : 'Payment setup pending deployment verification.'}</p>}
    {plan.code === 'trial' && !status.trial_available && <p>Your lifetime trial has already been used.</p>}
    <Button disabled={Boolean(busy) || (['basic', 'trial'].includes(plan.code) ? activationDisabled(plan, status) : !ownerCheckoutAllowed(readiness, status))} loading={busy === plan.code} onClick={() => activate(plan.code)}>
      {!['basic', 'trial'].includes(plan.code) ? (ownerCheckoutAllowed(readiness, status) ? 'Continue to Stripe Test Checkout' : readiness?.checkout_available ? 'Available after current period ends' : 'Payment setup pending') : status.plan === plan.code ? 'Current plan' : plan.code === 'trial' ? 'Start Free Trial' : 'Choose Free Basic'}
    </Button>
  </section>)}</div>;
}
export default function Subscription() {
  const { user } = useAuth();
  const { state, search } = useLocation();
  const paymentReturn = new URLSearchParams(search).get('payment');
  const navigate = useNavigate();
  const { updateOnboarding } = useOutletContext();
  const [data, setData] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState('');
  const [retry, setRetry] = useState(0), [success, setSuccess] = useState('');
  const keys = useRef({}), submitting = useRef(false);
  useEffect(() => {
    let active = true; setData(null); setError('');
    Promise.all([getPlans(), getSubscription(), getOwnerPaymentReadiness().catch(() => ({ checkout_available: false, paid_activation_available: false, unavailable: true }))]).then(([plans, status, readiness]) => { if (active) { setData({ plans, status, readiness }); if (['starter', 'growth', 'unlimited'].includes(status.plan)) { clearCheckoutKey('owner', user.id, status.plan); delete keys.current[status.plan]; } } })
      .catch(e => { if (active) setError(ownerError(e, 'Unable to load subscription options.')); });
    return () => { active = false; };
  }, [retry, search, user.id]);
  async function activate(plan) {
    if (submitting.current) return;
    submitting.current = true; setBusy(plan); setError('');
    try {
      // Retain this key on any failure, including a lost response after commit.
      keys.current[plan] ||= ['starter', 'growth', 'unlimited'].includes(plan) ? checkoutRequestKey('owner', user.id, plan) : crypto.randomUUID();
      if (['starter', 'growth', 'unlimited'].includes(plan)) {
        if (!ownerCheckoutAllowed(data?.readiness, data?.status)) throw new Error('Checkout unavailable');
        const url = await startOwnerCheckout(plan, keys.current[plan]);
        window.location.assign(url);
        return;
      }
      await activatePlan(plan, keys.current[plan]);
      const [status, onboarding] = await Promise.all([getSubscription(), getOnboarding('activation-confirmation')]);
      if (!activationConfirmed(status, onboarding)) throw new Error('Activation not confirmed');
      updateOnboarding(onboarding); setSuccess('Your plan is ready.');
      navigate('/owner/dashboard', { replace: true, state: { planActivated: true } });
    } catch (e) { if (checkoutExpired(e)) { clearCheckoutKey('owner', user.id, plan); delete keys.current[plan]; } setError(ownerError(e, 'Unable to confirm activation. Retry safely with the same request.')); }
    finally { submitting.current = false; setBusy(''); }
  }
  return <AccountLayout><header className="account-heading"><div><h1>Choose your studio plan</h1><p>Start with Free Basic or explicitly activate your one-time Free Trial.</p></div></header>
    {state?.studioSaved && <div className="account-notice" role="status">Studio details saved successfully.</div>}
    {['return', 'cancelled'].includes(paymentReturn) && <div className="account-notice" role="status">
      {paymentReturn === 'cancelled' ? 'Checkout cancelled. Your current subscription is shown below.' : 'Returned from Stripe. Only backend-verified subscription details are shown below; webhook confirmation may still be pending.'}
      <button className="account-secondary" disabled={Boolean(busy)} onClick={() => setRetry(n => n + 1)}>Refresh subscription status</button>
    </div>}
    {success && <p role="status">{success}</p>}
    {error && <div className="account-error" role="alert">{error}<button className="account-secondary" disabled={Boolean(busy)} onClick={() => setRetry(n => n + 1)}>Reload options</button></div>}
    {!data && !error && <p role="status">Loading plans and current subscription…</p>}
    {data?.readiness.unavailable && <p role="alert">Unable to load payment availability. Paid checkout is disabled. Refresh to retry.</p>}
    {data && <><PlanCards {...data} busy={busy} activate={activate} />
      <p>Current plan: {data.status.plan || 'Not available'} · Remaining credits: {data.status.remaining_credits ?? 'Not available'}</p>
      {data.status.period_end && <p>Current credit period ends: {utcDate(data.status.period_end)}. Unused credits do not carry over.</p>}</>}
  </AccountLayout>;
}
