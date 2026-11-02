import api from "./api";

export async function createPlan(values) {
  const { data } = await api.post("/plans", values);
  return data;
}

export async function getMyPlans(signal) {
  const { data } = await api.get("/plans", { signal });
  return data;
}