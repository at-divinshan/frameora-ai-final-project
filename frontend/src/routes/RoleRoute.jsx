import { Navigate, Outlet } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import { dashboardRoute } from "../utils/constants";

export default function RoleRoute({ role }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={dashboardRoute(user.role)} replace />;
  return <Outlet />;
}
