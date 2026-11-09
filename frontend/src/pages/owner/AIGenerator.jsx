import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getProject } from "../../services/projectService";
import OwnerCustomization from "../../components/ai/OwnerCustomization";
import { normalizeOwnerPreferences, validateOwnerPreferences, DEFAULT_OWNER_PREFERENCES } from "../../config/ownerPreferences";
import AccountLayout from "../../components/layout/AccountLayout";
import GeneratedImageCard from "../../components/ai/GeneratedImageCard";
import GenerationLoader from "../../components/ai/GenerationLoader";
import ImageUploader from "../../components/ai/ImageUploader";
import PlanForm from "../../components/photography/PlanForm";
import { preferenceEntries } from "../../components/photography/PlanCard";
import useAuth from "../../hooks/useAuth";
import {
  createOwnerPhotographyPlan,
  generateOwnerImages,
  getOwnerEntitlements,
  getOwnerGeneration,
  getOwnerGenerations,
  getOwnerGeneratedImage,
  getOwnerPhotographyPlans,
  ownerGenerationError,
  ownerGenerationStatusMessage,
} from "../../services/ownerAiService";
import {
  isOwnerGalleryBatch,
  LEGACY_OWNER_CONTRACT,
  ownerBatchContractMatches,
  ownerContractsMatch,
  ownerGenerationAllowed,
  OWNER_GENERATION_CONTRACT,
} from "../../config/ownerGeneration";
import "../../styles/account.css";
import "../../styles/ai.css";

const pendingStorageKey = (userId) => `frameora.owner.ai.pending.${userId}`;

function readPending(userId) {
  if (!userId || typeof window === "undefined") return null;
  let raw;
  try {
    raw = window.sessionStorage.getItem(pendingStorageKey(userId));
  } catch {
    return { storageUnavailable: true };
  }
  if (!raw) return null;
  try {
    const pending = JSON.parse(raw);
    if (typeof pending.idempotencyKey === "string" &&
        Number.isInteger(pending.planId) &&
        typeof pending.description === "string") {
      return {
        ...pending,
        contract: pending.contract || LEGACY_OWNER_CONTRACT,
      };
    }
  } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
  }
  try {
    window.sessionStorage.removeItem(pendingStorageKey(userId));
  } catch {
    return { storageUnavailable: true };
  }
  return null;
}

function referenceMatches(file, info) {
  if (!info) return !file;
  return Boolean(file && file.name === info.name && file.size === info.size &&
    file.type === info.type && file.lastModified === info.lastModified);
}

export function linkedProjectIsEditable(projectId, projectAccess) {
  if (projectId == null) return true;
  const expectedId = Number(projectId);
  const actualId = Number(projectAccess?.id);
  return Number.isSafeInteger(expectedId) && expectedId > 0 &&
    Number.isSafeInteger(actualId) && actualId === expectedId &&
    projectAccess?.is_editable === true;
}

