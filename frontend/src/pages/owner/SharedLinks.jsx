import {useEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import AccountLayout from '../../components/layout/AccountLayout';
import useAuth from '../../hooks/useAuth';
import {getOwnerShareLinks,setShareLinkActive,publishProjectPhase,cachedShareUrl,shareLinkStatus} from '../../services/shareService';
import {utcDate} from '../../utils/subscription';
import '../../styles/account.css';

export function ManagedShareLink({link,url,busy,onStatus,onPublish,onCopy}) {
  const [phase,setPhase]=useState('');
  const status=shareLinkStatus(link);
  const expired=link.expires_at && new Date(/[Zz]|[+-]\d\d:\d\d$/.test(link.expires_at)?link.expires_at:`${link.expires_at}Z`).getTime() <= Date.now();
  return <article className="account-card">
    <h2>{link.project_name}{link.project_archived ? ' (archived)' : ''} · Link #{link.id}</h2>
    <p role="status">{status} · Created {utcDate(link.created_at)} · Expires {link.expires_at?utcDate(link.expires_at):'Never'}</p>
    {link.manageable === false && <p>This legacy link has no project association. Project-based activation and phase publication are unavailable.</p>}
    <p>Original batch #{link.generation_id} remains included when this link is active.</p>
    <p>Published phases: {link.published_phases.length?link.published_phases.map(p=>`Phase ${p.number}`).join(', '):'No numbered phases published'}</p>
    {url ? <div className="form-field"><label htmlFor={`link-url-${link.id}`}>Customer link URL</label><div className="input-wrapper"><input id={`link-url-${link.id}`} value={url} readOnly onFocus={e=>e.target.select()}/></div></div> : <p>URL unavailable in this browser session. Existing customer links still work; the server stores only a secure token hash.</p>}
    <div className="photoshoot-actions">
      <button className="account-secondary" disabled={!url || busy} onClick={()=>onCopy(url)}>Copy Link</button>
      <button className="account-secondary" disabled={busy || link.manageable === false || (!link.is_active && (expired || link.project_archived))} onClick={()=>onStatus(link,!link.is_active)}>{link.is_active?'Deactivate':'Activate'}</button>
      {link.project_id && !link.project_archived && <Link className="account-secondary" to={`/owner/projects/${link.project_id}#share-customer`}>Open project</Link>}
    </div>
    {link.unpublished_phases.length>0 && status==='Active' && !link.project_archived && <form className="form-field" onSubmit={event=>{event.preventDefault();if(phase)onPublish(link,Number(phase));}}>
      <label htmlFor={`phase-${link.id}`}>Publish a completed phase to this link</label>
      <select id={`phase-${link.id}`} value={phase} disabled={busy} onChange={e=>setPhase(e.target.value)}><option value="">Choose an unpublished phase</option>{link.unpublished_phases.map(p=><option key={p.id} value={p.id}>Phase {p.number}</option>)}</select>
      <button className="owner-gradient-button" disabled={busy || !link.unpublished_phases.some(p=>String(p.id)===phase)}>Publish Phase</button>
    </form>}
  </article>;
}

export default function SharedLinks() {
  const {user}=useAuth();
  const [project,setProject]=useState(''),[data,setData]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const [loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[refresh,setRefresh]=useState(0);
  const pending=useRef(false),request=useRef(0);
  useEffect(()=>{
    const controller=new AbortController(),ticket=++request.current;
    setLoading(true);setError('');setData(null);
    getOwnerShareLinks(project,undefined,controller.signal).then(result=>{if(ticket===request.current&&!controller.signal.aborted)setData(result);})
      .catch(e=>{if(!controller.signal.aborted)setError(e.response?.data?.detail || 'Unable to load share links.');})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>{controller.abort();request.current+=1;};
  },[project,refresh]);
  async function more() {
    if(loading || !data?.next_before)return;
    const ticket=++request.current;setLoading(true);setError('');
    try {const result=await getOwnerShareLinks(project,data.next_before);if(ticket===request.current)setData(current=>({...result,items:[...current.items,...result.items]}));}
    catch(e){if(ticket===request.current)setError(e.response?.data?.detail || 'Unable to load more links.');}
    finally {if(ticket===request.current)setLoading(false);}
  }
  async function mutate(action,message) {
    if(pending.current)return;
    pending.current=true;setBusy(true);setError('');setNotice('');
    try {await action();setNotice(message);setRefresh(n=>n+1);}
    catch(e){setError(e.response?.data?.detail || 'Unable to update the link. Refresh and try again.');}
    finally{pending.current=false;setBusy(false);}
  }
  function status(link,active) {
    if(!window.confirm(`${active?'Activate':'Deactivate'} this customer link?`))return;
    mutate(()=>setShareLinkActive(link.project_id,link.id,active),`Link ${active?'activated':'deactivated'}.`);
  }
  function publish(link,phase) {
    if(!window.confirm('Publish this phase to everyone who has this active link?'))return;
    mutate(()=>publishProjectPhase(link.project_id,link.id,phase),'Phase published. Previous images and comments remain available.');
  }
  async function copy(url) {try{await navigator.clipboard.writeText(url);setNotice('Link copied.');}catch{setError('Clipboard unavailable. Select and copy the URL above.');}}
  function url(link){try{return cachedShareUrl(window.sessionStorage,user.id,link.project_id,link.id,window.location.origin);}catch{return null;}}
  return <AccountLayout><section className="account-page user-plan-page">
    <header className="account-heading"><div><h1>Share Links</h1><p>Manage customer access and publish completed project phases.</p></div></header>
    <div className="form-field"><label htmlFor="share-project-filter">Project</label><select id="share-project-filter" disabled={loading || busy} value={project} onChange={e=>{setProject(e.target.value);setNotice('');}}><option value="">All projects</option>{data?.projects.map(p=><option key={p.id} value={p.id}>{p.name}{p.archived?' (archived)':''}</option>)}</select></div>
    <button className="account-secondary" disabled={loading||busy} onClick={()=>setRefresh(n=>n+1)}>Refresh</button>
    {notice&&<p className="account-notice" role="status">{notice}</p>}{error&&<p className="account-error" role="alert">{error}</p>}
    {loading&&<p role="status">Loading share links…</p>}
    {data&&!data.phase_publication_available&&<p role="status">Phase publication is unavailable until migration 010 is applied. Existing links retain their access.</p>}
    {data?.items.map(link=><ManagedShareLink key={link.id} link={link} url={url(link)} busy={busy||loading} onStatus={status} onPublish={publish} onCopy={copy}/>)}
    {data&&!data.items.length&&<p>No share links for this selection. Create links from a project’s sharing section.</p>}
    {data?.next_before&&<button className="account-secondary" disabled={loading||busy} onClick={more}>Load more</button>}
  </section></AccountLayout>;
}
