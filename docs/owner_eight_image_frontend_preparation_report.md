# Studio Owner 8-Image Frontend Preparation

**Date:** 2026-11-05  
**Status:** Frontend prepared for a future backend update. Eight-image generation is **not live**.

## Summary

The Studio Owner frontend now uses a shared, configurable batch contract for owner-only copy, confirmation, result validation, loading skeleton count, and request timeout. The production contract remains **4 images / 4 credits** because the current owner backend still implements four. New submissions are blocked unless the server-returned `batch_cost` matches the configured contract and the server allows generation.

The eight-image behavior is covered with mocked UI contracts only. An explicit eight-image mock renders eight cards, eight individual Camera Setup Guides and an eight-credit confirmation without changing the live configuration or making an eight-image API request.

Normal User generation remains at four images with its existing one-successful-free-generation allowance.

## Files changed

- [`frontend/src/config/ownerGeneration.js`](../frontend/src/config/ownerGeneration.js) — defines the live owner batch contract (`batchSize: 4`, `batchCost: 4`, current request timeout), fixed legacy four-image contract, and checks for backend agreement and gallery batch cardinality/charged credits.
- [`frontend/src/pages/owner/AIGenerator.jsx`](../frontend/src/pages/owner/AIGenerator.jsx) — renders configured owner batch details, cost confirmation, success validation and skeleton count; checks the server cost before generation; stores the contract with each pending idempotency key and blocks resubmission if the contract later changes.
- [`frontend/src/pages/owner/AIResults.jsx`](../frontend/src/pages/owner/AIResults.jsx) — shows the configured batch size and continues to display historical four-image batches after a future switch to eight.
- [`frontend/src/pages/owner/Dashboard.jsx`](../frontend/src/pages/owner/Dashboard.jsx) — uses the configured batch size for owner generation labels and disables generation navigation if the configured batch cost disagrees with the server entitlement.
- [`frontend/src/services/ownerAiService.js`](../frontend/src/services/ownerAiService.js) — uses the shared request timeout and configured cardinality for current-generation status validation; removes four-specific owner error wording.
- [`frontend/src/components/ai/GenerationLoader.jsx`](../frontend/src/components/ai/GenerationLoader.jsx) — supports a configurable image count. Its default remains four skeletons and the existing Normal User free-request message.
- [`frontend/tests/owner-ai.test.mjs`](../frontend/tests/owner-ai.test.mjs) — adds mocked eight-card, eight-guide and eight-credit coverage, historical four-image gallery compatibility, current four-image confirmation, and backend-contract mismatch disablement.
- [`frontend/tests/ai.test.mjs`](../frontend/tests/ai.test.mjs) — verifies the shared loader still renders four Normal User skeletons and can render eight when explicitly configured for an owner mock.

The shared image card and approved styles were reused; no theme or visual redesign was made.

## Mocked eight-image support

The owner components accept an explicit contract for isolated rendering/tests. The mocked eight-image contract verifies:

- Exactly eight generated image cards render only for a completed batch of eight.
- Each card renders its own Camera Setup Guide.
- Seven-image incomplete results remain hidden as successful batches.
- Confirmation displays and requests eight credits.
- A backend entitlement reporting four credits disables the eight-credit confirmation and surfaces an unavailable state.
- The configurable loader produces eight skeleton cards.
- Gallery validation accepts both historical four-image batches and the configured current batch size.

These are frontend mock results only. The API request does not accept a client-selected image count; the backend remains authoritative.

## Current live behavior

- The checked-in frontend contract is **4 images / 4 credits**.
- The current backend entitlement must return `batch_cost: 4` and `generation_allowed: true` before a new owner batch can be submitted.
- The current owner generation request and backend behavior are unchanged. No eight-image request field or new endpoint was introduced.
- Gallery cards continue to map every image returned by the backend. Four-image completed records remain valid historical records after the future frontend contract changes to eight only when the saved charge is four credits; an eight-image record must report the configured eight-credit charge. This prevents a four-image partial result from a new eight-image batch being treated as an older successful batch.
- When a request is stored for retries, its batch contract is persisted with the idempotency key. A request from a different contract is not resubmitted under the new contract; users are directed to check its existing status in the gallery.
- Normal User pages and service calls remain unchanged. The shared loader defaults to four and preserves its Normal User message.

## Backend integration dependencies and exact switch

After the backend eight-image work is deployed and verified, update **only the frontend contract values** in [`frontend/src/config/ownerGeneration.js`](../frontend/src/config/ownerGeneration.js):

1. Change `OWNER_GENERATION_CONTRACT.batchSize` from `4` to `8`.
2. Change `OWNER_GENERATION_CONTRACT.batchCost` from `4` to `8`.
3. Set `OWNER_GENERATION_CONTRACT.requestTimeoutMs` to the backend-approved end-to-end request timeout that accommodates eight provider calls and the deployment proxy/server limits. The present value is 1,300,000 ms and is not sufficient for eight sequential calls at the current default provider timeout.
4. Keep `LEGACY_OWNER_CONTRACT` and `LEGACY_OWNER_BATCH_SIZES` at four so older gallery records continue to display.
5. Update the mocked/current frontend test fixtures from four to eight for new owner batches, then run all frontend tests and the production build against the deployed eight-image contract.

The backend must first return entitlement `batch_cost: 8`, reserve/settle eight credits, return exactly eight persisted images with eight per-image guides, and support the approved timeout/recovery boundary. Until its cost agrees with the configured cost, the frontend disables new generation and does not submit. Do not change the live contract before those backend conditions are met.

## Validation

Commands were run from `frontend/`; tests use mocks and do not call Pollinations:

- `node tests/owner-ai.test.mjs` — **8 passed**, including mocked eight-image rendering, eight individual guides, confirmation, mismatch protection and historical gallery batches.
- `node tests/ai.test.mjs` — passed; Normal User four-card loader behavior and existing AI assertions remain intact.
- `node tests/account.test.mjs` — **43 passed**.
- `node tests/photography-plans.test.mjs` — **8 passed**.
- `npm run build` — passed.
- `git diff --check` — passed.

No backend source, database, migrations, subscription records, real credits, or Pollinations calls were touched.

## Remaining steps

- Complete and deploy the owner backend’s eight-image planning, reservation, persistence, recovery and timeout changes.
- Resolve and verify the backend accounting and end-to-end timeout/recovery contracts before changing frontend values.
- After backend deployment, update the three contract values above, update owner mocks for eight images, and run tests/build again.
- Perform isolated browser verification with a mocked provider and test owner account. Do not use live credits or Pollinations for verification.
