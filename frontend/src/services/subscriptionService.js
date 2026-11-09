import api from "./api";

export const getAccountHistoryPlans = signal =>
  api.get("/owner/account-history/photography-plans", { signal }).then(({ data }) => data);

export const getAccountHistoryGenerations = (signal, before) =>
  api.get("/owner/account-history/generations", { signal, params: { before } }).then(({ data }) => data);

export async function getAccountHistoryImage(id, signal) {
  const { data } = await api.get(`/owner/account-history/images/${id}`, {
    responseType: "blob",
    signal,
  });
  if (data.type !== "image/png") throw new Error("Invalid historical image response.");
  return data;
}