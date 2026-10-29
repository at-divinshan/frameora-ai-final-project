import useAuth from "../../hooks/useAuth";
import DashboardLayout from "./DashboardLayout";
import OwnerLayout from "./OwnerLayout";
import AdminLayout from "./AdminLayout";
import "../../styles/account.css";

export default function AccountLayout({ children, title }) {
  const { user } = useAuth();
  const Layout = user?.role === "admin" ? AdminLayout : user?.role === "owner" ? OwnerLayout : DashboardLayout;
  return <Layout title={title}><div className="account-page">{children}</div></Layout>;
}
