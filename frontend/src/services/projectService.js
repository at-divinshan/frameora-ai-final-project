import api from './api';

export const getProjects = signal => api.get('/owner/projects', { signal }).then(r => r.data);
export const getProject = (id, signal) => api.get(`/owner/projects/${id}`, { signal }).then(r => r.data);
export const createProject = values => api.post('/owner/projects', values).then(r => r.data);
export const updateProject = (id, values) => api.patch(`/owner/projects/${id}`, values).then(r => r.data);

export function projectError(error, action = 'load') {
  const status = error.response?.status;
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'You do not have permission to access this project.';
  if (status === 404) return 'This project could not be found.';
  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (status === 422) return 'Check your project details and try again.';
  return `Unable to ${action} the project. Please try again.`;
}

export const getProjectPlans = (id, signal) => api.get(`/owner/projects/${id}/photography-plans`, { signal }).then(r => r.data);
export const createProjectPlan = (id, values) => api.post(`/owner/projects/${id}/photography-plans`, values).then(r => r.data);
export const linkProjectPlan = (id, planId) => api.post(`/owner/projects/${id}/photography-plans/${planId}`).then(r => r.data);
export async function getProjectGenerations(id, signal) {
  const items = []; let before;
  do {
    const {data} = await api.get(`/owner/projects/${id}/ai/generations`, {signal, params: {before}});
    items.push(...data);
    if (data.length < 20) break;
    const next = data.at(-1).id;
    if (before != null && next >= before) throw new Error('Invalid gallery pagination');
    before = next;
  } while (!signal?.aborted);
  return items;
}
export const eligibleProjectPlans = plans => plans.filter(plan => plan.project_id == null);
