import { Moon, Search, Sun } from "lucide-react";
import NotificationBell from "../common/NotificationBell";
import useAuth from "../../hooks/useAuth";
import useTheme from "../../hooks/useTheme";
import { Link } from "react-router-dom";
import AccountAvatar from "../common/AccountAvatar";

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
        <NotificationBell className="user-dashboard-icon-button" />
        <Link className="user-dashboard-account account-profile-link" to="/user/profile" aria-label="Open your profile">
          <AccountAvatar className="user-dashboard-avatar" />
          <div className="user-dashboard-account-copy">
            <span className="user-dashboard-account-name" title={user?.name}>{user?.name}</span>
            <span className="user-dashboard-account-role">{user?.role === "user" ? "Normal User" : ""}</span>
          </div>
        </Link>
        <button className="user-dashboard-icon-button user-dashboard-theme-toggle" type="button" onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
          {theme === "dark" ? <Moon size={19} aria-hidden="true" /> : <Sun size={19} aria-hidden="true" />}
        </button>
      </div>
    </header>
  );
}
