import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import PlanForm from "../../components/photography/PlanForm";
import { createPlan } from "../../services/planService";

export default function CreatePlan() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  async function submit(values) {
    setSubmitting(true);
    try {
      await createPlan(values);
      navigate("/user/plans", { replace: true, state: { planCreated: true } });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DashboardLayout>
      <section className="user-plan-page account-page" aria-labelledby="create-plan-heading">
        <div className="account-heading">
          <div>
            <h1 id="create-plan-heading">Create Photography Plan</h1>
            <p>Capture the details for your upcoming photography session.</p>
          </div>
          <Link className="account-secondary" to="/user/plans">My Plans</Link>
        </div>
        <div className="account-card user-plan-form-card">
          <PlanForm onSubmit={submit} submitting={submitting} />
        </div>
      </section>
    </DashboardLayout>
  );
}