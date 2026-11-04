import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import ImageUploader from "../../components/ai/ImageUploader";
import GenerationLoader from "../../components/ai/GenerationLoader";
import { getMyPlans } from "../../services/planService";
import { generateImages, getFreeGenerationEligibility, generationError } from "../../services/aiService";
import "../../styles/account.css";
import "../../styles/ai.css";

export default function AIGenerator() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState(params.get("plan") || "");
  const [description, setDescription] = useState("");
  const [reference, setReference] = useState(null);
  const [eligibility, setEligibility] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
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
    if (busy) return;
    if (reference && (reference.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(reference.type))) {
      setError("Choose a JPEG, PNG or WebP image of at most 5 MiB."); return;
    }
    setBusy(true); setError("");
    try {
      await generateImages({ planId, description, reference });
      navigate("/user/gallery");
    } catch (err) {
      setError(generationError(err));
      try { setEligibility(await getFreeGenerationEligibility()); } catch { setEligibility(null); }
    } finally { setBusy(false); }
  }
  return <DashboardLayout><section className="user-plan-page account-page ai-page">
    <div className="user-dashboard-section-heading"><div><h1>AI Image Generation</h1><p>Explore four poses, angles and compositions for your photography plan.</p></div><Link to="/user/gallery" className="user-dashboard-view-all">My Gallery</Link></div>
    <p>Each account includes one successful free request with four images. Facial appearance may vary; exact identity preservation is not guaranteed.</p>
    {loading ? <p role="status">Loading your plans and free request…</p> : <>
      {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
      {!eligibility && <button className="account-secondary" onClick={() => setAttempt(attempt + 1)}>Retry loading</button>}
      {eligibility?.free_request_status === "used" && <p className="user-plan-message">Your free request has been used. <Link to="/user/gallery">View your images</Link>.</p>}
      {eligibility?.free_request_status === "in_progress" && <p className="user-plan-message">A request is already in progress. <Link to="/user/gallery">Check your gallery</Link>.</p>}
      {!plans.length ? <p><Link to="/user/plans/create">Create a photography plan</Link> to get started.</p> : <form className="account-card ai-form" onSubmit={submit}>
        <fieldset disabled={busy || !eligibility?.free_request_available}>
          <div className="form-field"><label htmlFor="ai-plan">Photography plan</label><select id="ai-plan" required value={planId} onChange={(e) => setPlanId(e.target.value)}><option value="">Choose a plan</option>{plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.photography_type} · {plan.environment} · #{plan.id}</option>)}</select></div>
          <div className="form-field"><label htmlFor="ai-description">Describe your subject and setting</label><textarea id="ai-description" required minLength={3} maxLength={2000} rows={5} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe appearance, clothing, location and mood…" /></div>
          <ImageUploader onChange={setReference} disabled={busy} />
          <p className="ai-note">Your description and optional photo are sent to Pollinations to generate images. Frameora keeps your gallery private; the provider may retain generated media.</p>
          <button className="user-dashboard-create-button" type="submit">Generate four images</button>
        </fieldset>
      </form>}
    </>}
    {busy && <GenerationLoader />}
  </section></DashboardLayout>;
}
