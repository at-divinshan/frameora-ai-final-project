import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { Bell, CalendarDays, ClipboardList, Compass, Heart, House, LogOut, Menu, UserRound, Settings, X } from "lucide-react";
import FrameoraLogo from "../common/FrameoraLogo";

const upcomingItems = [
  { label: "Explore", icon: Compass },
  { label: "My Plans", icon: ClipboardList },
  { label: "My Favorites", icon: Heart },
  { label: "My Bookings", icon: CalendarDays },
  { label: "Notifications", icon: Bell },
];

export default function Sidebar() {
  const [expanded, setExpanded] = useState(false);
  return (
    <aside className="user-dashboard-sidebar">
      <div className="user-dashboard-brand-row">
        <Link to="/user/dashboard" aria-label="Frameora home"><FrameoraLogo /></Link>
        <button className="user-dashboard-icon-button user-dashboard-menu-toggle" type="button"
          aria-label={expanded ? "Close navigation" : "Open navigation"}
          aria-expanded={expanded} aria-controls="user-dashboard-navigation"
          onClick={() => setExpanded((current) => !current)}>
          {expanded ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>
      <div id="user-dashboard-navigation" className={`user-dashboard-navigation${expanded ? " is-expanded" : ""}`}>
        <nav aria-label="Main navigation">
          <NavLink className={({ isActive }) => `user-dashboard-nav-item${isActive ? " is-active" : ""}`} to="/user/dashboard" onClick={() => setExpanded(false)}>
            <House size={20} aria-hidden="true" /><span>Home</span>
          </NavLink>
          {upcomingItems.map(({ label, icon: Icon }) => (
            <button className="user-dashboard-nav-item" key={label} type="button" disabled title={`${label} — coming soon`}>
              <Icon size={20} aria-hidden="true" /><span>{label}</span>
            </button>
          ))}
          {[{ path: "profile", label: "Profile", icon: UserRound }, { path: "settings", label: "Settings", icon: Settings }].map(({ path, label, icon: Icon }) => (
            <NavLink key={path} to={`/user/${path}`} className={({ isActive }) => `user-dashboard-nav-item${isActive ? " is-active" : ""}`} onClick={() => setExpanded(false)}>
              <Icon size={20} aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="user-dashboard-sidebar-footer">
          <p>More features coming soon.</p>
          <Link className="user-dashboard-nav-item" to="/logout"><LogOut size={20} aria-hidden="true" /><span>Logout</span></Link>
        </div>
      </div>
    </aside>
  );
}
