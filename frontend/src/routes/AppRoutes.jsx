import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import Login from "../pages/auth/Login";
import Register from "../pages/auth/Register";
import ForgotPassword from "../pages/auth/ForgotPassword";
import GoogleCallback from "../pages/auth/GoogleCallback";
import GoogleLink from "../pages/auth/GoogleLink";
import UserDashboard from "../pages/user/Dashboard";
import OwnerDashboard from "../pages/owner/Dashboard";
import AdminDashboard from "../pages/admin/Dashboard";
import ProtectedRoute from "./ProtectedRoute";
import RoleRoute from "./RoleRoute";
import useAuth from "../hooks/useAuth";
import { DASHBOARD_ROUTES, dashboardRoute } from "../utils/constants";

import PublicLayout from "../components/public/PublicLayout";
import Landing from "../pages/public/Landing";
import { Features, HowItWorks, ForCreators, ForStudios, About } from "../pages/public/MarketingPages";

function PublicAuthRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to={dashboardRoute(user.role)} replace /> : children;
}

function Logout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  useEffect(() => {
    logout();
    navigate("/login", { replace: true });
  }, [logout, navigate]);
  return null;
}

export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/features" element={<Features />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/for-creators" element={<ForCreators />} />
        <Route path="/for-studios" element={<ForStudios />} />
        <Route path="/about" element={<About />} />
      </Route>
      <Route path="/login" element={<PublicAuthRoute><Login /></PublicAuthRoute>} />
      <Route path="/register" element={<PublicAuthRoute><Register /></PublicAuthRoute>} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/logout" element={<Logout />} />
      <Route path="/auth/google/callback" element={<GoogleCallback />} />
      <Route path="/auth/google/link" element={<GoogleLink />} />
      <Route element={<ProtectedRoute />}>
        {Object.entries(DASHBOARD_ROUTES).map(([role, path]) => (
          <Route key={role} element={<RoleRoute role={role} />}>
            <Route path={path} element={role === "user" ? <UserDashboard /> : role === "owner" ? <OwnerDashboard /> : role === "admin" ? <AdminDashboard /> : null} />
          </Route>
        ))}
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
