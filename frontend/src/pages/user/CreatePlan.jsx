import { useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import DashboardLayout from '../../components/layout/DashboardLayout';
import PlanForm, {mapPlanToFormValues} from '../../components/photography/PlanForm';
import {createPlan} from '../../services/planService';
import useAuth from '../../hooks/useAuth';
import {getExploreSample,samplePlan} from '../../data/exploreSamples';
import {readDraft,writeSession,planContextKey,validPlanId,sessionStore} from '../../utils/exploreFlow';
import '../../styles/explore.css';

function NewPlan({sample,userId,invalidSample}) {
  const navigate=useNavigate();
  const draftKey=`frameora.explore.draft.${userId}.${sample?.id || 'new'}`;
  const [draft]=useState(()=>readDraft(sessionStore(),draftKey,mapPlanToFormValues(sample ? samplePlan(sample) : {})));
  const values=useRef(draft.values), pending=useRef(false);
  const [mode,setMode]=useState(draft.mode), [action,setAction]=useState('save');
  const [submitting,setSubmitting]=useState(false);
  const [storageNotice,setStorageNotice]=useState('');
  function persist(nextMode=mode) {
    if (!writeSession(sessionStore(),draftKey,{values:values.current,mode:nextMode})) setStorageNotice('Draft storage is unavailable. Keep this page open until you save.');
  }
  async function submit(payload) {
    if (pending.current) return;
    pending.current=true;setSubmitting(true);
    try {
      const created=await createPlan(payload);
      const id=validPlanId(created.id);
      if (!id) throw new Error('The saved plan could not be confirmed. Check My Plans before retrying.');
      if (sample) writeSession(sessionStore(),planContextKey(userId,id),{sampleId:sample.id,mode});
      try {window.sessionStorage.removeItem(draftKey);} catch { /* Saving itself succeeded. */ }
      if (action === 'generate') {
        const query=new URLSearchParams({plan:id});
        if (sample) {query.set('sample',sample.id);query.set('referenceMode',mode);}
        navigate(`/user/ai?${query}`,{replace:true});
      } else navigate('/user/plans',{replace:true,state:{planCreated:true}});
    } finally {pending.current=false;setSubmitting(false);}
  }
  return <section className="user-plan-page account-page plan-create-page" aria-labelledby="create-plan-heading">
    <div className="account-heading"><div><h1 id="create-plan-heading">Create Photography Plan</h1><p>{sample ? `Inspired by ${sample.title}. Edit any detail before saving.` : 'Capture the details for your upcoming photography session.'}</p></div><Link className="account-secondary" to="/user/plans">My Plans</Link></div>
    {invalidSample && <p role="status">That inspiration is unavailable. You can create a plan from scratch or <Link to="/user/explore">browse Explore</Link>.</p>}
    {storageNotice && <p role="status">{storageNotice}</p>}
    <div className="account-card user-plan-form-card">
      {sample && <fieldset className="explore-options" disabled={submitting}><legend>How would you like to use this sample?</legend>
        <label><input type="radio" name="sample-mode" checked={mode==='inspiration'} onChange={()=>{setMode('inspiration');persist('inspiration');}}/>Use Inspiration Only</label>
        <label><input type="radio" name="sample-mode" checked={mode==='scene'} onChange={()=>{setMode('scene');persist('scene');}}/>Use Sample as Background/Scene Reference</label>
        <p>The sample contains people. It is never used as your identity reference. On the generation page, explicitly attach it as a scene; exact scenery and removal of depicted people are not guaranteed.</p>
      </fieldset>}
      <fieldset className="explore-options" disabled={submitting}><legend>Next step</legend>
        <label><input type="radio" name="plan-next" checked={action==='save'} onChange={()=>setAction('save')}/>Save Project — generate later</label>
        <label><input type="radio" name="plan-next" checked={action==='generate'} onChange={()=>setAction('generate')}/>Generate Now — save and continue to AI</label>
        <p>Generation starts only after your confirmation on the AI page, subject to your existing allowance.</p>
      </fieldset>
      <div onChange={event=>{const {name,value}=event.target;if (name && Object.hasOwn(values.current,name)) {values.current={...values.current,[name]:value};persist();}}}>
        <PlanForm compact initialValues={draft.values} onSubmit={submit} submitting={submitting} submitLabel={action==='save'?'Save Project':'Save & Continue to AI'} />
      </div>
    </div>
  </section>;
}
export default function CreatePlan() {
  const [params]=useSearchParams();const {user}=useAuth();
  const sample=getExploreSample(params.get('sample'));
  return <DashboardLayout><NewPlan key={`${user.id}:${sample?.id || 'new'}`} userId={user.id} sample={sample} invalidSample={!!params.get('sample') && !sample}/></DashboardLayout>;
}
