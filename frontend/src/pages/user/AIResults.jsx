import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../../components/layout/DashboardLayout";
import GeneratedImageCard from "../../components/ai/GeneratedImageCard";
import { getGenerations, generationError } from "../../services/aiService";
import "../../styles/account.css";
import "../../styles/ai.css";

import ProjectFolders, { useProjectGallery } from "../../components/ai/ProjectFolders";

export default function AIResults() {
  const [refresh, setRefresh] = useState(0);
  const gallery = useProjectGallery(refresh);
  const {items, error, loading, hasMore, loadMore} = gallery;
  return <DashboardLayout><section className="user-plan-page account-page ai-page">
    <div className="user-dashboard-section-heading"><div><h1>My Gallery</h1><p>Your private AI photography images.</p></div><Link className="user-dashboard-create-button" to="/user/ai">Generate Images</Link></div>
    <button className="account-secondary" disabled={loading} onClick={() => setRefresh(refresh + 1)}>Refresh</button>
    {error && <p className="user-plan-message is-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading your gallery…</p>}
    {!loading && !error && !gallery.folders.length && !gallery.selected && <div className="user-dashboard-empty-state">No generated images yet. Start with a photography plan.</div>}
    <ProjectFolders gallery={gallery} />
    {items.map((generation) => <section className="ai-generation" key={generation.id}>
      <h2>Photography plan #{generation.plan_id}</h2>
      <p>{new Date(generation.created_at + (generation.created_at.endsWith("Z") ? "" : "Z")).toLocaleString()}</p>
      {generation.status === "completed" ? <div className="ai-image-grid">{generation.images.map((image, index) => <GeneratedImageCard key={image.id} image={image} index={index} />)}</div> : <p role="status">{generation.status === "failed" ? "This request failed. Your free request was not used." : "This request is in progress. Refresh to check for saved results."}</p>}
    </section>)}
    {hasMore && <button className="account-secondary" disabled={loading} onClick={loadMore}>Load more</button>}
  </section></DashboardLayout>;
}
