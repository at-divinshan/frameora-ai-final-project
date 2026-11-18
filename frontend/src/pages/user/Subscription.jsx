import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import { loadUserPaymentState, startCheckout, userCheckoutAllowed, checkoutRequestKey, clearCheckoutKey, checkoutExpired } from '../../services/paymentService';
import { utcDate } from '../../utils/subscription';
import useAuth from "../../hooks/useAuth";
import { USER_SUBSCRIPTION_PLANS } from "../../config/userSubscriptionPlans";
import "../../styles/account.css";
import "../../styles/ai.css";

export function SubscriptionPlanCards({ readiness, status, busy, checkout } = {}) {
  const activePaid = ['starter', 'pro'].includes(status?.plan);
  return USER_SUBSCRIPTION_PLANS.map((plan) => (
    <article className="account-card user-subscription-card" key={plan.name}>
      <h2>{plan.name}</h2>
      <p className="studio-plan-price">{plan.currency} {plan.price}<span>{plan.code === 'free' ? '' : ' / month'}</span></p>
      <p>{plan.code === 'free' ? `${plan.free_images} generated images once per account` : `${plan.credits} AI credits per paid monthly period`}</p>
      {plan.code !== 'free' && <p className="ai-note">4 credits per four-image batch · No carryover · Available only after verified payment.</p>}
      <button className="user-dashboard-create-button" type="button" disabled={plan.code === 'free' || Boolean(busy) || !userCheckoutAllowed(readiness, status)} onClick={() => checkout(plan.code)}>
        {activePaid ? (status.plan === plan.code ? 'Current Plan' : 'Available After Your Current Plan Ends') : plan.code === 'free' ? 'Included — once per account' : busy === plan.code ? 'Opening checkout…' : userCheckoutAllowed(readiness, status) ? 'Continue to Stripe Test Checkout' : readiness?.checkout_available ? 'Available after current paid period ends' : 'Coming Soon — Payment setup pending'}
      </button>
    </article>
  ));
}

export function StudioOwnerUpgradeCard({ onUpgrade, busy, error, status }) {
  const activePaid = ['starter', 'pro'].includes(status?.plan);
  return (
    <article className="account-card user-subscription-card user-owner-upgrade-card">
      <h2>Become Studio Owner</h2>
      <p>Manage your studio profile, client photoshoots, photography plans, AI generations, and customer share links.</p>
      <ul>
        <li>Free Basic: 10 credits per month</li>
        <li>Manage up to 2 active projects and 3 share links</li>
        <li>Optional one-time Free Trial: 100 credits for 14 days</li>
      </ul>
      <p className="ai-note">Studio setup and a plan choice are required before the Studio Owner dashboard is available. The Free Trial starts only when you explicitly choose it.</p>
      {activePaid && <p role="note">Your current paid plan ends {status.period_end ? utcDate(status.period_end) : 'at the end of your paid period'}. You can become a Studio Owner afterward. Paid credits cannot be transferred.</p>}
      {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
      <button className="user-dashboard-create-button" type="button" disabled={busy || activePaid} onClick={onUpgrade}>
        {activePaid ? "Available After Your Current Plan Ends" : busy ? "Upgrading account…" : "Upgrade to Studio Owner"}
      </button>
    </article>
  );
}

function upgradeError(error, fallback = "Unable to upgrade this account. Please try again.") {
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

export default function Subscription() {
  const { becomeStudioOwner, user } = useAuth();
  const { search } = useLocation();
  const paymentReturn = new URLSearchParams(search).get('payment');
  const [payment, setPayment] = useState(null), [paymentError, setPaymentError] = useState('');
  const [checkoutBusy, setCheckoutBusy] = useState(''), [refresh, setRefresh] = useState(0);
  const checkoutKeys = useRef({}), checkoutSubmitting = useRef(false);
  useEffect(() => {
    let active = true; setPayment(null); setPaymentError('');
    (async () => {
      const { readiness, status } = await loadUserPaymentState();
      if (active) {
        setPayment({ readiness, status });
        if (['starter', 'pro'].includes(status?.plan)) { clearCheckoutKey('user', user.id, status.plan); delete checkoutKeys.current[status.plan]; }
      }
    })().catch(error => { if (active) setPaymentError(upgradeError(error, "Unable to confirm payment status. Refresh and retry safely.")); });
    return () => { active = false; };
  }, [search, refresh, user.id]);
  async function checkout(plan) {
    if (checkoutSubmitting.current || !userCheckoutAllowed(payment?.readiness, payment?.status)) return;
    checkoutSubmitting.current = true; setCheckoutBusy(plan); setPaymentError('');
    try {
      checkoutKeys.current[plan] ||= checkoutRequestKey('user', user.id, plan);
      const url = await startCheckout('user', plan, checkoutKeys.current[plan]);
      window.location.assign(url);
    } catch (error) {
      if (checkoutExpired(error)) { clearCheckoutKey('user', user.id, plan); delete checkoutKeys.current[plan]; }
      setPaymentError(upgradeError(error, "Unable to confirm payment status. Refresh and retry safely."));
    }
    finally { checkoutSubmitting.current = false; setCheckoutBusy(''); }
  }
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function upgrade() {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await becomeStudioOwner();
      navigate("/owner/studio-setup", { replace: true });
    } catch (requestError) {
      setError(upgradeError(requestError));
      setBusy(false);
    }
  }

  return (
    <DashboardLayout>
      <section className="user-plan-page account-page ai-page">
        <header className="account-heading">
          <div>
            <h1>Subscription Plans</h1>
            <p>Approved Normal User plans. Choose the option that fits your photography needs.</p>
          </div>
        </header>
        <p className="user-plan-message" role="note">Free includes one successful request of four images per account, not a monthly allowance. Paid credits require verified payment. Paid periods renew only through a new manual payment after expiry; unused credits do not carry over.</p>
        {['return', 'cancelled'].includes(paymentReturn) && <p role="status">{paymentReturn === 'cancelled' ? 'Checkout cancelled. No payment is assumed.' : 'Returned from Stripe. Payment may still be awaiting webhook verification. Only backend-confirmed credits are shown.'}</p>}
        {!payment && !paymentError && <p role="status">Loading payment availability and subscription…</p>}
        {paymentError && <p className="account-error" role="alert">{paymentError}</p>}
        {payment?.status && <p role="status">Current plan: {payment.status.plan} · Paid credits: {payment.status.remaining_credits ?? 'Not available'}{payment.status.period_end ? ` · Period ends: ${utcDate(payment.status.period_end)}` : ''}</p>}
        {payment && !payment.readiness.checkout_available && <p role="status">Stripe Test Checkout is disabled pending configuration and deployment verification.</p>}
        <button className="account-secondary" disabled={Boolean(checkoutBusy)} onClick={() => setRefresh(n => n + 1)}>Refresh subscription status</button>
        <div className="user-subscription-grid">
          <SubscriptionPlanCards {...payment} busy={checkoutBusy || busy} checkout={checkout} />
          <StudioOwnerUpgradeCard onUpgrade={upgrade} status={payment?.status} busy={busy || Boolean(checkoutBusy) || !payment?.status} error={error} />
        </div>
      </section>
    </DashboardLayout>
  );
}