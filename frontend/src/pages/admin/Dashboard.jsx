import { Plus, Search, Users } from "lucide-react";
import AdminLayout from "../../components/layout/AdminLayout";

export default function Dashboard() {
  return (
    <AdminLayout>
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
    </AdminLayout>
  );
}
