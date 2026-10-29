import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { BarChart3, Bell, Building2, CalendarDays, CreditCard, FolderOpen, House, LogOut, Menu, Moon, Plus, Search, Settings, Sun, Users, UserRound, X } from "lucide-react";
import AccountAvatar from "../common/AccountAvatar";
import FrameoraLogo from "../common/FrameoraLogo";
import useAuth from "../../hooks/useAuth";
import useTheme from "../../hooks/useTheme";
import "../../styles/dashboard.css";

const navigation = [
  { label: "Users", icon: Users },
  { label: "Studios", icon: Building2 },
  { label: "Projects", icon: FolderOpen },
  { label: "Bookings", icon: CalendarDays },
  { label: "Payments", icon: CreditCard },
  { label: "Analytics", icon: BarChart3 },
  { label: "Notifications", icon: Bell },
  { label: "Profile", icon: UserRound, path: "/admin/profile" },
  { label: "Settings", icon: Settings, path: "/admin/settings" },
];

export default function AdminLayout({ children, title = "Manage Users & Studio Owners" }) {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [menuOpen, setMenuOpen] = useState(false);
  const dark = theme === "dark";

  return (
    <div className="admin-dashboard">
      <a className="admin-skip-link" href="#admin-dashboard-content">Skip to content</a>
      <aside className="admin-sidebar">
        <div className="admin-brand-row">
          <Link to="/admin/dashboard" aria-label="Frameora Admin dashboard"><FrameoraLogo /></Link>
          <button className="admin-icon-button admin-menu-toggle" type="button" aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            aria-expanded={menuOpen} aria-controls="admin-navigation" onClick={() => setMenuOpen((open) => !open)}>
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
        <div id="admin-navigation" className={`admin-navigation${menuOpen ? " is-open" : ""}`}>
          <nav aria-label="Admin navigation">
            <NavLink className={({ isActive }) => `admin-nav-item${isActive ? " is-active" : ""}`} to="/admin/dashboard" onClick={() => setMenuOpen(false)}><House size={18} aria-hidden="true" />Dashboard</NavLink>
            {navigation.map(({ label, icon: Icon, path }) => path ? (
              <NavLink key={label} to={path} className={({ isActive }) => `admin-nav-item${isActive ? " is-active" : ""}`} onClick={() => setMenuOpen(false)}><Icon size={18} aria-hidden="true" />{label}</NavLink>
            ) : (
              <button className="admin-nav-item" key={label} type="button" disabled title={`${label} — coming soon`}><Icon size={18} aria-hidden="true" />{label}</button>
            ))}
          </nav>
          <div className="admin-sidebar-footer">
            <p>More features coming soon.</p>
            <Link className="admin-nav-item" to="/logout"><LogOut size={18} aria-hidden="true" />Logout</Link>
          </div>
        </div>
      </aside>
      <div className="admin-workspace">
        <header className="admin-navbar">
          <h1>{title}</h1>
          <div className="admin-navbar-controls">
            <button className="admin-icon-button" type="button" disabled title="Notifications — coming soon" aria-label="Notifications — coming soon"><Bell size={20} aria-hidden="true" /></button>
            <Link className="admin-account account-profile-link" to="/admin/profile" aria-label="Open your profile">
              <AccountAvatar className="admin-avatar" />
              <div><strong title={user?.name}>{user?.name}</strong><span>Admin</span></div>
            </Link>
            <button className="admin-icon-button admin-theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${dark ? "light" : "dark"} mode`} title={`Switch to ${dark ? "light" : "dark"} mode`}>
              {dark ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
            </button>
          </div>
        </header>
        <main id="admin-dashboard-content" className="admin-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
