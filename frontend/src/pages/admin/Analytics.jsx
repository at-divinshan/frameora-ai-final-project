import { lazy, Suspense, useEffect, useState } from 'react';
import AdminLayout from '../../components/layout/AdminLayout';
import { getAdminAnalytics } from '../../services/adminService';
import '../../styles/admin-analytics.css';

const number = value => value == null ? 'Not available' : Number(value).toLocaleString();
const AnalyticsCharts = lazy(() => import('../../components/admin/AnalyticsCharts'));
export function AnalyticsContent({ data }) {
  return <>
    <div className="analytics-stats">{[
      ['Registered users', data.users], ['Studio owners', data.owners], ['Photography projects', data.projects],
      ['AI-generated image records', data.images], ['Verified Test Mode payments', data.payments],
      ['Test Mode payment total (LKR)', data.revenue],
    ].map(([label, value]) => <section className="analytics-panel" key={label}><h2>{label}</h2><strong className="analytics-number">{number(value)}</strong></section>)}</div>
    <p className="analytics-note">Registered users includes all roles. Projects includes non-deleted studio projects and standalone photography plans. Image counts reflect completed database records, not file availability.</p>
    <Suspense fallback={<p role="status">Loading charts…</p>}><AnalyticsCharts data={data} /></Suspense>
    <p className="analytics-note">Payment figures are verified Stripe Test Mode LKR payments, not real revenue. Failed, pending, refunded, disputed and revoked payments are excluded. Charts show up to 12 consecutive months ending at the latest recorded activity, with zeroes for gaps within known coverage. Image trends use generation completion dates; records without a completion date are omitted.</p>
  </>;
}
export default function Analytics() {
  const [data, setData] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(true), [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    getAdminAnalytics(controller.signal).then(value => { if (!controller.signal.aborted) setData(value); }).catch(() => {
      if (!controller.signal.aborted) setError('Analytics could not be loaded. Please try again.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [retry]);
  return <AdminLayout title="Analytics"><div className="admin-analytics"><h1>Analytics</h1><p>Account, project and Test Mode payment activity.</p>
    {loading ? <p role="status">Loading analytics…</p> : error ? <div role="alert"><p>{error}</p><button className="user-dashboard-create-button" onClick={() => setRetry(value => value + 1)}>Try again</button></div> : data && <AnalyticsContent data={data} />}
  </div></AdminLayout>;
}
