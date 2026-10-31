import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import AdminLayout from '../../components/layout/AdminLayout';
import Button from '../../components/common/Button';
import { getAdminSummary, getAdminOwners, getAdminOwner, getAdminOwnerPhoto } from '../../services/adminService';
import { ownerError, utcDate, watchSubscriptionRefresh } from '../../utils/subscription';
import '../../styles/account.css';

export const onboardingLabel = status => ({ pending_studio: 'Pending Studio', pending_plan: 'Pending Plan', completed: 'Completed' }[status] || 'Unknown');

export function AdminMetrics({ summary, error }) {
  return <section className="account-grid admin-summary" aria-label="System totals" aria-busy={!summary && !error}>
    {[['normal_users', 'Normal Users'], ['studio_owners', 'Studio Owners']].map(([key, label]) => <div className="account-card admin-summary-card" key={key}>
      <h2>{label}</h2><p className={summary ? 'admin-summary-count' : 'admin-summary-state'}>{summary ? summary[key].toLocaleString() : error ? 'Unavailable' : 'Loading…'}</p>
    </div>)}
  </section>;
}

export function OwnerFacts({ owner }) {
  const studio = owner.studio;
  return <><h3>{owner.name}</h3><dl className="account-details">
    <div><dt>Registered email</dt><dd>{owner.email}</dd></div><div><dt>Joined</dt><dd>{utcDate(owner.created_at)}</dd></div>
    <div><dt>Studio name</dt><dd>{studio?.studio_name || 'Not provided'}</dd></div><div><dt>Studio phone</dt><dd>{studio?.studio_phone || 'Not provided'}</dd></div>
    <div><dt>Address and city</dt><dd>{[studio?.studio_address, studio?.studio_city].filter(Boolean).join(', ') || 'Not provided'}</dd></div>
    <div><dt>Onboarding status</dt><dd>{onboardingLabel(owner.onboarding_status)}</dd></div>
    <div><dt>Subscription status</dt><dd>{owner.subscription_status.replaceAll('_',' ')}</dd></div>
    <div><dt>Current plan</dt><dd>{owner.subscription?.plan || (owner.subscription_status === 'unavailable' ? 'Unavailable' : 'Not selected')}</dd></div>
    <div><dt>Credits remaining</dt><dd>{owner.subscription ? owner.subscription.remaining_credits : 'Unavailable'}</dd></div>
    <div><dt>Credit period ends</dt><dd>{utcDate(owner.subscription?.period_end)}</dd></div>
  </dl>{studio?.studio_description && <p className="studio-description">{studio.studio_description}</p>}
  {owner.subscription_status === 'unavailable' && <p>Subscription information is unavailable. The required migration or subscription configuration may not be ready.</p>}</>;
}
function OwnerDetail({ id, close }) {
  const [owner,setOwner]=useState(null), [error,setError]=useState(''), [photo,setPhoto]=useState(''), [photoError,setPhotoError]=useState(''), [retry,setRetry]=useState(0);
  useEffect(()=>{
    const controller=new AbortController(); let url;
    setOwner(null); setError(''); setPhoto(''); setPhotoError('');
    getAdminOwner(id,controller.signal).then(async data=>{
      if(controller.signal.aborted) return; setOwner(data);
      if(data.has_photo) {
        try { const blob=await getAdminOwnerPhoto(id,controller.signal); if(!controller.signal.aborted) { url=URL.createObjectURL(blob);setPhoto(url); } }
        catch { if(!controller.signal.aborted) setPhotoError('Studio photo could not be loaded.'); }
      }
    }).catch(e=>{if(!controller.signal.aborted) setError(ownerError(e,'Unable to load owner details.'));});
    return ()=>{controller.abort();if(url) URL.revokeObjectURL(url);};
  },[id,retry]);
  useEffect(() => watchSubscriptionRefresh(owner?.subscription?.period_end, () => setRetry(n => n + 1)), [owner]);
  return <section className="account-card" aria-label="Studio Owner details"><div className="account-heading"><h2>Studio Owner details</h2><button className="account-secondary" onClick={close}>Close details</button></div>
    {!owner && !error && <p role="status">Loading owner details…</p>}
    {(error || photoError) && <div className="account-error" role="alert">{error || photoError}<button className="account-secondary" onClick={()=>setRetry(n=>n+1)}>Retry</button></div>}
    {owner && <><OwnerFacts owner={owner} />{photo ? <img className="studio-photo-preview" src={photo} alt={`${owner.studio?.studio_name || owner.name} studio`} /> : <p>{!owner.photo_available ? 'Studio photos are unavailable until the photo migration is applied.' : owner.has_photo && !photoError ? 'Loading studio photo…' : 'No studio photo available.'}</p>}</>}
  </section>;
}
export default function Dashboard() {
  const [summary,setSummary]=useState(null),[summaryError,setSummaryError]=useState('');
  const [data,setData]=useState(null),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  const [q,setQ]=useState(''),[filter,setFilter]=useState('');
  const [query,setQuery]=useState({page:1,page_size:20}),[selected,setSelected]=useState(null);
  useEffect(()=>{const c=new AbortController();setSummary(null);setSummaryError('');getAdminSummary(c.signal).then(d=>{if(!c.signal.aborted)setSummary(d);}).catch(e=>{if(!c.signal.aborted)setSummaryError(ownerError(e,'Unable to load totals.'));});return ()=>c.abort();},[retry]);
  useEffect(()=>{const c=new AbortController();setData(null);setError('');getAdminOwners(query,c.signal).then(d=>{if(!c.signal.aborted)setData(d);}).catch(e=>{if(!c.signal.aborted)setError(ownerError(e,'Unable to load Studio Owners.'));});return ()=>c.abort();},[query,retry]);
  return <AdminLayout><div className="account-page">
    <AdminMetrics summary={summary} error={summaryError} />
    {summaryError && <p className="account-error" role="alert">{summaryError}<button className="account-secondary" onClick={()=>setRetry(n=>n+1)}>Retry</button></p>}
    <section id="studio-owners" aria-labelledby="admin-users-heading"><h2 id="admin-users-heading" className="admin-section-title">Studio Owner management</h2>
      <p>Read-only studio and account information. Studio onboarding does not require Admin approval.</p>
      <form className="admin-table-toolbar admin-owner-filters" onSubmit={e=>{e.preventDefault();setSelected(null);setQuery({page:1,page_size:20,q:q.trim(),...(filter?{onboarding:filter}:{})});}}>
        <div className="admin-search"><Search size={16} /><input aria-label="Search Studio Owners" placeholder="Name, email, studio or city" maxLength={100} value={q} onChange={e=>setQ(e.target.value)} /></div>
        <label>Onboarding<select value={filter} onChange={e=>setFilter(e.target.value)}><option value="">All statuses</option><option value="pending_studio">Pending Studio</option><option value="pending_plan">Pending Plan</option><option value="completed">Completed</option></select></label><Button type="submit" disabled={!data && !error}>Search</Button><button className="account-secondary" type="button" disabled={!q && !filter && !query.q && !query.onboarding} onClick={()=>{setQ('');setFilter('');setSelected(null);setQuery({page:1,page_size:20});}}>Clear filters</button>
      </form>
      {error && <div className="account-error" role="alert">{error}<button className="account-secondary" onClick={()=>setRetry(n=>n+1)}>Retry</button></div>}
      {!data && !error && <p role="status">Loading Studio Owners…</p>}
      {data && <><div className="admin-table-scroll" role="region" aria-label="Studio Owners" tabIndex={0}><table className="admin-users-table admin-owner-table"><caption className="admin-visually-hidden">Real Studio Owner records</caption><thead><tr>{['Owner','Registered email','Studio','City','Onboarding','Joined','Details'].map(h=><th key={h} scope="col">{h}</th>)}</tr></thead><tbody>
        {data.items.map(owner=><tr key={owner.id}><td title={owner.name}>{owner.name}</td><td title={owner.email}>{owner.email}</td><td title={owner.studio?.studio_name}>{owner.studio?.studio_name || 'Not provided'}</td><td title={owner.studio?.studio_city}>{owner.studio?.studio_city || 'Not provided'}</td><td><span className="admin-onboarding-status">{onboardingLabel(owner.onboarding_status)}</span></td><td>{utcDate(owner.created_at)}</td><td><button className="account-secondary" aria-label={`View details for ${owner.name}`} onClick={()=>setSelected(owner.id)}>View Details</button></td></tr>)}
        {!data.items.length && <tr><td colSpan={7} className="admin-empty-cell">No Studio Owners match the current filters. Clear the filters to see all owners.</td></tr>}
      </tbody></table></div><div className="admin-owner-pagination"><span role="status">{data.total} matching owners · Page {data.page} of {Math.max(1, Math.ceil(data.total / data.page_size))}</span><button className="account-secondary" disabled={data.page<=1} onClick={()=>{setSelected(null);setQuery(v=>({...v,page:v.page-1}));}}>Previous</button><button className="account-secondary" disabled={data.page*data.page_size>=data.total || data.page>=10000} onClick={()=>{setSelected(null);setQuery(v=>({...v,page:v.page+1}));}}>Next</button></div></>}
    </section>{selected && <OwnerDetail key={selected} id={selected} close={()=>setSelected(null)} />}
  </div></AdminLayout>;
}
