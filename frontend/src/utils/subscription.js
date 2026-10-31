export function activationDisabled(plan, status) {
  return !plan.activation_available || plan.code === 'pro' || !status ||
    (plan.code === 'trial' && !status.trial_available) ||
    (plan.code === 'basic' && ['basic', 'trial'].includes(status.plan));
}
export function activationConfirmed(status, onboarding) {
  return ['basic', 'trial'].includes(status?.plan) && onboarding?.onboarding_status === 'completed';
}
export function utcDate(value) {
  if (!value) return 'Unavailable';
  // Backend DATETIME values are UTC, not browser-local wall-clock times.
  const date = new Date(/[Zz]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString();
}
export function ownerError(error, fallback) {
  return typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : fallback;
}
export function validateStudioPhoto(file) {
  if (!file || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) return 'Choose a JPEG, PNG or WebP image.';
  if (!file.size || file.size > 5 * 1024 * 1024) return 'Choose an image no larger than 5 MiB.';
  return '';
}

// Refresh displayed entitlements through GET only; never activate a plan here.
export function watchSubscriptionRefresh(periodEnd, refresh, browser = window, now = Date.now()) {
  const focus = () => { if (!browser.document.hidden) refresh(); };
  browser.addEventListener('focus', focus);
  browser.document.addEventListener('visibilitychange', focus);
  const end = periodEnd && new Date(/[Zz]|[+-]\d\d:\d\d$/.test(periodEnd) ? periodEnd : `${periodEnd}Z`).getTime();
  // Bound timers and avoid retry loops when the client clock is ahead of the server.
  const timer = Number.isFinite(end) ? browser.setTimeout(refresh,
    Math.min(2147483647, Math.max(30000, end - now + 1000))) : null;
  return () => {
    browser.removeEventListener('focus', focus);
    browser.document.removeEventListener('visibilitychange', focus);
    if (timer !== null) browser.clearTimeout(timer);
  };
}
