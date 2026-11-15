import {useEffect, useState} from 'react';
import AdminLayout from '../../components/layout/AdminLayout';
import {getAdminPayments, getAdminPayment} from '../../services/adminPaymentService';
import {adminUserError} from '../../services/adminUserService';
import '../../styles/account.css';
import '../../styles/admin-payments.css';
const value = v => v ?? 'Not available';
const date = v => v ? new Date(v.endsWith('Z') ? v : `${v}Z`).toLocaleString() : 'Not available';
export function formatPaymentAmount(amount, currency) {
  if (amount == null || String(amount).trim() === '' || !Number.isFinite(Number(amount))) return 'Not available';
  const number = new Intl.NumberFormat('en-LK', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(Number(amount));
  return currency ? `${currency.toUpperCase()} ${number}` : `${number} (currency unavailable)`;
}
const statusLabels = {succeeded:'Succeeded', pending:'Pending', expired:'Expired', failed:'Failed', refunded:'Refunded', partially_refunded:'Partially refunded', disputed:'Disputed', review:'Review'};
export function PaymentStatus({status, checkout = false}) {
  const known = Object.hasOwn(statusLabels, status);
  return <span className={`payment-status payment-status--${known ? status : 'unknown'}`}>{known ? statusLabels[status] : value(status)}{checkout ? ' checkout' : ''}</span>;
}
export function PaymentSummary({summary}) {
  return <div className="account-grid payment-summary">{[['Successful sandbox payments',summary.successful],['Sandbox revenue',formatPaymentAmount(summary.revenue,'LKR')],['Pending payments / checkouts',summary.pending],['Failed / refunded / disputed',summary.failed_refunded]].map(([label,n])=><article className="account-card" key={label}><h2>{label}</h2><p>{value(n)}</p></article>)}</div>;
}
export function PaymentRows({items, onSelect}) {
  if (!items.length) return <p className="account-notice payment-empty" role="status">No payment records found. Try adjusting your filters.</p>;
  return <div className="payment-table-scroll" role="region" aria-label="Payment transactions" tabIndex={0}><table className="payment-table"><caption className="payment-sr-only">Payment transactions — scroll horizontally to view all columns.</caption><thead><tr>{['Date','Customer','Role','Plan','Amount','Status','Stripe reference','Details'].map(x=><th scope="col" className={x==='Amount' ? 'payment-amount' : undefined} key={x}>{x}</th>)}</tr></thead><tbody>{items.map(r=><tr key={`${r.kind}-${r.id}`}>
    <td>{date(r.date)}</td><td className="payment-customer"><strong>{r.name}</strong><span>{r.email}</span></td><td>{r.role==='user'?'Normal User':r.role==='owner'?'Studio Owner':r.role}</td><td>{value(r.plan)}</td><td className="payment-amount">{formatPaymentAmount(r.amount,r.currency)}</td><td><PaymentStatus status={r.status} checkout={r.kind==='checkout'}/></td><td className="payment-reference">{value(r.transaction_id)}</td><td><button className="account-secondary" onClick={()=>onSelect(r)}>View Details</button></td>
  </tr>)}</tbody></table></div>;
}
export function PaymentDetail({record:r}) {
  return <section className="account-card payment-detail"><h2>Payment details</h2><p>{r.name} · {r.email} · {r.role}</p>
    <p>Plan: {value(r.plan)} · Status: <PaymentStatus status={r.status}/> · {formatPaymentAmount(r.amount,r.currency)}</p>
    <p>Stripe reference: {value(r.transaction_id)}</p><p>Recorded verification: {date(r.verified_at)} · Mode: {r.livemode===false?'Sandbox':r.livemode===true?'Live':'Not available'}</p>
    <p>Subscription: {r.subscription ? `${r.subscription.status} · ${date(r.subscription.start_date)} — ${date(r.subscription.end_date)}` : 'Not available'}</p>
    <p>Recorded credits allocated: {value(r.allocation?.credits)}</p><p>Allocation revoked: {date(r.allocation?.revoked_at)}</p>
    <h3>Recorded refund/dispute and fulfillment events</h3>{r.events.length ? <ul>{r.events.map((e,i)=><li key={i}>{e.event_type} · {e.outcome} · {date(e.processed_at)}{e.amount_minor != null ? ` · ${formatPaymentAmount(e.amount_minor/100,e.currency)}`:''}</li>)}</ul>:<p>No recorded events.</p>}
  </section>;
}
export default function Payments() {
  const [filters,setFilters]=useState({}),[page,setPage]=useState(1),[refresh,setRefresh]=useState(0);
  const [data,setData]=useState(null),[error,setError]=useState(''),[selected,setSelected]=useState(null),[detail,setDetail]=useState(null),[detailError,setDetailError]=useState('');
  useEffect(()=>{const c=new AbortController();setData(null);setError('');getAdminPayments({...filters,page},c.signal).then(r=>{if(!c.signal.aborted)setData(r);}).catch(e=>{if(!c.signal.aborted)setError(adminUserError(e));});return()=>c.abort();},[filters,page,refresh]);
  useEffect(()=>{const c=new AbortController();setDetail(null);setDetailError('');if(selected)getAdminPayment(selected.kind,selected.id,c.signal).then(r=>{if(!c.signal.aborted)setDetail(r);}).catch(e=>{if(!c.signal.aborted)setDetailError(adminUserError(e));});return()=>c.abort();},[selected,refresh]);
  function change(key,v){setFilters(f=>({...f,[key]:v||undefined}));setPage(1);setSelected(null);}
  return <AdminLayout title="Payments"><section className="account-page admin-payments"><header className="account-heading"><h1>Payments</h1><button className="account-secondary" onClick={()=>setRefresh(n=>n+1)}>Refresh</button></header>
    <div className="account-card account-grid payment-filters">
      <label>Role<select onChange={e=>change('role',e.target.value)}><option value="">All roles</option><option value="user">Normal User</option><option value="owner">Studio Owner</option></select></label>
      <label>Plan<select onChange={e=>change('plan',e.target.value)}><option value="">All plans</option>{['basic','trial','starter','pro','growth','unlimited'].map(p=><option key={p}>{p}</option>)}</select></label>
      <label>Status<select onChange={e=>change('status',e.target.value)}><option value="">All statuses</option>{['succeeded','pending','expired','failed','refunded','partially_refunded','disputed','review'].map(p=><option key={p}>{p}</option>)}</select></label>
      <label>From (UTC)<input type="date" onChange={e=>change('date_from',e.target.value)}/></label><label>Through (UTC)<input type="date" onChange={e=>change('date_to',e.target.value)}/></label>
    </div>
    {error && <p className="account-error" role="alert">{error}</p>}{!data&&!error&&<p className="account-notice" role="status">Loading payments…</p>}
    {data&&<><PaymentSummary summary={data.summary}/>
      <p>Summaries follow filters. Revenue includes recorded, verified successful sandbox LKR payments; reversed payments are excluded. Checkout creation is not payment confirmation.</p>
      <PaymentRows items={data.items} onSelect={setSelected}/><p>Page {page} · {data.total} records</p><button className="account-secondary" disabled={page<=1} onClick={()=>setPage(p=>p-1)}>Previous</button><button className="account-secondary" disabled={page*data.page_size>=data.total} onClick={()=>setPage(p=>p+1)}>Next</button></>}
    {selected&&<button className="account-secondary" onClick={()=>setSelected(null)}>Close details</button>}{selected&&!detail&&!detailError&&<p className="account-notice" role="status">Loading payment details…</p>}{detailError&&<p className="account-error" role="alert">{detailError}</p>}{detail&&<PaymentDetail record={detail}/>}
  </section></AdminLayout>;
}
