import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AdminLayout from '../layout/AdminLayout';
import UserBillingDetails from './UserBillingDetails';
import { getAdminUsers, getAdminUser, adminUserError } from '../../services/adminUserService';
import '../../styles/account.css';

export default function BillingAccounts({ title }) {
  const [q,setQ]=useState(''), [role,setRole]=useState(''), [page,setPage]=useState(1);
  const [accounts,setAccounts]=useState(null), [selected,setSelected]=useState(null), [detail,setDetail]=useState(null);
  const [error,setError]=useState(''), [detailError,setDetailError]=useState(''), [paymentPage,setPaymentPage]=useState(1), [refresh,setRefresh]=useState(0);
  useEffect(() => {
    const controller=new AbortController();setAccounts(null);setError('');
    getAdminUsers({q,role:role || undefined,page},controller.signal).then(data=>{if(!controller.signal.aborted)setAccounts(data);})
      .catch(e=>{if(!controller.signal.aborted)setError(adminUserError(e));});
    return ()=>controller.abort();
  },[q,role,page,refresh]);
  useEffect(() => {
    const controller=new AbortController();setDetail(null);setDetailError('');
    if(selected)getAdminUser(selected,controller.signal,paymentPage).then(data=>{if(!controller.signal.aborted)setDetail(data);})
      .catch(e=>{if(!controller.signal.aborted)setDetailError(adminUserError(e));});
    return ()=>controller.abort();
  },[selected,paymentPage,refresh]);
  return <AdminLayout title={title}><section className="account-page">
    <header className="account-heading"><h1>{title}</h1><button className="account-secondary" onClick={()=>setRefresh(n=>n+1)}>Refresh</button></header>
    <p>Select an account to view its recorded subscriptions and payment history.</p>
    <p><Link to="/admin/payments">Payments</Link> · <Link to="/admin/subscriptions">Subscriptions</Link></p>
    <div className="account-card account-grid"><label>Search name or email<input className="form-input" value={q} maxLength={100} onChange={e=>{setQ(e.target.value);setPage(1);}} /></label>
    <label>Role<select value={role} onChange={e=>{setRole(e.target.value);setPage(1);}}><option value="">All roles</option><option value="user">Normal User</option><option value="owner">Studio Owner</option></select></label></div>
    {error && <p role="alert">{error}</p>}{!accounts && !error && <p role="status">Loading accounts…</p>}
    {accounts && <><div className="account-grid">{accounts.items.map(user=><button className="account-secondary" key={user.id} onClick={()=>{setSelected(user.id);setPaymentPage(1);}}>{user.name} · {user.email} · {user.role}</button>)}</div>
      {!accounts.total && <p>No accounts found.</p>}
      <button className="account-secondary" disabled={page<=1} onClick={()=>setPage(n=>n-1)}>Previous accounts</button>
      <button className="account-secondary" disabled={page*accounts.page_size>=accounts.total} onClick={()=>setPage(n=>n+1)}>Next accounts</button></>}
    {detailError && <p role="alert">{detailError}</p>}
    {selected && !detail && !detailError && <p role="status">Loading billing details…</p>}
    {detail && <section className="account-card"><h2>{detail.name} · {detail.role}</h2><UserBillingDetails subscription={detail.subscription} payments={detail.payments} onPaymentPage={setPaymentPage} /></section>}
  </section></AdminLayout>;
}
