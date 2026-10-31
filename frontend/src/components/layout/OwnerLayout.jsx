import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import {
  ArrowRight, Bell, Camera, ClipboardList, CreditCard, FolderOpen,
  Gem, House, Images, Link2, LogOut, Menu, Moon, Plus, Search,
  Sparkles, Sun, UserRound, Settings, X,
} from "lucide-react";
import AccountAvatar from "../common/AccountAvatar";
import FrameoraLogo from "../common/FrameoraLogo";
import useAuth from "../../hooks/useAuth";
import useTheme from "../../hooks/useTheme";
import "../../styles/dashboard.css";

const navigation = [
  { label: "Customer Projects", icon: FolderOpen },
  { label: "AI Preview", icon: Images },
  { label: "Equipment", icon: Camera },
  { label: "Share Links", icon: Link2 },
  { label: "Subscription", icon: CreditCard, path: "/owner/subscription" },
  { label: "Notifications", icon: Bell },
  { label: "Studio Profile", icon: Camera, path: "/owner/studio-setup" },
  { label: "Profile", icon: UserRound, path: "/owner/profile" },
  { label: "Settings", icon: Settings, path: "/owner/settings" },
];

export default function OwnerLayout({ children }) {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [navigationOpen, setNavigationOpen] = useState(false);
  const dark = theme === "dark";
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
            <NavLink className={({ isActive }) => `owner-nav-item${isActive ? " is-active" : ""}`} to="/owner/dashboard" onClick={() => setNavigationOpen(false)}>
              <House size={18} aria-hidden="true" />Dashboard
            </NavLink>
            {navigation.map(({ label, icon: Icon, path }) => path ? (
              <NavLink key={label} to={path} className={({ isActive }) => `owner-nav-item${isActive ? " is-active" : ""}`} onClick={() => setNavigationOpen(false)}><Icon size={18} aria-hidden="true" />{label}</NavLink>
            ) : (
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
            <Link className="owner-account account-profile-link" to="/owner/profile" aria-label="Open your profile">
              <AccountAvatar className="owner-avatar" />
              <div><strong title={user?.name}>{user?.name}</strong><span>Studio Owner</span></div>
            </Link>
            <button className="owner-icon-button owner-theme-toggle" type="button" onClick={toggleTheme}
              aria-label={`Switch to ${dark ? "light" : "dark"} mode`} title={`Switch to ${dark ? "light" : "dark"} mode`}>
              {dark ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
            </button>
          </div>
        </header>

        <main id="owner-dashboard-content" className="owner-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