export function OwnerEntitlementSummary({ entitlement, contract = OWNER_GENERATION_CONTRACT }) {
  if (!entitlement) return null;
  const contractMatches = ownerBatchContractMatches(entitlement, contract);
  const planLabel = {
    basic: "Free Basic",
    trial: "Free Trial",
    pro: "Paid Pro",
  }[entitlement.plan] || "No active plan";
  const date = entitlement.subscription_end || entitlement.period_end;
  return <section className="account-card owner-ai-entitlement" aria-label="Owner AI entitlement">
    <h2>{planLabel}</h2>
    <p className="owner-ai-credit-summary"><strong>{entitlement.remaining_credits}</strong> available credits</p>
    {contractMatches
      ? <p className="owner-ai-batch-summary">Each batch uses {entitlement.batch_cost} credits and returns {contract.batchSize} images.</p>
      : <p className="user-plan-message is-error" role="alert">
        Generation is unavailable because the configured {contract.batchSize}-image batch does not match the backend credit cost ({entitlement.batch_cost} credits).
      </p>}
    {date && <p className="owner-ai-period-summary">{entitlement.plan === "trial" ? "Trial expires" : "Plan or credit period ends"}: {new Date(/[Zz]|[+-]\d\d:\d\d$/.test(date) ? date : `${date}Z`).toLocaleString()}</p>}
    {entitlement.previous_subscription_expired && <p role="status">Your previous plan expired. Free Basic is now active; unused credits did not carry over.</p>}
    {!entitlement.generation_allowed && entitlement.reason === "insufficient_credits" &&
      <p className="user-plan-message">At least {entitlement.batch_cost} credits are required for another batch.</p>}
    {!entitlement.generation_allowed && entitlement.reason === "paid_activation_disabled" &&
      <p className="user-plan-message">Paid Pro generation is unavailable until checkout and activation are enabled.</p>}
    {!entitlement.generation_allowed && entitlement.reason === "subscription_required" &&
      <p className="user-plan-message">Choose an owner subscription before generating images.</p>}
    {!entitlement.generation_allowed && entitlement.reason === "onboarding_required" &&
      <p className="user-plan-message">Complete Studio Owner setup before generating images.</p>}
    {!entitlement.generation_allowed && ![
      "insufficient_credits",
      "paid_activation_disabled",
      "subscription_required",
      "onboarding_required",
    ].includes(entitlement.reason) &&
      <p className="user-plan-message">Generation is currently unavailable under your owner subscription.</p>}
    <p className="owner-ai-limit-summary">Limits: {entitlement.max_projects} editable projects · {entitlement.max_share_links} active share links.</p>
  </section>;
}

export function OwnerGenerationImages({ generation, contract = OWNER_GENERATION_CONTRACT }) {
  if (generation?.status !== "completed" ||
      !isOwnerGalleryBatch(generation.images, contract, generation.charged_credits)) return null;
  return <section className="ai-generation">
    <h2>Your {generation.images.length} images are ready</h2>
    <p>{generation.charged_credits} credits charged · {generation.remaining_credits} credits available</p>
    <div className="ai-image-grid">{generation.images.map((image, index) =>
      <GeneratedImageCard key={image.id} image={image} index={index} loadImage={getOwnerGeneratedImage} enablePreview />)}</div>
  </section>;
}

export function OwnerGenerationConfirmation({
  entitlement,
  busy,
  onConfirm,
  onCancel,
  contract = OWNER_GENERATION_CONTRACT,
}) {
  const eligible = ownerGenerationAllowed(entitlement, contract);
  return <section className="account-card" aria-label="Generation charge confirmation">
    <h2>Confirm generation</h2>
    <p>This batch generates {contract.batchSize} images and reserves {entitlement?.batch_cost ?? contract.batchCost} credits.</p>
    <p>Available now: {entitlement?.remaining_credits ?? "Unavailable"} credits.</p>
    <button type="button" className="owner-gradient-button"
      disabled={busy || !eligible} onClick={onConfirm}>
      Confirm and generate ({entitlement?.batch_cost ?? contract.batchCost} credits)
    </button>
    <button type="button" className="account-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
  </section>;
}

