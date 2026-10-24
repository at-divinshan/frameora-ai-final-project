import { Bell, Moon, Search, Sun } from "lucide-react";
import useAuth from "../../hooks/useAuth";
import useTheme from "../../hooks/useTheme";

export default function Navbar() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  return (
    <header className="user-dashboard-navbar">
      <div className="user-dashboard-search" title="Search is coming soon">
        <Search size={17} aria-hidden="true" />
        <input type="search" aria-label="Search photos, studios, styles — coming soon" placeholder="Search photos, studios, styles..." disabled />
      </div>
      <div className="user-dashboard-account-controls">
        <button className="user-dashboard-icon-button" type="button" disabled aria-label="Notifications — coming soon" title="Notifications — coming soon">
          <Bell size={21} aria-hidden="true" />
        </button>
        <div className="user-dashboard-account">
          <span className="user-dashboard-avatar" aria-hidden="true">{user?.name?.trim().charAt(0).toUpperCase()}</span>
          <div className="user-dashboard-account-copy">
            <span className="user-dashboard-account-name" title={user?.name}>{user?.name}</span>
            <span className="user-dashboard-account-role">{user?.role === "user" ? "Normal User" : ""}</span>
          </div>
        </div>
        <button className="user-dashboard-icon-button user-dashboard-theme-toggle" type="button" onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
          {theme === "dark" ? <Moon size={19} aria-hidden="true" /> : <Sun size={19} aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
}
