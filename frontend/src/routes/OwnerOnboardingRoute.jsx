import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import AccountLayout from '../components/layout/AccountLayout';
import { getOnboarding } from '../services/ownerService';
import { onboardingDestination } from '../utils/onboarding';

export default function OwnerOnboardingRoute() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const key = `${user?.id ?? ''}:${pathname}`;
  const [state, setState] = useState({});
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    getOnboarding(key).then(data => {
      onboardingDestination(data.onboarding_status, pathname);
      if (active) setState({ key, data });
    }).catch(() => {
      if (active) setState({ key, error: true });
    });
    return () => { active = false; };
  }, [key, pathname, retry]);
  if (state.key !== key) {
    const loadingMessage = pathname === '/owner/profile' ? 'Loading profile…'
      : pathname === '/owner/settings' ? 'Loading privacy settings…' : 'Loading your studio…';
    return <AccountLayout><p role="status">{loadingMessage}</p></AccountLayout>;
  }
  if (state.error) return <AccountLayout><div className="account-error" role="alert">Unable to load your studio onboarding state.<button className="account-secondary" onClick={() => { setState({}); setRetry(n => n + 1); }}>Retry</button></div></AccountLayout>;
  const destination = onboardingDestination(state.data.onboarding_status, pathname);
  if (destination) return <Navigate to={destination} replace />;
  return <Outlet context={{
    onboarding: state.data,
    updateOnboarding: data => {
      setState({ key, data });
    },
  }} />;
}
