import { Navigate, Outlet, useLocation } from "react-router-dom";
import { safeShareReturn } from "../utils/shareReturn";
import useAuth from "../hooks/useAuth";

export default function ProtectedRoute() {
  const location = useLocation();
  const returnTo = safeShareReturn(location.pathname);
  const { user, loading, authError } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to={returnTo ? `/login?returnTo=${encodeURIComponent(returnTo)}` : "/login"} replace state={{ authError }} />;
  return <Outlet />;
}
