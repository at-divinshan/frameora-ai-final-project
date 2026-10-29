import { ArrowRight, ClipboardList, FolderOpen, Gem, Images, Link2, Plus, Sparkles } from "lucide-react";
import useAuth from "../../hooks/useAuth";
import useTheme from "../../hooks/useTheme";
import OwnerLayout from "../../components/layout/OwnerLayout";

export default function Dashboard() {
  const { user } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  // Labels follow the supplied references; values await real dashboard APIs.
  const metrics = [
    { label: "Active Projects", icon: ClipboardList, color: "cyan" },
    { label: "Total Previews", icon: Images, color: "purple" },
    { label: dark ? "Active Share Links" : "Total Share Links", icon: Link2, color: "orange" },
    { label: dark ? "Credits Left" : "Total Bookings", icon: Gem, color: "pink" },
  ];

  return (
    <OwnerLayout>
          <section className="owner-welcome" aria-labelledby="owner-welcome-heading">
            <div>
              <p className="owner-welcome-eyebrow">Welcome Back,</p>
              <h1 id="owner-welcome-heading">{user?.name}! <span aria-hidden="true">👋</span></h1>
              <p className="owner-welcome-description">Manage your studio projects and create amazing previews.</p>
            </div>
            <button className="owner-gradient-button owner-new-project" type="button" disabled title="Project creation — coming soon" aria-describedby="owner-data-note"><Plus size={17} aria-hidden="true" />New Project</button>
          </section>

          <section className="owner-metrics" aria-label="Studio overview" aria-describedby="owner-data-note">
            {metrics.map(({ label, icon: Icon, color }) => (
              <div className="owner-metric" key={label}>
                <span className={`owner-metric-icon owner-metric-icon-${color}`}><Icon size={22} aria-hidden="true" /></span>
                <div><span className="owner-metric-value" aria-label="Data unavailable">—</span><span className="owner-metric-label">{label}</span></div>
              </div>
            ))}
          </section>

          <section className="owner-projects" aria-labelledby="owner-projects-heading">
            <div className="owner-section-heading">
              <h2 id="owner-projects-heading">Recent Customer Projects</h2>
              <button className="owner-view-all" type="button" disabled title="Customer projects — coming soon">View All <ArrowRight size={16} aria-hidden="true" /></button>
            </div>
            <div className="owner-empty-state">
              <FolderOpen size={32} strokeWidth={1.5} aria-hidden="true" />
              <p>Customer projects are not available yet.</p>
              <span>Your recent projects will appear here when available.</span>
            </div>
            <p id="owner-data-note" className="owner-data-note"><Sparkles size={14} aria-hidden="true" />Studio statistics and project features are not available yet.</p>
          </section>
    </OwnerLayout>
  );
}
