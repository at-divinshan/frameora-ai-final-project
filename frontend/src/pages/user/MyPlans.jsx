import { useCallback, useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Images, Plus } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import PlanCard from "../../components/photography/PlanCard";
import { getMyPlans, getPlanErrorMessage } from "../../services/planService";

export default function MyPlans() {
  const location = useLocation();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(() => {
    if (location.state?.planUpdated) return "Your photography plan was updated.";
    if (location.state?.planCreated) return "Your photography plan was created.";
    return "";
  });

  const loadPlans = useCallback(async (signal) => {
    setLoading(true);
    setError("");
    try {
      setPlans(await getMyPlans(signal));
    } catch (requestError) {
      if (!signal?.aborted) {
        setError(getPlanErrorMessage(requestError, "load"));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  function removePlan(planId) {
    setPlans((current) => current.filter((plan) => plan.id !== planId));
    setNotice("Your photography plan was deleted.");
  }

  useEffect(() => {
    const controller = new AbortController();
    loadPlans(controller.signal);
    return () => controller.abort();
  }, [loadPlans]);

  return (
    <DashboardLayout>
      <section className="user-plan-page" aria-labelledby="my-plans-heading">
        <div className="user-dashboard-section-heading user-plan-page-heading">
          <div>
            <h1 id="my-plans-heading">My Photography Plans</h1>
            <p>Photography plans you have created.</p>
          </div>
          <Link className="user-dashboard-create-button" to="/user/plans/create">
            <Plus size={17} aria-hidden="true" /> Create Plan
          </Link>
        </div>
        <div className="user-dashboard-section-heading"><Link className="user-dashboard-view-all" to="/user/ai">Generate Images</Link><Link className="user-dashboard-view-all" to="/user/gallery">My Gallery</Link></div>
        {notice && <p className="user-plan-message" role="status">{notice}</p>}
        {loading ? (
          <div className="user-dashboard-empty-state" role="status">Loading your plans…</div>
        ) : error ? (
          <div className="user-plan-message is-error" role="alert">
            <p>{typeof error === "string" ? error : "Unable to load your plans. Please try again."}</p>
            <button type="button" className="account-secondary" onClick={() => loadPlans()}>Try again</button>
          </div>
        ) : plans.length === 0 ? (
          <div className="user-dashboard-empty-state">
            <Images size={30} strokeWidth={1.5} aria-hidden="true" />
            <p>You haven’t created any photography plans yet.</p>
            <Link className="user-dashboard-create-button" to="/user/plans/create">Create your first plan</Link>
          </div>
        ) : (
          <div className="user-plan-grid">
            {plans.map((plan) => <PlanCard key={plan.id} plan={plan} onDeleted={removePlan} />)}
          </div>
        )}
      </section>
    </DashboardLayout>
  );
}