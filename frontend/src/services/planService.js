import api from "./api";

export async function createPlan(values) {
  const { data } = await api.post("/plans", values);
  return data;
}

export async function getMyPlans(signal) {
  const { data } = await api.get("/plans", { signal });
  return data;
}

export async function getMyPlan(planId, signal) {
  const { data } = await api.get(`/plans/${planId}`, { signal });
  return data;
}

export async function updatePlan(planId, values) {
  const { data } = await api.patch(`/plans/${planId}`, values);
  return data;
}

export async function deletePlan(planId) {
  await api.delete(`/plans/${planId}`);
}

export function getPlanErrorMessage(error, action = "save") {
  switch (error.response?.status) {
    case 401:
      return "Your session has expired. Please sign in again.";
    case 403:
      return "You don’t have permission to change this photography plan.";
    case 404:
      return "This photography plan could not be found. It may have been deleted.";
    case 409:
      return "This plan can’t be deleted because generation history is linked to it.";
    case 503:
      return "The service is temporarily unavailable. Please try again later.";
    default: {
      const detail = error.response?.data?.detail;
      if (typeof detail === "string") return detail;
      return `Unable to ${action} your photography plan. Please try again.`;
    }
  }
}