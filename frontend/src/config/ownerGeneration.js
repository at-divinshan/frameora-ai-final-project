import configuration from '../../../owner-generation.config.json';

// FINAL PRODUCTION — 8 images / 8 credits — DO NOT DELETE
// TEMPORARY TESTING — 2 images / 2 credits
// One shared setting; rebuild frontend and restart backend after changing it.
const batchSize = configuration.studioOwnerBatchSize ?? 8;
if (![2, 8].includes(batchSize)) throw new Error('studioOwnerBatchSize must be 2 or 8');

export const OWNER_GENERATION_CONTRACT = Object.freeze({
  batchSize,
  batchCost: batchSize,
  requestTimeoutMs: 1_300_000,
});

export const LEGACY_OWNER_CONTRACT = Object.freeze({
  batchSize: 4,
  batchCost: 4,
});

export const LEGACY_OWNER_BATCH_SIZES = Object.freeze([2, 4, 8]);

export function ownerBatchContractMatches(entitlement, contract = OWNER_GENERATION_CONTRACT) {
  return Number.isInteger(entitlement?.batch_cost) &&
    entitlement.batch_cost === contract.batchCost;
}

export function ownerGenerationAllowed(entitlement, contract = OWNER_GENERATION_CONTRACT) {
  return entitlement?.generation_allowed === true &&
    ownerBatchContractMatches(entitlement, contract);
}

export function isCurrentOwnerBatch(
  images,
  contract = OWNER_GENERATION_CONTRACT,
  chargedCredits,
) {
  return Array.isArray(images) &&
    images.length === contract.batchSize &&
    chargedCredits === contract.batchCost;
}

export function isOwnerGalleryBatch(
  images,
  contract = OWNER_GENERATION_CONTRACT,
  chargedCredits,
) {
  if (!Array.isArray(images)) return false;
  if (images.length === contract.batchSize) return chargedCredits === contract.batchCost;
  return LEGACY_OWNER_BATCH_SIZES.includes(images.length) &&
    chargedCredits === images.length;
}

export function ownerContractsMatch(left, right) {
  return left?.batchSize === right?.batchSize && left?.batchCost === right?.batchCost;
}
