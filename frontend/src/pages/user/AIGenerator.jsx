import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import ImageUploader from "../../components/ai/ImageUploader";
import { preferenceEntries } from "../../components/photography/PlanCard";
import GenerationLoader from "../../components/ai/GenerationLoader";
import { getMyPlans } from "../../services/planService";
import { generateImages, getFreeGenerationEligibility, generationError } from "../../services/aiService";
import useAuth from "../../hooks/useAuth";
import {getExploreSample} from "../../data/exploreSamples";
import {readPlanContext,loadSampleScene,sceneMode,sessionStore} from "../../utils/exploreFlow";
import "../../styles/account.css";
import "../../styles/ai.css";

export function FreeRequestExhaustedNotice() {
  return <section className="user-plan-message free-generation-limit" aria-labelledby="free-generation-limit-heading">
    <h2 id="free-generation-limit-heading">Free Generation Limit Reached</h2>
    <p>Your one free request has been used. Your four generated images remain available in your gallery.</p>
    <Link className="user-dashboard-create-button" to="/user/subscription">View Plans</Link>
    <Link className="free-generation-gallery-link" to="/user/gallery">View your images</Link>
  </section>;
}

export default function AIGenerator() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const {user}=useAuth();
  const sceneRequest=useRef(0);
  const [sceneLoading,setSceneLoading]=useState(false);
  const [attachedSample,setAttachedSample]=useState(null);
  const [sceneError,setSceneError]=useState('');
  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState(params.get("plan") || "");
  const [description, setDescription] = useState("");
  const [reference, setReference] = useState(null);
  const [backgroundReference, setBackgroundReference] = useState(null);
  const [eligibility, setEligibility] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const submitting = useRef(false);
  const requestKey = useRef(null);
  const requestedPlan = params.get("plan") || "";
  const storedContext=readPlanContext(sessionStore(),user.id,planId);
  const sample=getExploreSample(planId === (params.get('plan') || '') ? params.get('sample') : null) || getExploreSample(storedContext?.sampleId);
  const requestedMode=sample?.id === params.get('sample') && planId === params.get('plan') ? sceneMode(params.get('referenceMode')) : sceneMode(storedContext?.mode);
  useEffect(()=>()=>{sceneRequest.current+=1;},[]);
  useEffect(()=>{sceneRequest.current+=1;setSceneLoading(false);},[planId]);
  async function attachScene() {
    if (!sample || backgroundReference || busy || sceneLoading) return;
    const ticket=++sceneRequest.current;
    setSceneLoading(true);setSceneError('');
    try {
      const file=await loadSampleScene(sample.id);
      if (ticket === sceneRequest.current) {setBackgroundReference(current=>current || file);setAttachedSample(sample.id);}
    } catch (err) {if (ticket === sceneRequest.current) setSceneError(err.message);}
    finally {if (ticket === sceneRequest.current) setSceneLoading(false);}
  }
  function changeBackground(file) {sceneRequest.current+=1;setSceneLoading(false);setBackgroundReference(file);setAttachedSample(null);setSceneError('');}
  const selectedPlan = plans.find((plan) => String(plan.id) === planId);
  useEffect(() => { setPlanId(requestedPlan); }, [requestedPlan]);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    Promise.all([getMyPlans(controller.signal), getFreeGenerationEligibility()]).then(([items, state]) => {
      if (active) { setPlans(items); setEligibility(state); setError(""); }
    }).catch((err) => { if (active) setError(generationError(err)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; controller.abort(); };
  }, [attempt]);
  async function submit(event) {
    event.preventDefault();
    if (submitting.current || sceneLoading || !eligibility?.generation_available) return;
    if (!selectedPlan) { setError("Choose one of your saved photography plans."); return; }
    if (reference && (reference.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(reference.type))) {
      setError("Choose a JPEG, PNG or WebP image of at most 5 MiB."); return;
    }
    submitting.current = true;
    setBusy(true); setError("");
    try {
      requestKey.current ||= crypto.randomUUID();
      await generateImages({ idempotencyKey: requestKey.current, planId, description: attachedSample ? `${description}
Use the sample only for scenery, decor and lighting, not the identity or people depicted in it.` : description, reference, backgroundReference });
      navigate("/user/gallery");
    } catch (err) {
      setError(generationError(err));
      try { setEligibility(await getFreeGenerationEligibility()); } catch { setEligibility(null); }
    } finally { submitting.current = false; setBusy(false); }
  }
  return <DashboardLayout><section className="user-plan-page account-page ai-page">
    <div className="user-dashboard-section-heading"><div><h1>AI Image Generation</h1><p>Explore four poses, angles and compositions for your photography plan.</p></div><Link to="/user/gallery" className="user-dashboard-view-all">My Gallery</Link></div>
    <p>Each account includes one successful free request with four images. Facial appearance may vary; exact identity preservation is not guaranteed.</p>
    {eligibility?.paid?.plan && eligibility.paid.plan !== "free" && <p role="status">{eligibility.paid.remaining_credits} paid credits remaining · 4 credits per four-image batch.</p>}
    {loading ? <p role="status">Loading your plans and free request…</p> : <>
      {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
      {!eligibility && <button className="account-secondary" onClick={() => setAttempt(attempt + 1)}>Retry loading</button>}
      {eligibility?.free_request_status === "used" && !eligibility?.paid?.paid_generation_available && <FreeRequestExhaustedNotice />}
      {eligibility?.free_request_status === "in_progress" && <p className="user-plan-message">A request is already in progress. <Link to="/user/gallery">Check your gallery</Link>.</p>}
      {(eligibility?.free_request_status !== "used" || eligibility?.paid?.paid_generation_available) && (!plans.length ? <p><Link to="/user/plans/create">Create a photography plan</Link> to get started.</p> : <form className="account-card ai-form" onSubmit={submit}>
        <fieldset disabled={busy || !eligibility?.generation_available}>
          <div className="form-field"><label htmlFor="ai-plan">Photography plan</label><select id="ai-plan" required value={planId} onChange={(e) => setPlanId(e.target.value)}><option value="">Choose a plan</option>{plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.photography_type} · {plan.environment} · #{plan.id}</option>)}</select></div>
          {selectedPlan && <section className="ai-plan-summary" aria-label="Saved plan details">
            <h2>Using your saved plan</h2>
            <p>{selectedPlan.photography_type} · {selectedPlan.people_count} people · {selectedPlan.environment}</p>
            <dl className="user-plan-preference-list">
              {selectedPlan.location && <div><dt>Location</dt><dd>{selectedPlan.location}</dd></div>}
              {selectedPlan.shoot_datetime && <div><dt>Shoot date/time</dt><dd>{selectedPlan.shoot_datetime.replace("T", " ")}</dd></div>}
              {preferenceEntries(selectedPlan.preferences).map(([key, label, value]) => <div key={key}><dt>{label}</dt><dd>{value}</dd></div>)}
            </dl>
            <p className="ai-note">Your saved requirements are included automatically in every image.</p>
          </section>}
          <div className="form-field"><label htmlFor="ai-description">Additional description (optional)</label><textarea id="ai-description" maxLength={500} rows={3} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Add a short detail for this generation, if needed…" /></div>
          <ImageUploader value={reference} onChange={setReference} disabled={busy} />
          <ImageUploader id="background-reference" background value={backgroundReference} onChange={changeBackground} disabled={busy} />
          {sample && <section className="ai-plan-summary" aria-label="Explore scene reference">
            <h2>{sample.title}</h2><p>{attachedSample ? 'The sample is attached as your scene reference.' : requestedMode === 'scene' ? 'Scene reference requested. Attach it below when ready.' : 'Using inspiration only. No sample image is attached automatically.'}</p>
            <p>This image contains people. It will only be sent as a background/scene reference, never as a person reference. Your own reference uploads stay separate.</p>
            {attachedSample && <p role="status">Sample attached as background. Remove it above to use inspiration only.</p>}
            {sceneError && <p role="alert">{sceneError}</p>}
            <button type="button" className="account-secondary" disabled={!!backgroundReference || sceneLoading || !selectedPlan} onClick={attachScene}>{sceneLoading ? 'Loading sample…' : 'Attach sample as scene reference'}</button>
            {backgroundReference && !attachedSample && <p>Your uploaded background is retained. Remove it first if you want to attach this sample instead.</p>}
          </section>}
          <p className="ai-note">Your saved plan, additional description and optional photo are sent to Pollinations to generate images. Frameora keeps your gallery private; the provider may retain generated media.</p>
          <button className="user-dashboard-create-button" type="submit" disabled={!selectedPlan || sceneLoading}>Generate four images</button>
        </fieldset>
      </form>)}
    </>}
    {busy && <GenerationLoader />}
  </section></DashboardLayout>;
}
