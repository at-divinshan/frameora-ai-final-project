export const DASHBOARD_ROUTES = Object.freeze({
  user: "/user/dashboard",
  owner: "/owner/dashboard",
  admin: "/admin/dashboard",
});

export function dashboardRoute(role) {
  return DASHBOARD_ROUTES[role] || "/login";
}
