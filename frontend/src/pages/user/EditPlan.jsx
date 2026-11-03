import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import PlanForm, { mapPlanToFormValues } from "../../components/photography/PlanForm";
import { getPlanErrorMessage, getMyPlan, updatePlan } from "../../services/planService";

export default function EditPlan() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    getMyPlan(planId, controller.signal)
      .then(setPlan)
      .catch((requestError) => {
        if (!controller.signal.aborted) setError(getPlanErrorMessage(requestError, "load"));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [planId]);

  async function submit(values) {
    setSubmitting(true);
    try {
      await updatePlan(planId, values);
      navigate("/user/plans", { replace: true, state: { planUpdated: true } });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DashboardLayout>
      <section className="user-plan-page account-page" aria-labelledby="edit-plan-heading">
        <div className="account-heading">
          <div>
            <h1 id="edit-plan-heading">Edit Photography Plan</h1>
            <p>Update the details for your photography session.</p>
          </div>
          <Link className="account-secondary" to="/user/plans">My Plans</Link>
        </div>
        {loading ? (
          <div className="user-dashboard-empty-state" role="status">Loading your plan…</div>
        ) : error ? (
          <div className="user-plan-message is-error" role="alert">
            <p>{error}</p>
            <Link className="account-secondary" to="/user/plans">Back to My Plans</Link>
          </div>
        ) : plan ? (
          <div className="account-card user-plan-form-card">
            <PlanForm
              key={plan.id}
              initialValues={mapPlanToFormValues(plan)}
              onSubmit={submit}
              submitting={submitting}
              submitLabel="Save Changes"
            />
          </div>
        ) : null}
      </section>
    </DashboardLayout>
  );
}
