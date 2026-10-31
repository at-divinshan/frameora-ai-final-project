import api from './api';
export const getAdminSummary = signal => api.get('/admin/summary', { signal }).then(r => r.data);
export const getAdminOwners = (params, signal) => api.get('/admin/owners', { params, signal }).then(r => r.data);
export const getAdminOwner = (id, signal) => api.get(`/admin/owners/${id}`, { signal }).then(r => r.data);
export async function getAdminOwnerPhoto(id, signal) {
  const { data } = await api.get(`/admin/owners/${id}/photo`, { responseType:'blob', signal });
  if (data.type !== 'image/png') throw new Error('Invalid photo response');
  return data;
}