export default function OwnerAIGenerator({ photoshoot } = {}) {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [plans, setPlans] = useState([]);
  const [planId, setPlanId] = useState(() => {
    const saved = readPending(user?.id);
    return saved ? String(saved.planId) : photoshoot ? String(photoshoot.planId) : (/^[1-9]\d*$/.test(searchParams.get("plan") || "") ? searchParams.get("plan") : "");
  });
  const [description, setDescription] = useState(() => readPending(user?.id)?.description || "");
  const [preferences, setPreferences] = useState(() => normalizeOwnerPreferences(readPending(user?.id)?.preferences || photoshoot?.preferences));
  const [preferenceErrors, setPreferenceErrors] = useState({});
  const [reference, setReference] = useState(photoshoot?.reference || null);
  const [entitlement, setEntitlement] = useState(null);
  const [activeGeneration, setActiveGeneration] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [reviewing, setReviewing] = useState(Boolean(photoshoot));
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [planSaving, setPlanSaving] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [pending, setPending] = useState(() => readPending(user?.id));
  const submitting = useRef(false);
  const selectedPlan = plans.find((plan) => String(plan.id) === planId);
  const loadedPreferencesFor = useRef(photoshoot ? String(photoshoot.planId) : null);
  useEffect(() => {
    if (!selectedPlan || pending || loadedPreferencesFor.current === planId) return;
    loadedPreferencesFor.current = planId;
    let saved = selectedPlan.preferences;
    if (typeof saved === 'string') { try { saved = JSON.parse(saved); } catch { saved = null; } }
    setPreferences(normalizeOwnerPreferences(saved?.owner_generation));
    setReviewing(false);
  }, [selectedPlan, planId, pending]);
  const blockedByPending = Boolean(activeGeneration?.status === "owner_reserved");
  const pendingStorageUnavailable = pending?.storageUnavailable === true;
  const retryNeedsReference = Boolean(pending?.referenceInfo && !reference);
  const retryContractMatches = !pending ||
    ownerContractsMatch(pending.contract, OWNER_GENERATION_CONTRACT);
  const [projectAccess, setProjectAccess] = useState(null);
  const [projectAccessLoading, setProjectAccessLoading] = useState(false);
  const [projectAccessFailed, setProjectAccessFailed] = useState(false);
  const linkedProjectId = selectedPlan?.project_id;
  const projectEditable = linkedProjectIsEditable(linkedProjectId, projectAccess);
  const canGenerate = ownerGenerationAllowed(entitlement) && projectEditable;
  useEffect(() => {
    if (!linkedProjectId) {
      setProjectAccess(null);
      setProjectAccessLoading(false);
      setProjectAccessFailed(false);
      return;
    }
    const controller = new AbortController();
    let latestRequest = 0;
    const refreshAccess = () => {
      const requestId = ++latestRequest;
      setProjectAccess(null);
      setProjectAccessLoading(true);
      setProjectAccessFailed(false);
      getProject(linkedProjectId, controller.signal)
        .then(p => {
          if (!controller.signal.aborted && requestId === latestRequest) setProjectAccess(p);
        })
        .catch(() => {
          if (!controller.signal.aborted && requestId === latestRequest) {
            setProjectAccess(null);
            setProjectAccessFailed(true);
          }
        })
        .finally(() => {
          if (!controller.signal.aborted && requestId === latestRequest) setProjectAccessLoading(false);
        });
    };
    refreshAccess();
    window.addEventListener('focus', refreshAccess);
    return () => { controller.abort(); window.removeEventListener('focus', refreshAccess); };
  }, [linkedProjectId]);

  const clearPending = useCallback(() => {
    if (user?.id && typeof window !== "undefined") {
      try {
        window.sessionStorage.removeItem(pendingStorageKey(user.id));
      } catch {
        setError("The completed request key could not be cleared from this browser. Do not start a new batch until session storage is available.");
        return false;
      }
    }
    setPending(null);
    return true;
  }, [user?.id]);

  const refreshEntitlements = useCallback(async () => {
    setEntitlement(await getOwnerEntitlements());
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    Promise.all([
      getOwnerEntitlements(),
      getOwnerPhotographyPlans(controller.signal),
      getOwnerGenerations(),
    ]).then(([nextEntitlement, nextPlans, generations]) => {
      if (!active) return;
      setEntitlement(nextEntitlement);
      setPlans(nextPlans);
      const currentPending = generations.find((generation) => generation.status === "owner_reserved");
      setActiveGeneration(currentPending || null);
      if (!planId && nextPlans.length) {
        const savedPlan = readPending(user?.id)?.planId;
        setPlanId(String(nextPlans.find((plan) => plan.id === savedPlan)?.id || nextPlans[0].id));
      }
    }).catch((requestError) => {
      if (active) setError(ownerGenerationError(requestError));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [refresh, user?.id]);

  async function savePlan(values) {
    setPlanSaving(true);
    try {
      const created = await createOwnerPhotographyPlan(values);
      setPlans((current) => [...current, created]);
      setPlanId(String(created.id));
      setShowPlanForm(false);
    } finally {
      setPlanSaving(false);
    }
  }

  async function applyGeneration(generation) {
    setActiveGeneration(generation?.status === "owner_reserved" ? generation : null);
    if (generation?.status === "completed" &&
        isOwnerGalleryBatch(generation.images, OWNER_GENERATION_CONTRACT, generation.charged_credits)) {
      setResult(generation);
      setReviewing(false);
      clearPending();
      if (photoshoot && Number(generation.plan_id) === Number(photoshoot.planId)) photoshoot.onCompleted?.(generation);
      try {
        await refreshEntitlements();
      } catch {
        setError("Your images are ready, but the credit balance could not refresh. Reload the page to check it.");
      }
    } else if (generation?.status === "failed") {
      setResult(generation);
      setReviewing(false);
      clearPending();
      try {
        await refreshEntitlements();
      } catch {
        setError("The batch failed and its status is confirmed, but the credit balance could not refresh.");
      }
    } else if (generation?.status === "completed") {
      setResult(generation);
      setError(ownerGenerationStatusMessage(generation));
    }
    return generation;
  }

  async function checkActiveGeneration() {
    if (!activeGeneration?.id) return;
    setBusy(true);
    setError("");
    try {
      await applyGeneration(await getOwnerGeneration(activeGeneration.id));
    } catch (requestError) {
      setError(ownerGenerationError(requestError));
    } finally {
      setBusy(false);
    }
  }

  async function submitBatch(event) {
    event?.preventDefault();
    if (submitting.current || busy || blockedByPending) return;
    if (!projectEditable) { setError("This project is read-only or its permissions could not be verified."); return; }
    if (!pending && !canGenerate) {
      setError("The owner generation batch does not match the backend entitlement. No generation was submitted.");
      return;
    }
    if (pending && retryContractMatches && !ownerBatchContractMatches(entitlement)) {
      setError("The owner generation batch does not match the backend entitlement. Check the existing request status; it was not resubmitted.");
      return;
    }
    if (pendingStorageUnavailable) {
      setError("Browser session storage is unavailable, so a safe idempotency key cannot be retained. No generation was submitted.");
      return;
    }
    if (!selectedPlan && !pending) {
      setError("Choose or create one of your saved photography plans.");
      return;
    }
    if (reference && (reference.size > 5 * 1024 * 1024 ||
        !["image/jpeg", "image/png", "image/webp"].includes(reference.type))) {
      setError("Choose a JPEG, PNG or WebP reference photo of at most 5 MiB.");
      return;
    }
    if (pending && !referenceMatches(reference, pending.referenceInfo)) {
      setError("Re-select the same reference photo used for this pending request before retrying it.");
      return;
    }
    if (pending && !retryContractMatches) {
      setError("This request uses a different image-batch contract. Check its status in the owner gallery; it cannot be resubmitted under the changed contract.");
      return;
    }

    const errors = validateOwnerPreferences(preferences);
    setPreferenceErrors(errors);
    if (Object.keys(errors).length) { setReviewing(false); return; }
    submitting.current = true;
    setBusy(true);
    setError("");
    let request = pending;
    try {
      if (!request) {
        request = {
          idempotencyKey: crypto.randomUUID(),
          planId: Number(planId),
          projectId: selectedPlan?.project_id || null,
          description: description.trim(),
          preferences: normalizeOwnerPreferences(preferences),
          contract: OWNER_GENERATION_CONTRACT,
          referenceInfo: reference ? {
            name: reference.name,
            size: reference.size,
            type: reference.type,
            lastModified: reference.lastModified,
          } : null,
        };
        try {
          window.sessionStorage.setItem(pendingStorageKey(user.id), JSON.stringify(request));
        } catch {
          setError("The browser could not save a safe retry key. Check session storage and try again; no generation was submitted.");
          return;
        }
        setPending(request);
      }
      if (Number(planId) !== request.planId || description.trim() !== request.description ||
          JSON.stringify(normalizeOwnerPreferences(preferences)) !== JSON.stringify(normalizeOwnerPreferences(request.preferences))) {
        setError("This retry must use the original photography plan and customization preferences. Start a new batch only after checking this request.");
        return;
      }
      const generation = await generateOwnerImages({
        planId: request.planId,
        projectId: request.projectId,
        description: request.description,
        preferences: request.preferences,
        reference,
        idempotencyKey: request.idempotencyKey,
      });
      if (generation.status === "owner_reserved") {
        setActiveGeneration(generation);
        setReviewing(false);
        await refreshEntitlements();
      } else {
        await applyGeneration(generation);
      }
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      const generationId = typeof detail === "object" ? detail?.generation_id : null;
      if (generationId) {
        try {
          const current = await getOwnerGeneration(generationId);
          await applyGeneration(current);
          setError(current.status === "owner_reserved" ? ownerGenerationError(requestError) : "");
        } catch {
          setActiveGeneration({ id: generationId, status: "owner_reserved" });
          setError(ownerGenerationError(requestError));
        }
      } else if (requestError.response?.status === 402 ||
          requestError.response?.status === 403 ||
          requestError.response?.status === 422 ||
          (requestError.response?.status === 409 &&
            ["subscription_required", "onboarding_required", "paid_activation_disabled"].includes(detail))) {
        clearPending();
        setError(ownerGenerationError(requestError));
      } else {
        setError(ownerGenerationError(requestError));
      }
      try {
        await refreshEntitlements();
      } catch {
        setEntitlement(null);
      }
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function startNewBatch() {
    if (!clearPending()) return;
    setResult(null);
    setActiveGeneration(null);
    setReference(null);
    setDescription("");
    setPreferences({ ...DEFAULT_OWNER_PREFERENCES });
    setPreferenceErrors({});
    setReviewing(false);
    setError("");
  }

  const retrying = Boolean(pending && !pendingStorageUnavailable);
  const batchContractMatches = ownerBatchContractMatches(entitlement);
  const Layout = photoshoot ? Fragment : AccountLayout;
  if (photoshoot && pending && !pending.storageUnavailable && Number(pending.planId) !== Number(photoshoot.planId)) return <section className="account-notice">
    <h2>Your photoshoot is saved</h2><p>A previous image request still needs attention. Resolve it before generating another batch.</p>
    <Link className="owner-gradient-button" to="/owner/ai/generate">Resume Previous Generation</Link>
  </section>;
  return <Layout><section className="user-plan-page account-page ai-page owner-ai-page">
    <header className="account-heading">
      <div><h1>{photoshoot ? "Generate Photoshoot Images" : "Studio AI Image Generation"}</h1><p>{batchContractMatches
        ? `Generate ${OWNER_GENERATION_CONTRACT.batchSize} photography concepts using your saved studio requirements.`
        : "Generation is unavailable until the owner AI batch contract matches the backend."}</p></div>
      <Link className="account-secondary" to="/owner/ai/gallery">Owner Gallery</Link>
    </header>
    {linkedProjectId && <div className="account-notice">
      <Link to={`/owner/projects/${linkedProjectId}`}>Back to customer project</Link>
      {projectAccessLoading && <p role="status">Checking access to customer project #{linkedProjectId}…</p>}
      {projectAccessFailed && <p className="user-plan-message is-error" role="alert">
        The access check for customer project #{linkedProjectId} failed. Generation remains disabled until project access can be verified.
      </p>}
      {!projectAccessLoading && !projectAccessFailed &&
        Number(projectAccess?.id) === Number(linkedProjectId) && projectAccess?.is_editable === false &&
        <p role="status">Customer project #{linkedProjectId} is read-only under your current subscription. Generation is disabled for this project.</p>}
      {!projectAccessLoading && !projectAccessFailed &&
        (!projectAccess || Number(projectAccess.id) !== Number(linkedProjectId)) && !projectEditable &&
        <p className="user-plan-message is-error" role="alert">
          Access to customer project #{linkedProjectId} could not be verified. Generation remains disabled.
        </p>}
    </div>}
    {entitlement && <OwnerEntitlementSummary entitlement={entitlement} />}
    {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
    {pendingStorageUnavailable && <p className="user-plan-message is-error" role="alert">
      A prior request key may still exist, but browser session storage is unavailable. Re-enable it and reload before submitting another batch.
    </p>}
    {loading ? <p role="status">Loading your studio credits and photography plans…</p> : <>
      {!entitlement && <button className="account-secondary" onClick={() => setRefresh((value) => value + 1)}>Retry loading</button>}
      {blockedByPending && <section className="account-card" role="status">
        <h2>Generation in progress</h2>
        <p>{ownerGenerationStatusMessage(activeGeneration)}</p>
        {activeGeneration.recover_after && <p>Recovery available after: {new Date(`${activeGeneration.recover_after.replace(/Z$/, "")}Z`).toLocaleString()}</p>}
        <button className="account-secondary" type="button" disabled={busy} onClick={checkActiveGeneration}>Check generation status</button>
        <Link className="account-secondary" to="/owner/ai/gallery">Open owner gallery</Link>
      </section>}
      {!photoshoot && !plans.length && !showPlanForm && <section className="account-card">
        <p>Create a saved photography plan before generating images.</p>
        <button type="button" className="account-secondary" onClick={() => setShowPlanForm(true)}>Create photography plan</button>
      </section>}
      {showPlanForm && <section className="account-card">
        <h2>Create a studio photography plan</h2>
        <PlanForm onSubmit={savePlan} submitting={planSaving} />
        <button type="button" className="account-secondary" onClick={() => setShowPlanForm(false)} disabled={planSaving}>Cancel</button>
      </section>}
      {plans.length > 0 && !blockedByPending && !result && <form className="account-card ai-form" onSubmit={(event) => {
        event.preventDefault();
        if (retrying) submitBatch();
        else {
          const errors = validateOwnerPreferences(preferences);
          setPreferenceErrors(errors);
          setReviewing(Object.keys(errors).length === 0);
        }
      }}>
        <fieldset disabled={busy || !projectEditable}>
          <div className="form-field">
            <label htmlFor="owner-ai-plan">Photography plan</label>
            <select id="owner-ai-plan" required value={planId} disabled={retrying || Boolean(photoshoot)}
              onChange={(event) => setPlanId(event.target.value)}>
              {plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.photography_type} · {plan.environment} · #{plan.id}</option>)}
              {pending && !plans.some((plan) => plan.id === pending.planId) &&
                <option value={pending.planId}>Saved plan #{pending.planId} for this pending request</option>}
            </select>
          </div>
          {selectedPlan && <section className="ai-plan-summary" aria-label="Saved plan details">
            <h2>Using your saved studio plan</h2>
            <p>{selectedPlan.photography_type} · {selectedPlan.people_count} people · {selectedPlan.environment}</p>
            <dl className="user-plan-preference-list">
              {selectedPlan.location && <div><dt>Location</dt><dd>{selectedPlan.location}</dd></div>}
              {selectedPlan.shoot_datetime && <div><dt>Shoot date/time</dt><dd>{selectedPlan.shoot_datetime.replace("T", " ")}</dd></div>}
              {preferenceEntries(selectedPlan.preferences).map(([key, label, value]) => <div key={key}><dt>{label}</dt><dd>{value}</dd></div>)}
            </dl>
          </section>}
          <details open={!photoshoot}><summary>Image customization</summary>
          <OwnerCustomization values={preferences} errors={preferenceErrors} disabled={retrying}
            onChange={event => {
              const { name, value } = event.target;
              setPreferences(current => ({ ...current, [name]: value }));
              setPreferenceErrors(current => ({ ...current, [name]: '' }));
              setReviewing(false);
            }} />
          </details>
          {photoshoot?.reference && reference && <p>Reference photo ready: {reference.name}</p>}
          <ImageUploader onChange={setReference} disabled={busy} />
          {retrying && <p className="ai-note">Retrying the same request key; the plan and customization preferences are locked to the original submission.</p>}
          {reviewing && !retrying && <OwnerGenerationConfirmation entitlement={entitlement} busy={busy}
            onConfirm={submitBatch} onCancel={() => setReviewing(false)} />}
          {!reviewing && !retrying && <button type="submit" className="owner-gradient-button"
            disabled={!selectedPlan || !canGenerate}>Review {OWNER_GENERATION_CONTRACT.batchSize} images / {OWNER_GENERATION_CONTRACT.batchCost} credits</button>}
          {retrying && retryContractMatches && <button type="submit" className="owner-gradient-button" disabled={busy || retryNeedsReference}>
            {retryNeedsReference ? "Re-select original reference photo to retry" : "Retry the same request"}
          </button>}
          {retrying && !retryContractMatches && <p className="user-plan-message is-error" role="alert">
            This request was created for a different batch contract and cannot be resubmitted. Check the owner gallery before starting another batch.
            {" "}<Link to="/owner/ai/gallery">Check owner gallery</Link>
          </p>}
          {retryNeedsReference && <p role="status">Re-select the exact original photo to safely retry this request.</p>}
        </fieldset>
      </form>}
      {!photoshoot && plans.length > 0 && !showPlanForm && !blockedByPending && <button type="button" className="account-secondary"
        onClick={() => setShowPlanForm(true)}>Add another photography plan</button>}
      {activeGeneration && !blockedByPending && <section className="account-card" role="status">
        <h2>Checking generation</h2><p>{ownerGenerationStatusMessage(activeGeneration)}</p>
      </section>}
      {result?.status === "completed" && isOwnerGalleryBatch(result.images, OWNER_GENERATION_CONTRACT, result.charged_credits) && <>
        <OwnerGenerationImages generation={result} />
        {linkedProjectId && <Link className="owner-gradient-button" to={`/owner/projects/${linkedProjectId}#gallery`}>Gallery &amp; Share with Customer</Link>}
        <button type="button" className="account-secondary" onClick={startNewBatch}>Start a new batch</button>
      </>}
      {result?.status === "failed" && <section className="account-card" role="status">
        <h2>Batch failed</h2><p>{ownerGenerationStatusMessage(result)}</p>
        <button type="button" className="account-secondary" onClick={startNewBatch}>Start a new batch with a new request key</button>
      </section>}
      {result?.status === "completed" && !isOwnerGalleryBatch(result.images, OWNER_GENERATION_CONTRACT, result.charged_credits) && <section className="account-card" role="alert">
        <h2>Generation requires review</h2><p>{ownerGenerationStatusMessage(result)}</p>
        <Link className="account-secondary" to="/owner/ai/gallery">Check the owner gallery</Link>
      </section>}
    </>}
    {busy && !activeGeneration && <GenerationLoader imageCount={OWNER_GENERATION_CONTRACT.batchSize}
      message={`Your Studio Owner request reserves ${OWNER_GENERATION_CONTRACT.batchCost} credits. Credits are charged only for a complete ${OWNER_GENERATION_CONTRACT.batchSize}-image batch.`} />}
  </section></Layout>;
}