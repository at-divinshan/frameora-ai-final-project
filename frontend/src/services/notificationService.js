import api from './api';
export const getNotifications = (before, signal) => api.get('/notifications', {params: before ? {before} : {},signal}).then(r=>r.data);
export const markNotification = id => api.patch(`/notifications/${id}`,{is_read:true}).then(r=>r.data);
export function withoutNotifications(data, ids) {
  if (!data) return data;
  return {...data,items:data.items.filter(n=>!n.is_read && !ids.has(n.id)),unread_count:Math.max(0,data.unread_count-ids.size)};
}
const pendingReads = new Map();
export function readNotification(id, userId) {
  const key = `${userId}:${id}`;
  if (pendingReads.has(key)) return pendingReads.get(key);
  const publish = (phase, error) => window.dispatchEvent(new CustomEvent('notification-read', {detail:{id,userId,phase,error}}));
  publish('start');
  const request = markNotification(id).then(result=>{publish('success');return result;},error=>{publish('failure',notificationError(error));throw error;}).finally(()=>pendingReads.delete(key));
  pendingReads.set(key,request);
  return request;
}
export const notificationError = e => e.response?.status === 503 ? 'Notifications are not available yet.' : 'Unable to load or update notifications. Please try again.';
export const safeNotificationLink = href => typeof href === 'string' && /^\/(owner\/(projects(?:\/[1-9]\d*(?:#feedback-[1-9]\d*)?)?|subscription|notifications)|user\/notifications)$/.test(href) ? href : null;
