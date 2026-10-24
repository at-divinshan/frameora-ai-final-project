import { useState } from "react";
import { Link } from "react-router-dom";
import { BarChart3, Bell, Building2, CalendarDays, CreditCard, FolderOpen, House, LogOut, Menu, Moon, Plus, Search, Settings, Sun, Users, X } from "lucide-react";
import FrameoraLogo from "../../components/common/FrameoraLogo";
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
  { label: "Settings", icon: Settings },
];

export default function Dashboard() {
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
            <Link className="admin-nav-item is-active" to="/admin/dashboard" aria-current="page" onClick={() => setMenuOpen(false)}><House size={18} aria-hidden="true" />Dashboard</Link>
            {navigation.map(({ label, icon: Icon }) => (
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
          <h1>Manage Users &amp; Studio Owners</h1>
          <div className="admin-navbar-controls">
            <button className="admin-icon-button" type="button" disabled title="Notifications — coming soon" aria-label="Notifications — coming soon"><Bell size={20} aria-hidden="true" /></button>
            <div className="admin-account">
              <span className="admin-avatar" aria-hidden="true">{user?.name?.trim().charAt(0).toUpperCase()}</span>
              <div><strong title={user?.name}>{user?.name}</strong><span>Admin</span></div>
            </div>
            <button className="admin-icon-button admin-theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${dark ? "light" : "dark"} mode`} title={`Switch to ${dark ? "light" : "dark"} mode`}>
              {dark ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
            </button>
          </div>
        </header>
        <main id="admin-dashboard-content" className="admin-content" tabIndex={-1}>
          <section aria-labelledby="admin-users-heading">
            <h2 id="admin-users-heading" className="admin-section-title">All Users</h2>
            <div className="admin-table-toolbar">
              <div className="admin-search" title="User search — coming soon">
                <Search size={16} aria-hidden="true" />
                <input type="search" placeholder="Search users..." aria-label="Search users — coming soon" disabled />
              </div>
              <button className="admin-add-button" type="button" disabled title="Studio management — coming soon"><Plus size={16} aria-hidden="true" />Add Studio</button>
            </div>
            <div className="admin-table-scroll" role="region" aria-label="Users table" tabIndex={0}>
              <table className="admin-users-table">
                <caption className="admin-visually-hidden">Users and Studio Owners. User data is not available yet.</caption>
                <thead><tr>{["#", "Name", "Email", "Role", "Status", "Joined Date", "Actions"].map((heading) => <th scope="col" key={heading}>{heading}</th>)}</tr></thead>
                <tbody>
                  {/* No admin users API exists. Never substitute fabricated users or counts. */}
                  <tr><td colSpan={7} className="admin-empty-cell">
                    <div className="admin-empty-state"><Users size={32} strokeWidth={1.5} aria-hidden="true" /><p>User data is not available yet.</p><span>Users and Studio Owners will appear here when available.</span></div>
                  </td></tr>
                </tbody>
              </table>
            </div>
            <p className="admin-availability-note">User search, studio management, and account actions are coming soon.</p>
          </section>
        </main>
      </div>
    </div>
  );
}
