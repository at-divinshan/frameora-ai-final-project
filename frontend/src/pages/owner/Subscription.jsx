import { Camera, Sprout, Zap, Crown, Layers, Gem, Check, Info, RefreshCw } from 'lucide-react';
import '../../styles/owner-subscription.css';
import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useOutletContext } from 'react-router-dom';
import { getOwnerPaymentReadiness, startOwnerCheckout, ownerCheckoutAllowed } from '../../services/ownerPaymentService';
import useAuth from '../../hooks/useAuth';
import { checkoutRequestKey, clearCheckoutKey, checkoutExpired } from '../../services/paymentService';
import AccountLayout from '../../components/layout/AccountLayout';
import Button from '../../components/common/Button';
import { getPlans, getSubscription, activatePlan, getOnboarding } from '../../services/ownerService';
import { activationDisabled, activationConfirmed, ownerError, utcDate } from '../../utils/subscription';

const PLAN_ICONS = { basic: Sprout, trial: Zap, starter: Crown, growth: Layers, unlimited: Gem };

export function PlanCards({ plans, status, readiness, busy, activate }) {
  return <div className="studio-plan-grid">{plans.map(plan => {
    const Icon = PLAN_ICONS[plan.code] || Gem;
    return <section className={`account-card studio-plan studio-plan-${plan.code}${status.plan === plan.code ? ' is-current' : ''}`} key={plan.code}>
    <div className="owner-plan-card-heading"><span className="owner-plan-icon"><Icon size={26} aria-hidden="true" /></span><div><h2>{plan.name}</h2>
    <p className="studio-plan-price">{plan.currency} {Number(plan.price).toLocaleString('en-LK')}<span>{!['basic', 'trial'].includes(plan.code) ? ' / month' : ''}</span></p></div>
    {status.plan === plan.code && <span className="studio-plan-badge">Current plan</span>}</div>
    <ul><li><Check size={18} aria-hidden="true" /><span>{plan.credits} credits {plan.credit_period === 'trial_total' ? 'total' : 'per month'}</span></li>
      <li><Check size={18} aria-hidden="true" /><span>{plan.max_projects === null ? 'Unlimited' : plan.max_projects} active/editable projects</span></li><li><Check size={18} aria-hidden="true" /><span>{plan.max_share_links === null ? 'Unlimited' : plan.max_share_links} active share links</span></li>
      <li><Check size={18} aria-hidden="true" /><span>{plan.trial_days ? `${plan.trial_days} days · one trial per Studio Owner lifetime` : plan.code === 'basic' ? 'Free ongoing' : 'Manual monthly payment · no automatic renewal'}</span></li>
      <li><Check size={18} aria-hidden="true" /><span>{plan.code === 'trial' ? 'Trial credits expire at the end of the trial.' : plan.code === 'basic' ? 'Credits renew on your plan anniversary, with no carryover.' : 'Credits are allocated per verified paid period, with no carryover.'}</span></li></ul>
    {!['basic', 'trial'].includes(plan.code) && <p className="owner-plan-note">{readiness?.checkout_available ? 'Credits activate only after verified payment. Renew manually after your paid period ends.' : 'Payment setup pending deployment verification.'}</p>}
    {plan.code === 'trial' && !status.trial_available && <p className="owner-plan-note" role="note"><Info size={17} aria-hidden="true" />Your lifetime trial has already been used.</p>}
    <Button disabled={Boolean(busy) || (['basic', 'trial'].includes(plan.code) ? activationDisabled(plan, status) : !ownerCheckoutAllowed(readiness, status))} loading={busy === plan.code} onClick={() => activate(plan.code)}>
      {status.plan === plan.code ? 'Current plan' : !['basic', 'trial'].includes(plan.code) ? (ownerCheckoutAllowed(readiness, status) ? 'Continue to Stripe Test Checkout' : readiness?.checkout_available ? 'Available after current period ends' : 'Payment setup pending') : status.plan === plan.code ? 'Current plan' : plan.code === 'trial' ? 'Start Free Trial' : 'Choose Free Basic'}
    </Button>
  </section>; })}</div>;
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
  return <AccountLayout><section className="owner-subscription-page"><header className="account-heading"><div><h1><span className="owner-plan-icon"><Camera size={28} aria-hidden="true" /></span>Studio Owner Plans</h1><p>Choose the right plan for your studio. Manage projects, share links, and generate AI images for your clients.</p></div></header>
    <div className="owner-plan-overview" role="note"><Info size={25} aria-hidden="true" /><div><h2>Plan Overview</h2><p>Start with Free Basic or explicitly activate your one-time Free Trial. Paid plans require verified payment and renew only through a new manual payment after expiry. Unused credits do not carry over.</p></div></div>
    {state?.studioSaved && <div className="account-notice" role="status">Studio details saved successfully.</div>}
    {['return', 'cancelled'].includes(paymentReturn) && <div className="account-notice" role="status">
      {paymentReturn === 'cancelled' ? 'Checkout cancelled. Your current subscription is shown below.' : 'Returned from Stripe. Only backend-verified subscription details are shown below; webhook confirmation may still be pending.'}
    </div>}
    {success && <p role="status">{success}</p>}
    {error && <div className="account-error" role="alert">{error}<button className="account-secondary" disabled={Boolean(busy)} onClick={() => setRetry(n => n + 1)}>Reload options</button></div>}
    {!data && !error && <p role="status">Loading plans and current subscription…</p>}
    {data?.readiness.unavailable && <p role="alert">Unable to load payment availability. Paid checkout is disabled. Refresh to retry.</p>}
    <div className="owner-plan-status-row">
      {data && <OwnerSubscriptionStatus status={data.status} plans={data.plans} />}
      <button className="account-secondary owner-plan-refresh" disabled={Boolean(busy)} onClick={() => setRetry(n => n + 1)}><RefreshCw size={16} aria-hidden="true" />Refresh subscription status</button>
    </div>
    {data && <PlanCards {...data} busy={busy} activate={activate} />}
  </section></AccountLayout>;
}

export function OwnerSubscriptionStatus({ status, plans }) {
  return <dl className="owner-plan-status" aria-label="Current studio subscription">
    <div><dt><Layers size={18} aria-hidden="true" />Current plan</dt><dd>{plans.find(plan => plan.code === status.plan)?.name || status.plan || 'Not available'}</dd></div>
    <div><dt>Remaining credits</dt><dd>{status.remaining_credits ?? 'Not available'}</dd></div>
    <div><dt>Credit period ends</dt><dd>{status.period_end ? utcDate(status.period_end) : 'Not available'}</dd></div>
  </dl>;
}
