import { useEffect, useState } from "react";
import AccountLayout from "../../components/layout/AccountLayout";
import GeneratedImageCard from "../../components/ai/GeneratedImageCard";
import {
  getAccountHistoryGenerations,
  getAccountHistoryImage,
  getAccountHistoryPlans,
} from "../../services/subscriptionService";
import "../../styles/account.css";
import "../../styles/ai.css";

function localDate(value) {
  if (!value) return "Unavailable";
  const date = new Date(/[Zz]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Unavailable" : date.toLocaleString();
}

export default function AccountHistory() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setError("");
    Promise.all([
      getAccountHistoryPlans(controller.signal),
      getAccountHistoryGenerations(controller.signal),
    ]).then(([plans, generations]) => {
      if (!controller.signal.aborted) setData({ plans, generations, hasMore: generations.length === 20 });
    }).catch((requestError) => {
      if (!controller.signal.aborted) {
        const detail = requestError.response?.data?.detail;
        setError(typeof detail === "string" ? detail : "Unable to load previous account data.");
      }
    });
    return () => controller.abort();
  }, [retry]);

  async function loadMore() {
    if (!data?.generations.length) return;
    setError("");
    try {
      const more = await getAccountHistoryGenerations(undefined, data.generations.at(-1).id);
      setData((current) => ({
        ...current,
        generations: [...current.generations, ...more],
        hasMore: more.length === 20,
      }));
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Unable to load more previous generations.");
    }
  }

  return (
    <AccountLayout>
      <section className="user-plan-page account-page ai-page">
        <header className="account-heading">
          <div>
            <h1>Previous Account Data</h1>
            <p>Read-only access to photography plans and AI images saved before your Studio Owner upgrade.</p>
          </div>
        </header>
        {error && <div className="account-error" role="alert">{error}</div>}
        {!data && !error && <p role="status">Loading previous account data…</p>}
        {error && !data && <button className="account-secondary" type="button" onClick={() => setRetry((value) => value + 1)}>Retry</button>}
        {data && <>
          <section aria-labelledby="previous-plans-heading">
            <h2 id="previous-plans-heading">Photography Plans</h2>
            {!data.plans.length && <p>No previous photography plans were found.</p>}
            <div className="user-history-plan-grid">
              {data.plans.map((plan) => (
                <article className="account-card" key={plan.id}>
                  <h3>{plan.photography_type}</h3>
                  <dl className="account-details">
                    <div><dt>Environment</dt><dd>{plan.environment}</dd></div>
                    <div><dt>People</dt><dd>{plan.people_count}</dd></div>
                    <div><dt>Created</dt><dd>{localDate(plan.created_at)}</dd></div>
                    {plan.location && <div><dt>Location</dt><dd>{plan.location}</dd></div>}
                  </dl>
                </article>
              ))}
            </div>
          </section>
          <section aria-labelledby="previous-generations-heading">
            <h2 id="previous-generations-heading">AI Gallery</h2>
            {!data.generations.length && <p>No previous AI generations were found.</p>}
            {data.generations.map((generation) => (
              <article className="ai-generation account-card" key={generation.id}>
                <h3>Photography plan #{generation.plan_id}</h3>
                <p>{localDate(generation.created_at)}</p>
                {generation.status === "completed" && generation.images.length > 0
                  ? <div className="ai-image-grid">{generation.images.map((image, index) => (
                    <GeneratedImageCard key={image.id} image={image} index={index} loadImage={getAccountHistoryImage} />
                  ))}</div>
                  : <p role="status">{generation.status === "failed" ? "This previous request failed." : "This previous request has no completed images."}</p>}
              </article>
            ))}
            {data.hasMore && <button className="account-secondary" type="button" onClick={loadMore}>Load more generations</button>}
          </section>
        </>}
      </section>
    </AccountLayout>
  );
}
