// Accept only an internal shared-gallery path; never redirect to an arbitrary URL.
export function safeShareReturn(value) {
  return typeof value === 'string' && /^\/sharing\/[A-Za-z0-9_-]+$/.test(value) ? value : null;
}
export function shareReturnFromSearch(search) {
  return safeShareReturn(new URLSearchParams(search).get('returnTo'));
}
