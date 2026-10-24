import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, Bell, Camera, ClipboardList, CreditCard, FolderOpen,
  Gem, House, Images, Link2, LogOut, Menu, Moon, Plus, Search,
  Sparkles, Sun, UserRound, X,
} from "lucide-react";
import FrameoraLogo from "../../components/common/FrameoraLogo";
import useAuth from "../../hooks/useAuth";
import useTheme from "../../hooks/useTheme";
import "../../styles/dashboard.css";

const navigation = [
  { label: "Customer Projects", icon: FolderOpen },
  { label: "AI Preview", icon: Images },
  { label: "Equipment", icon: Camera },
  { label: "Share Links", icon: Link2 },
  { label: "Subscription", icon: CreditCard },
  { label: "Notifications", icon: Bell },
  { label: "Profile", icon: UserRound },
];

export default function Dashboard() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const dark = theme === "dark";
  // Labels follow the supplied references; values await real dashboard APIs.
  const metrics = [
    { label: "Active Projects", icon: ClipboardList, color: "cyan" },
    { label: "Total Previews", icon: Images, color: "purple" },
    { label: dark ? "Active Share Links" : "Total Share Links", icon: Link2, color: "orange" },
    { label: dark ? "Credits Left" : "Total Bookings", icon: Gem, color: "pink" },
  ];

  return (
    <div className="owner-dashboard">
      <a className="owner-skip-link" href="#owner-dashboard-content">Skip to content</a>
      <aside className="owner-sidebar">
        <div className="owner-brand-row">
          <Link to="/owner/dashboard" aria-label="Frameora Studio Owner dashboard"><FrameoraLogo /></Link>
          <button className="owner-icon-button owner-menu-toggle" type="button"
            aria-label={navigationOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={navigationOpen} aria-controls="owner-navigation"
            onClick={() => setNavigationOpen((open) => !open)}>
            {navigationOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
        <div id="owner-navigation" className={`owner-navigation${navigationOpen ? " is-open" : ""}`}>
          <nav aria-label="Studio navigation">
            <Link className="owner-nav-item is-active" to="/owner/dashboard" aria-current="page" onClick={() => setNavigationOpen(false)}>
              <House size={18} aria-hidden="true" />Dashboard
            </Link>
            {navigation.map(({ label, icon: Icon }) => (
              <button key={label} className="owner-nav-item" type="button" disabled title={`${label} — coming soon`}>
                <Icon size={18} aria-hidden="true" />{label}
              </button>
            ))}
          </nav>
          <div className="owner-upgrade">
            <div className="owner-upgrade-copy">
              <Gem size={25} aria-hidden="true" />
              <div><strong>Upgrade to Pro</strong><span>Unlock more features</span></div>
            </div>
            <button className="owner-gradient-button" type="button" disabled title="Subscription upgrades — coming soon">Upgrade <Plus size={14} aria-hidden="true" /></button>
          </div>
          <p className="owner-navigation-note">More features coming soon.</p>
          <Link className="owner-nav-item owner-logout" to="/logout"><LogOut size={18} aria-hidden="true" />Logout</Link>
        </div>
      </aside>

      <div className="owner-workspace">
        <header className="owner-navbar">
          <div className="owner-search" title="Customer and project search — coming soon">
            <Search size={16} aria-hidden="true" />
            <input type="search" placeholder="Search customers, projects..." aria-label="Search customers and projects — coming soon" disabled />
          </div>
          <div className="owner-navbar-controls">
            <button className="owner-icon-button" type="button" disabled title="Notifications — coming soon" aria-label="Notifications — coming soon"><Bell size={20} aria-hidden="true" /></button>
            <div className="owner-account">
              <span className="owner-avatar" aria-hidden="true">{user?.name?.trim().charAt(0).toUpperCase()}</span>
              <div><strong title={user?.name}>{user?.name}</strong><span>Studio Owner</span></div>
            </div>
            <button className="owner-icon-button owner-theme-toggle" type="button" onClick={toggleTheme}
              aria-label={`Switch to ${dark ? "light" : "dark"} mode`} title={`Switch to ${dark ? "light" : "dark"} mode`}>
              {dark ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
            </button>
          </div>
        </header>

        <main id="owner-dashboard-content" className="owner-content" tabIndex={-1}>
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
        </main>
      </div>
    </div>
  );
}
