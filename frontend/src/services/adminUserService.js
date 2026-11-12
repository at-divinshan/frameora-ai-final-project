import api from './api';
export const getAdminUsers=(params,signal)=>api.get('/admin/users',{params,signal}).then(r=>r.data);
export const getAdminUser=(id,signal,payment_page=1)=>api.get(`/admin/users/${id}`,{signal,params:{payment_page}}).then(r=>r.data);
export async function setAdminUserStatus(id,is_active,expected_version){
 const {data}=await api.patch(`/admin/users/${id}/status`,{is_active,expected_version});
 if(data?.id!==id || data.is_active!==is_active || !Number.isInteger(data.status_version) || data.status_version<expected_version){
  const error=new Error('Account status was not confirmed by the server. Refresh before trying again.');
  error.code='STATUS_NOT_CONFIRMED';throw error;
 }
 return data;
}
export function adminUserError(error){
 if(error.code==='STATUS_NOT_CONFIRMED')return error.message;
 if(!error.response)return 'Unable to reach the server. Check your connection and try again.';
 if(error.response?.status===503 && error.response.data?.detail?.code==='ADMIN_USERS_SCHEMA_UNAVAILABLE')return 'The account-status database schema is missing or incompatible. Ask the administrator to check the database configuration and migration status.';
 if(error.response?.status===503)return 'User management is temporarily unavailable. Please try again later; if this continues, ask the administrator to check the backend logs.';
 if(error.response?.status===403)return 'You do not have permission to manage this account.';
 if(error.response?.status===409)return 'The account changed. Refresh its status before trying again.';
 if(error.response?.status===401)return 'Please sign in again.';
 if(error.response?.status>=500)return 'An unexpected server error occurred. Please try again later.';
 return 'Unable to load or update this account. Please try again.';
}
