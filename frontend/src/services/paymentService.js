import api from './api';
const plans = { user: ['starter', 'pro'], owner: ['starter', 'growth', 'unlimited'] };
function checkRole(role) { if (!plans[role]) throw new Error('Unsupported payment role'); }
export function getPaymentReadiness(role) { checkRole(role); return api.get(`/${role}/payments/readiness`).then(r => r.data); }
export const getUserPaidSubscription = () => api.get('/user/payments/subscription').then(r => r.data);
export async function startCheckout(role, plan, idempotencyKey) {
  checkRole(role);
  if (!plans[role].includes(plan)) throw new Error('Unsupported paid plan');
  const { data } = await api.post(`/${role}/payments/checkout`, { plan_code: plan, idempotency_key: idempotencyKey });
  const url = new URL(data.checkout_url);
  if (data.mode !== 'test' || url.protocol !== 'https:' || url.hostname !== 'checkout.stripe.com' || url.username || url.password)
    throw new Error('Checkout destination was not verified');
  return url.href;
}
export function userCheckoutAllowed(readiness, status) {
  return Boolean(readiness?.checkout_available && readiness?.paid_activation_available && status?.plan === 'free');
}

// Non-secret retry identifiers only. Keep them across the Stripe return/navigation.
export function checkoutRequestKey(role, userId, plan, storage) {
  const name = `frameora:checkout:${role}:${userId}:${plan}`;
  try {
    storage ??= window.sessionStorage;
    const saved = storage.getItem(name);
    if (saved && /^[A-Za-z0-9_-]{16,128}$/.test(saved)) return saved;
  } catch { /* A blocked storage still permits an in-memory request key. */ }
  const key = crypto.randomUUID();
  try { storage.setItem(name, key); } catch { /* Caller also retains the key in a ref. */ }
  return key;
}
export function clearCheckoutKey(role, userId, plan, storage) {
  try { storage ??= window.sessionStorage; storage.removeItem(`frameora:checkout:${role}:${userId}:${plan}`); } catch { /* Storage may be disabled. */ }
}
export function checkoutExpired(error) {
  return error.response?.status === 409 && error.response?.data?.detail === 'Checkout expired. Start a new purchase.';
}

export async function loadUserPaymentState() {
  const readiness = await getPaymentReadiness('user');
  let status = null;
  try { status = await getUserPaidSubscription(); }
  catch (error) { if (error.response?.status !== 503 || readiness.checkout_available) throw error; }
  return { readiness, status };
}
