import api from './api';

const onboardingRequests = new Map();

export function getOnboarding(userId) {
  if (onboardingRequests.has(userId)) return onboardingRequests.get(userId);
  const request = api.get('/owner/onboarding').then(response => response.data)
    .finally(() => onboardingRequests.delete(userId));
  onboardingRequests.set(userId, request);
  return request;
}

export async function saveStudio(data) {
  const response = await api.put('/owner/studio', data);
  return response.data;
}

export const getPlans = () => api.get('/owner/plans').then(r => r.data.plans);
export const getSubscription = () => api.get('/owner/subscription').then(r => r.data);
export function activatePlan(plan, idempotencyKey) {
  if (!['basic', 'trial'].includes(plan)) throw new Error('Plan activation unavailable');
  return api.post(`/owner/subscription/${plan}`, { idempotency_key: idempotencyKey }).then(r => r.data);
}
export const getStudioPhotoStatus = () => api.get('/owner/studio/photo-status').then(r => r.data);
export const uploadStudioPhoto = file => api.post('/owner/studio/photo', file, { headers: { 'Content-Type': file.type } }).then(r => r.data);
export const removeStudioPhoto = () => api.delete('/owner/studio/photo').then(r => r.data);
export async function getStudioPhoto() {
  const { data } = await api.get('/owner/studio/photo', { responseType: 'blob' });
  if (data.type !== 'image/png') throw new Error('Invalid photo response');
  return data;
}
