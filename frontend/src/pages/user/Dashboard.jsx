import { ArrowRight, Images } from "lucide-react";
import DashboardLayout from "../../components/layout/DashboardLayout";
import useTheme from "../../hooks/useTheme";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const { theme } = useTheme();
  return (
    <DashboardLayout>
      <section className="user-dashboard-hero" aria-labelledby="dashboard-hero-heading">
        <div className="user-dashboard-hero-copy">
          <h1 id="dashboard-hero-heading">Find Your Perfect<br /><span>Photography</span> Plan</h1>
          <p>Plan smarter. Create beautiful memories with AI.</p>
          <Link className="user-dashboard-create-button" to="/user/plans/create">
            Create New Plan <ArrowRight size={17} aria-hidden="true" />
          </Link>
        </div>
        <img className="user-dashboard-hero-image"
          src={`/images/hero/dashboard-hero-${theme === "dark" ? "dark" : "light"}.png`}
          alt="" width="2028" height="380" fetchPriority="high" />
      </section>
      <section className="user-dashboard-plans" aria-labelledby="dashboard-plans-heading">
        <div className="user-dashboard-section-heading">
          <h2 id="dashboard-plans-heading">Popular Categories</h2>
          <Link to="/user/plans" className="user-dashboard-view-all">
            My Plans <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </div>
        {/* No published-plans API exists yet. Do not substitute example cards or counts. */}
        <div className="user-dashboard-empty-state">
          <Images size={30} strokeWidth={1.5} aria-hidden="true" />
          <p>No photography plans available yet.</p>
        </div>
        <p id="dashboard-unavailable-note" className="user-dashboard-availability-note">Explore and search are coming soon.</p>
      </section>
    </DashboardLayout>
  );
}
