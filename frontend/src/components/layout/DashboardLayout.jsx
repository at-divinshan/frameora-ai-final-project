import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import "../../styles/dashboard.css";

export default function DashboardLayout({ children }) {
  return (
    <div className="user-dashboard">
      <a className="user-dashboard-skip-link" href="#user-dashboard-content">Skip to content</a>
      <Sidebar />
      <div className="user-dashboard-workspace">
        <Navbar />
        <main id="user-dashboard-content" className="user-dashboard-content" tabIndex={-1}>{children}</main>
      </div>
    </div>
  );
}
