import api from "./api";

export async function loginUser(data) {
  const response = await api.post("/auth/login", data);
  return response.data;
}

export async function registerUser(data) {
  const response = await api.post("/auth/register", data);
  return response.data;
}

export async function requestPasswordReset(email) {
  const response = await api.post("/auth/forgot-password", {
    email,
  });
  return response.data;
}