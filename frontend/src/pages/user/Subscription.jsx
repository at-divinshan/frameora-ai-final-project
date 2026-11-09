import { useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import useAuth from "../../hooks/useAuth";
import { USER_SUBSCRIPTION_PLANS } from "../../config/userSubscriptionPlans";
import "../../styles/account.css";
import "../../styles/ai.css";

export function SubscriptionPlanCards() {
  return USER_SUBSCRIPTION_PLANS.map((plan) => (
    <article className="account-card user-subscription-card" key={plan.name}>
      <h2>{plan.name}</h2>
      <p className="studio-plan-price">${plan.price}<span> / month</span></p>
      <p>{plan.credits} AI credits each month</p>
      <button className="user-dashboard-create-button" type="button" disabled>
        Subscribe — checkout unavailable
      </button>
    </article>
  ));
}

export function StudioOwnerUpgradeCard({ onUpgrade, busy, error }) {
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
      {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
      <button className="user-dashboard-create-button" type="button" disabled={busy} onClick={onUpgrade}>
        {busy ? "Upgrading account…" : "Upgrade to Studio Owner"}
      </button>
    </article>
  );
}

function upgradeError(error) {
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : "Unable to upgrade this account. Please try again.";
}

export default function Subscription() {
  const { becomeStudioOwner } = useAuth();
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
            <p>Choose an option for your account. Normal User plans below are provisional placeholders only.</p>
          </div>
        </header>
        <p className="user-plan-message" role="note">Provisional pricing — these sample plans are not real purchasable subscriptions. Checkout remains disabled until verified payment integration is available.</p>
        <div className="user-subscription-grid">
          <SubscriptionPlanCards />
          <StudioOwnerUpgradeCard onUpgrade={upgrade} busy={busy} error={error} />
        </div>
      </section>
    </DashboardLayout>
  );
}