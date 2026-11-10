import LivePoseGuide from "../pages/shared/LivePoseGuide";
import SharedGallery from "../pages/shared/SharedGallery";
import { shareReturnFromSearch } from "../utils/shareReturn";
import AIGenerator from "../pages/user/AIGenerator";
import AIResults from "../pages/user/AIResults";
import UserProfile from "../pages/user/Profile";
import UserSettings from "../pages/user/Settings";
import OwnerProfile from "../pages/owner/Profile";
import OwnerSettings from "../pages/owner/Settings";
import AdminProfile from "../pages/admin/Profile";
import AdminSettings from "../pages/admin/Settings";
import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate, useLocation } from "react-router-dom";
import Login from "../pages/auth/Login";
import Register from "../pages/auth/Register";
import ForgotPassword from "../pages/auth/ForgotPassword";
import GoogleCallback from "../pages/auth/GoogleCallback";
import GoogleLink from "../pages/auth/GoogleLink";
import UserDashboard from "../pages/user/Dashboard";
import CreatePlan from "../pages/user/CreatePlan";
import EditPlan from "../pages/user/EditPlan";
import MyPlans from "../pages/user/MyPlans";
import UserSubscription from "../pages/user/Subscription";
import Projects from "../pages/owner/Projects";
import CreateProject from "../pages/owner/CreateProject";
import ProjectDetails from "../pages/owner/ProjectDetails";
import OwnerDashboard from "../pages/owner/Dashboard";
import OwnerAIGenerator from "../pages/owner/AIGenerator";
import OwnerAIResults from "../pages/owner/AIResults";
import StudioSetup from "../pages/owner/StudioSetup";
import SubscriptionSelection from "../pages/owner/Subscription";
import OwnerAccountHistory from "../pages/owner/AccountHistory";
import AdminDashboard from "../pages/admin/Dashboard";
import ProtectedRoute from "./ProtectedRoute";
import RoleRoute from "./RoleRoute";
import OwnerOnboardingRoute from "./OwnerOnboardingRoute";
import useAuth from "../hooks/useAuth";
import { DASHBOARD_ROUTES, dashboardRoute } from "../utils/constants";

import PublicLayout from "../components/public/PublicLayout";
import Landing from "../pages/public/Landing";
import { Features, HowItWorks, ForCreators, ForStudios, About } from "../pages/public/MarketingPages";

function PublicAuthRoute({ children }) {
  const location = useLocation();
  const returnTo = shareReturnFromSearch(location.search);
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to={returnTo || dashboardRoute(user.role)} replace /> : children;
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
        <Route path="/sharing/:token" element={<SharedGallery />} />
        {Object.entries(DASHBOARD_ROUTES).map(([role, path]) => (
          <Route key={role} element={<RoleRoute role={role} />}>
            {role === "owner" ? (
              <Route element={<OwnerOnboardingRoute />}>
                <Route path="/owner/live-pose" element={<LivePoseGuide />} />
                <Route path="/owner/projects" element={<Projects />} />
                <Route path="/owner/projects/create" element={<CreateProject />} />
                <Route path="/owner/projects/:projectId" element={<ProjectDetails />} />
                <Route path="/owner/profile" element={<OwnerProfile />} />
                <Route path="/owner/settings" element={<OwnerSettings />} />
                <Route path="/owner/studio-setup" element={<StudioSetup />} />
                <Route path="/owner/subscription" element={<SubscriptionSelection />} />
                <Route path="/owner/account-history" element={<OwnerAccountHistory />} />
                <Route path="/owner/ai/generate" element={<OwnerAIGenerator />} />
                <Route path="/owner/ai/gallery" element={<OwnerAIResults />} />
                <Route path={path} element={<OwnerDashboard />} />
              </Route>
            ) : (
              <>
                <Route path={`/${role}/profile`} element={role === "user" ? <UserProfile /> : <AdminProfile />} />
                <Route path={`/${role}/settings`} element={role === "user" ? <UserSettings /> : <AdminSettings />} />
                <Route path={path} element={role === "user" ? <UserDashboard /> : <AdminDashboard />} />
                {role === "user" && (
                  <>
                    <Route path="/user/live-pose" element={<LivePoseGuide />} />
                    <Route path="/user/ai" element={<AIGenerator />} />
                    <Route path="/user/gallery" element={<AIResults />} />
                    <Route path="/user/plans/create" element={<CreatePlan />} />
                    <Route path="/user/plans/:planId/edit" element={<EditPlan />} />
                    <Route path="/user/plans" element={<MyPlans />} />
                    <Route path="/user/subscription" element={<UserSubscription />} />
                  </>
                )}
              </>
            )}
          </Route>
        ))}
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
