import api from './api';
export const getAdminPayments = (params, signal) => api.get('/admin/payments', {params, signal}).then(r=>r.data);
export const getAdminPayment = (kind, id, signal) => api.get(`/admin/payments/${kind}/${id}`, {signal}).then(r=>r.data);
