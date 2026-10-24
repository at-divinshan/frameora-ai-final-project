import { Navigate, Outlet } from "react-router-dom";
import useAuth from "../hooks/useAuth";

export default function ProtectedRoute() {
  const { user, loading, authError } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace state={{ authError }} />;
  return <Outlet />;
}
