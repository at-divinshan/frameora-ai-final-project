import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import GeneratedImageCard from "../../components/ai/GeneratedImageCard";
import { getGenerations, generationError } from "../../services/aiService";
import "../../styles/account.css";
import "../../styles/ai.css";

export default function AIResults() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError("");
    getGenerations(controller.signal).then((data) => {
      setItems(data); setHasMore(data.length === 20);
    }).catch((err) => { if (!controller.signal.aborted) setError(generationError(err)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refresh]);
  async function loadMore() {
    setLoading(true); setError("");
    try {
      const data = await getGenerations(undefined, items.at(-1)?.id);
      setItems((current) => [...current, ...data]); setHasMore(data.length === 20);
    } catch (err) { setError(generationError(err)); } finally { setLoading(false); }
  }
  return <DashboardLayout><section className="user-plan-page account-page ai-page">
    <div className="user-dashboard-section-heading"><div><h1>My Gallery</h1><p>Your private AI photography images.</p></div><Link className="user-dashboard-create-button" to="/user/ai">Generate Images</Link></div>
    <button className="account-secondary" disabled={loading} onClick={() => setRefresh(refresh + 1)}>Refresh</button>
    {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading your gallery…</p>}
    {!loading && !error && !items.length && <div className="user-dashboard-empty-state">No generated images yet. Start with a photography plan.</div>}
    {items.map((generation) => <section className="ai-generation" key={generation.id}>
      <h2>Photography plan #{generation.plan_id}</h2>
      <p>{new Date(generation.created_at + (generation.created_at.endsWith("Z") ? "" : "Z")).toLocaleString()}</p>
      {generation.status === "completed" ? <div className="ai-image-grid">{generation.images.map((image, index) => <GeneratedImageCard key={image.id} image={image} index={index} />)}</div> : <p role="status">{generation.status === "failed" ? "This request failed. Your free request was not used." : "This request is in progress. Refresh to check for saved results."}</p>}
    </section>)}
    {hasMore && <button className="account-secondary" disabled={loading} onClick={loadMore}>Load more</button>}
  </section></DashboardLayout>;
}
