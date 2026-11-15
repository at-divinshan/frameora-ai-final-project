import { useState } from 'react';
import { Link } from 'react-router-dom';
import DashboardLayout from '../../components/layout/DashboardLayout';
import {exploreSamples, filterExploreSamples} from '../../data/exploreSamples';
import '../../styles/account.css';
import '../../styles/explore.css';

export function ExploreCard({sample}) {
  const [failed,setFailed]=useState(false);
  return <article className="explore-card">
    {sample.available && !failed ? <img src={sample.image} alt={`${sample.title}: ${sample.pose}`} loading="lazy" width="1536" height="1024" onError={()=>setFailed(true)} /> : <div className="explore-missing">Sample image unavailable</div>}
    <div className="explore-card-body"><span className="explore-category">{sample.category}</span><h2>{sample.title}</h2>
      {sample.available ? <><dl>{[['Pose',sample.pose],['Background',sample.background],['Camera angle',sample.camera],['Lighting',sample.lighting]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <details><summary>Style &amp; outfit details</summary><p>{sample.style} photography · {sample.outfit}</p><p>{sample.instructions}</p></details>
      <Link className="user-dashboard-create-button" to={`/user/plans/create?sample=${sample.id}`}>Try with AI</Link></> : <p>{sample.reason}</p>}
    </div>
  </article>;
}
export default function Explore() {
  const [query,setQuery]=useState(''), [category,setCategory]=useState('All');
  const samples=filterExploreSamples(query,category);
  return <DashboardLayout><section className="user-plan-page account-page explore-page">
    <header className="account-heading"><div><p className="explore-eyebrow">Find your next photoshoot</p><h1>Explore inspiration</h1><p>Start with a scene you love. Make the plan your own.</p></div></header>
    <div className="explore-filters"><div className="form-field"><label htmlFor="explore-search">Search inspiration</label><input id="explore-search" type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Try balloons, garden or warm lighting…" /></div>
      <div className="form-field"><label htmlFor="explore-category">Category</label><select id="explore-category" value={category} onChange={e=>setCategory(e.target.value)}>{['All',...new Set(exploreSamples.map(s=>s.category))].map(c=><option key={c}>{c}</option>)}</select></div></div>
    <p role="status">{samples.length} inspiration {samples.length===1?'idea':'ideas'}</p>
    <div className="explore-grid">{samples.map(s=><ExploreCard key={s.id} sample={s}/>)}</div>
    {!samples.length && <div className="user-dashboard-empty-state">No matching ideas. Try another search or category.<button className="account-secondary" onClick={()=>{setQuery('');setCategory('All');}}>Clear filters</button></div>}
  </section></DashboardLayout>;
}
