import { getPaymentReadiness, startCheckout } from './paymentService';
export const getOwnerPaymentReadiness = () => getPaymentReadiness('owner');
export const startOwnerCheckout = (plan, key) => startCheckout('owner', plan, key);
export function ownerCheckoutAllowed(readiness, status) {
  if (!readiness?.checkout_available || !readiness?.paid_activation_available || !status) return false;
  // Backend owns expiry decisions; it returns effective Free Basic after expiry.
  return status.plan === 'basic' || !status.plan;
}
