import api from './api';
export const getComments = (token, id, signal) => api.get(`/sharing/${encodeURIComponent(token)}/images/${id}/comments`, { signal }).then(r => r.data);
export const addComment = (token, id, data) => api.post(`/sharing/${encodeURIComponent(token)}/images/${id}/comments`, data).then(r => r.data);
export const getFeedback = (project, signal) => api.get(`/owner/projects/${project}/feedback`, { signal }).then(r => r.data);
export const updateFeedback = (project, id, data) => api.patch(`/owner/projects/${project}/feedback/${id}`, data).then(r => r.data);
export function feedbackError(error) {
  const status = error.response?.status;
  if (status === 503) return 'Comments are not available yet. Please try again later.';
  if (status === 404) return 'This image or share link is no longer available.';
  if (status === 401) return 'Please sign in again.';
  if (status === 422) return 'Enter a comment of 1–2,000 characters without control characters.';
  if (status === 409) return 'The submission could not be confirmed. Retry your unchanged comment.';
  return 'Unable to save or load feedback. Please try again.';
}
