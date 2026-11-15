import api from './api';
import { getProjects } from './projectService';

export const getProjectShareLinks = (id, signal) => api.get(`/owner/projects/${id}/share-links`, { signal }).then(r => r.data);
export const createProjectShareLink = (id, values) => api.post(`/owner/projects/${id}/share-links`, values).then(r => r.data);
export const deactivateProjectShareLink = (id, linkId) => api.delete(`/owner/projects/${id}/share-links/${linkId}`);
export const getSharedGallery = (token, signal) => api.get(`/sharing/${encodeURIComponent(token)}`, { signal }).then(r => r.data);
export const getSharedImage = (token, id, signal) => api.get(`/sharing/${encodeURIComponent(token)}/images/${id}`, { responseType: 'blob', signal }).then(r => r.data);

export function shareLinkStatus(link, now = Date.now()) {
  if (!link.is_active) return 'Inactive';
  const expiry = link.expires_at && new Date(/[Zz]|[+-]\d\d:\d\d$/.test(link.expires_at) ? link.expires_at : `${link.expires_at}Z`).getTime();
  return expiry && expiry <= now ? 'Expired' : 'Active';
}
export async function getShareUsage(signal) {
  const projects = await getProjects(signal);
  const lists = await Promise.all(projects.map(p => getProjectShareLinks(p.id, signal)));
  return lists.flat().filter(link => shareLinkStatus(link) === 'Active').length;
}
export function sharingError(error) {
  if ([404, 410].includes(error.response?.status)) return 'This share link is invalid, expired, or deactivated. Ask the studio for a new link.';
  if (error.response?.status === 403) return 'You do not have access to this shared gallery.';
  return 'Unable to load the shared gallery. Please try again.';
}

export const publishProjectPhase = (projectId, linkId, phaseId) => api.put(`/owner/projects/${projectId}/share-links/${linkId}/phases/${phaseId}`).then(r => r.data);

export const getOwnerShareLinks = (projectId, before, signal) => api.get('/owner/share-links', {params:{project_id:projectId || undefined,before},signal}).then(r=>r.data);
export const setShareLinkActive = (projectId, linkId, isActive) => api.patch(`/owner/projects/${projectId}/share-links/${linkId}`,{is_active:isActive}).then(r=>r.data);

export function cachedShareUrl(storage, ownerId, projectId, linkId, origin) {
  try {
    const value=JSON.parse(storage.getItem(`frameora.photoshoot.share.${ownerId}.${projectId}`))?.[linkId];
    if (typeof value !== 'string') return null;
    const url=new URL(value);
    return url.origin === origin && /^\/sharing\/[A-Za-z0-9_-]{43}$/.test(url.pathname) && !url.search && !url.hash ? url.href : null;
  } catch { return null; }
}
