export const onboardingRoutes = {
  pending_studio: '/owner/studio-setup',
  pending_plan: '/owner/subscription',
  completed: '/owner/dashboard',
};
export function onboardingDestination(status, path) {
  const destination = onboardingRoutes[status];
  if (!destination) throw new Error('Unknown onboarding state');
  if (status === 'pending_plan' && path === '/owner/studio-setup') return null;
  if (status === 'completed' && ['/owner/profile', '/owner/settings', '/owner/subscription', '/owner/studio-setup'].includes(path)) return null;
  return path === destination ? null : destination;
}
export function validateStudio(values) {
  const errors = {};
  for (const [key, min, max] of [['studio_name', 2, 150], ['studio_phone', 7, 20], ['studio_address', 2, 255], ['studio_city', 2, 100]]) {
    const value = values[key]?.trim() || '';
    if (value.length < min || value.length > max || /[\p{C}]/u.test(value)) errors[key] = `Enter ${min}–${max} characters.`;
  }
  const phone = values.studio_phone?.trim() || '';
  if (!/^\+?[0-9 ()-]+$/.test(phone) || phone.replace(/\D/g, '').length < 7 || phone.replace(/\D/g, '').length > 15) errors.studio_phone = 'Enter a valid phone number with 7–15 digits.';
  const description = values.studio_description || '';
  if (description.length > 2000 || [...description].some(char => /\p{C}/u.test(char) && char !== '\n' && char !== '\t')) {
    errors.studio_description = 'Use no more than 2000 characters and avoid control characters.';
  }
  return errors;
}

export function studioSaveDestination(status) {
  return status === 'completed' ? '/owner/dashboard' : '/owner/subscription';
}

export function studioPhotoNotice({ busy, pending }) {
  if (busy) return 'Please wait for the studio photo update to finish before leaving.';
  if (pending) return 'Upload the selected photo or discard the selection before continuing.';
  return '';
}

// BrowserRouter has no data-router blocker. Guard its navigation methods and
// same-document history traversal while a photo would otherwise be abandoned.
export function guardStudioNavigation(navigator, browser, isBlocked, notify) {
  const originals = {};
  for (const method of ['push', 'replace', 'go']) {
    originals[method] = navigator[method];
    navigator[method] = function (...args) {
      if (isBlocked()) { notify(); return; }
      return originals[method].apply(this, args);
    };
  }
  const index = browser.history.state?.idx;
  let restoring = false;
  const pop = event => {
    if (restoring) { restoring = false; event.stopImmediatePropagation(); return; }
    if (!isBlocked()) return;
    const next = browser.history.state?.idx;
    if (Number.isInteger(index) && Number.isInteger(next) && index !== next) {
      event.stopImmediatePropagation();
      restoring = true;
      browser.history.go(index - next);
      notify();
    }
  };
  const unload = event => {
    if (isBlocked()) { event.preventDefault(); event.returnValue = ''; }
  };
  browser.addEventListener('popstate', pop, true);
  browser.addEventListener('beforeunload', unload);
  return () => {
    for (const method of Object.keys(originals)) navigator[method] = originals[method];
    browser.removeEventListener('popstate', pop, true);
    browser.removeEventListener('beforeunload', unload);
  };
}
