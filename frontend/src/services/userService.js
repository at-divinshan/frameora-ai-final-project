import api from "./api";

export async function getProfile(signal) {
  return (await api.get("/users/me", { signal })).data;
}

export async function updateProfile({ name, phone }) {
  return (await api.patch("/users/me", { name: name.trim(), phone: phone.trim() || null })).data;
}

export async function getPrivacy(signal) {
  return (await api.get("/users/me/privacy", { signal })).data;
}

export async function updatePrivacy(values, role) {
  const data = {
    photography_plans_default: values.photography_plans_default,
    ai_images_default: values.ai_images_default,
  };
  if (role !== "admin") data.profile_visibility = values.profile_visibility;
  return (await api.patch("/users/me/privacy", data)).data;
}

export async function getProfilePicture(signal) {
  try {
    const response = await api.get("/users/me/picture", { signal, responseType: "blob" });
    if (response.data.type !== "image/png" || response.data.size > 2 * 1024 * 1024) {
      throw new Error("Unexpected picture response");
    }
    return response.data;
  } catch (error) {
    if (error.response?.status === 404) return null;
    throw error;
  }
}

export async function uploadProfilePicture(file) {
  return (await api.post("/users/me/picture", file, {
    headers: { "Content-Type": file.type },
    transformRequest: [(body) => body],
  })).data;
}

export async function removeProfilePicture() {
  return (await api.delete("/users/me/picture")).data;
}

export function profileError(error) {
  const status = error.response?.status;
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "This change is not permitted for your account.";
  if (status === 413) return "Choose an image no larger than 5 MiB.";
  if (status === 415) return "Choose a JPEG or PNG image.";
  if (status === 422) return "Check your entries. Images must be valid, non-animated JPEG or PNG files of at most 16 megapixels.";
  if (status === 429) return "Too many attempts. Please wait before trying again.";
  if (status === 503) return "This service is temporarily unavailable. Please try again.";
  return "Unable to complete your request. Please try again.";
}

export function profileFieldErrors(error) {
  const detail = error.response?.data?.detail;
  if (!Array.isArray(detail)) return {};
  return Object.fromEntries(detail.flatMap((item) => {
    const key = item.loc?.at(-1);
    return ["name", "phone"].includes(key) && typeof item.msg === "string" ? [[key, item.msg]] : [];
  }));
}
