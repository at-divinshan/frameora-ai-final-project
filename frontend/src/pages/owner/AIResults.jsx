import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AccountLayout from "../../components/layout/AccountLayout";
import GeneratedImageCard from "../../components/ai/GeneratedImageCard";
import {
  getOwnerGenerations,
  getOwnerGeneratedImage,
  ownerGenerationError,
  recoverOwnerGeneration,
} from "../../services/ownerAiService";
import { ownerGenerationStatusMessage } from "../../services/ownerAiService";
import {
  isOwnerGalleryBatch,
  OWNER_GENERATION_CONTRACT,
} from "../../config/ownerGeneration";
import "../../styles/account.css";
import "../../styles/ai.css";

function utcDate(value) {
  if (!value) return "Unavailable";
  const date = new Date(/[Zz]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}

export default function OwnerAIResults() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [recovering, setRecovering] = useState(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    getOwnerGenerations().then((data) => {
      if (active) setItems(data);
    }).catch((requestError) => {
      if (active) setError(ownerGenerationError(requestError));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    const deadlines = items
      .filter((item) => item.status === "owner_reserved" && item.recover_after)
      .map((item) => new Date(
        /[Zz]|[+-]\d\d:\d\d$/.test(item.recover_after)
          ? item.recover_after : `${item.recover_after}Z`,
      ).getTime())
      .filter((deadline) => Number.isFinite(deadline) && deadline > now);
    if (!deadlines.length) return undefined;
    const timer = window.setTimeout(
      () => setNow(Date.now()),
      Math.min(...deadlines) - now,
    );
    return () => window.clearTimeout(timer);
  }, [items, now]);

  async function recover(id) {
    setRecovering(id);
    setError("");
    try {
      const updated = await recoverOwnerGeneration(id);
      setItems((current) => current.map((item) => item.id === id ? updated : item));
    } catch (requestError) {
      setError(ownerGenerationError(requestError));
    } finally {
      setRecovering(null);
    }
  }

  return <AccountLayout><section className="user-plan-page account-page ai-page">
    <header className="account-heading">
      <div><h1>Studio AI Gallery</h1><p>Your private owner-credit generations and Camera Setup Guides.</p></div>
      <Link className="user-dashboard-create-button" to="/owner/ai/generate">Generate Images</Link>
    </header>
    <button className="account-secondary" type="button" disabled={loading}
      onClick={() => setRefresh((current) => current + 1)}>Refresh gallery</button>
    {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading your studio gallery…</p>}
    {!loading && !error && !items.length && <div className="user-dashboard-empty-state">No Studio Owner generations yet.</div>}
    {items.map((generation) => {
      const complete = generation.status === "completed" &&
        isOwnerGalleryBatch(
          generation.images,
          OWNER_GENERATION_CONTRACT,
          generation.charged_credits,
        );
      const incomplete = generation.status === "completed" && !complete;
      const deadline = generation.recover_after && new Date(
          /[Zz]|[+-]\d\d:\d\d$/.test(generation.recover_after)
            ? generation.recover_after : `${generation.recover_after}Z`,
        ).getTime();
      const canRecover = generation.status === "owner_reserved" &&
        Number.isFinite(deadline) && now >= deadline;
      return <section className="ai-generation account-card" key={generation.id}>
        <h2>Photography plan #{generation.plan_id}</h2>
        <p>{utcDate(generation.created_at)}</p>
        {complete && <>
          <p>{generation.images.length} images · {generation.charged_credits} credits charged · {generation.remaining_credits} available</p>
          <div className="ai-image-grid">{generation.images.map((image, index) =>
            <GeneratedImageCard key={image.id} image={image} index={index} loadImage={getOwnerGeneratedImage} enablePreview />)}</div>
        </>}
        {generation.status === "owner_reserved" && <div role="status">
          <p>{ownerGenerationStatusMessage(generation)}</p>
          <p>Recovery available after: {utcDate(generation.recover_after)}</p>
          {canRecover && <button className="account-secondary" type="button"
            disabled={recovering === generation.id} onClick={() => recover(generation.id)}>
            {recovering === generation.id ? "Recovering…" : "Recover and refund this overdue batch"}
          </button>}
        </div>}
        {generation.status === "failed" && <p role="status">{ownerGenerationStatusMessage(generation)}</p>}
        {incomplete && <p className="user-plan-message is-error" role="alert">{ownerGenerationStatusMessage(generation)}</p>}
      </section>;
    })}
  </section></AccountLayout>;
}