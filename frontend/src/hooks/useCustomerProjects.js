import { useEffect, useState } from 'react';
import { getProjects, projectError } from '../services/projectService';
import { getPlans, getSubscription } from '../services/ownerService';
import { watchSubscriptionRefresh } from '../utils/subscription';

export default function useCustomerProjects() {
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  const refresh = () => setRevision(n => n + 1);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    Promise.all([getProjects(controller.signal), getPlans(), getSubscription()])
      .then(([projects, plans, status]) => {
        if (!controller.signal.aborted) setData({ projects, status, plan: plans.find(p => p.code === status.plan) });
      }).catch(e => { if (!controller.signal.aborted) { setData(null); setError(projectError(e)); } });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => watchSubscriptionRefresh(data?.status.period_end, refresh), [data?.status.period_end]);
  return { data, error, refresh };
}
