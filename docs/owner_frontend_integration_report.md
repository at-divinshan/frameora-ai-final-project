# Studio Owner Subscription and AI Generation Frontend Integration

**Date:** 2026-11-05  
**Scope:** Frontend integration with the backend contracts documented in [owner_credit_backend_phase1_report.md](./owner_credit_backend_phase1_report.md). No backend code or database changes were made.

## Files changed

- `frontend/src/pages/owner/Dashboard.jsx` — reads owner entitlements and existing plan catalogue, shows the server-returned plan, credits, period/expiry, project/share limits, and links to owner generation/gallery.
- `frontend/src/pages/owner/AIGenerator.jsx` — owner-only plan selection/creation, four-credit confirmation, reference image input, stable retries, uncertain/in-progress handling, complete-batch result display, and credit refresh.
- `frontend/src/pages/owner/AIResults.jsx` — private owner generation gallery, complete-batch-only image display, camera guides, and explicit overdue recovery.
- `frontend/src/services/ownerAiService.js` — authenticated client functions for the documented owner endpoints and status-aware friendly errors.
- `frontend/src/routes/AppRoutes.jsx` — adds `/owner/ai/generate` and `/owner/ai/gallery` within existing protected owner/onboarding routes.
- `frontend/src/components/layout/OwnerLayout.jsx` — enables owner AI generation and gallery navigation.
- `frontend/src/components/ai/GeneratedImageCard.jsx` — accepts an optional image-fetch function while retaining the existing Normal User image service as its default.
- `frontend/src/components/ai/GenerationLoader.jsx` — accepts owner-specific loading copy; default Normal User copy remains unchanged.
- `frontend/tests/account.test.mjs` — verifies both new routes remain inside authenticated owner role routing.
- `frontend/tests/owner-ai.test.mjs` — mocked API, entitlement, confirmation, idempotency, status, four-image and Camera Setup Guide checks.

The existing subscription page and trial activation flow were preserved. Its plan cards continue to use `/owner/plans` values, including the explicit **Start Free Trial** action and disabled Pro checkout/activation.

## Integrated backend endpoints

The owner screens use only Phase 1 endpoints verified in the report and route implementation:

| Method and path | Frontend use |
|---|---|
| `GET /owner/entitlements` | Current plan, available credits, dates, batch cost, generation eligibility, and project/share limits. |
| `GET /owner/photography-plans` | List owner-saved generation requirements. |
| `POST /owner/photography-plans` | Create an owner-saved photography plan using the existing plan form. |
| `POST /owner/ai/generations` | Multipart four-image generation using `plan_id`, `idempotency_key`, optional `description`, and optional `reference`. |
| `GET /owner/ai/generations` | Load recent owner generations and detect in-progress work. |
| `GET /owner/ai/generations/{generation_id}` | Explicit status check for an in-progress or uncertain request. |
| `POST /owner/ai/generations/{generation_id}/recover` | Explicit user-triggered recovery once the backend's recovery deadline is reached. |
| `GET /owner/ai/images/{asset_id}` | Authenticated private image download through the reused image card. |
| Existing `GET /owner/plans`, `GET /owner/subscription`, and Basic/Trial activation endpoints | Existing owner catalogue and subscription selection/trial flow; unchanged. |

## Completed UI behavior

- Dashboard entitlements are rendered from server responses, not client-side credit calculations. It shows the plan, available balance, the four-credit batch cost, period/expiry date, project limit, and share-link limit.
- Project and share-link **usage counts** remain unavailable; the backend returns limits only. The UI labels these limits informational because enforcement is deferred.
- Studio Owners can create/select a saved photography plan, provide an optional additional description, and attach an optional JPEG/PNG/WebP photo (up to 5 MiB).
- A separate review step asks for confirmation before submitting a chargeable batch and displays available credits and the four-credit cost.
- One in-flight submit is allowed. A request key is generated once and saved in session storage before the POST. Retries reuse that key and original plan/description; the original photo must be reselected after reload when one was attached.
- A returned or discovered `owner_reserved` generation blocks another submission. The UI offers explicit status checking and the gallery route; it does not automatically resubmit, poll, or recover.
- Network/503 uncertainty retains the same key. If the backend supplies a generation ID, the page queries its status. It never silently creates a new key after an uncertain result.
- Only completed generations with exactly four images render as successful cards. Existing private download and Camera Setup Guide presentation is reused. Failed or incomplete records are not presented as a successful image batch.
- Owner gallery recovery is explicit and appears when the backend `recover_after` time has arrived. The backend remains the authority for whether recovery is permitted.
- The Normal User generator, free allowance endpoints, and image fetch defaults are unchanged.
- Existing Free Basic/Free Trial/Paid Pro cards remain server-catalogue-driven. Trial activation still requires the explicit button. Pro checkout and activation remain disabled.

## Test and build results

Commands were run from `frontend/`; tests use mocked API adapters and render components without connecting to a backend:

- `node tests/account.test.mjs` — **43 passed**, including owner route role-gating, subscription, onboarding, and Normal User regression checks.
- `node tests/ai.test.mjs` — **assertion script passed**; existing Normal User generation service, private image route, loading skeletons, and guide markup checks passed.
- `node tests/photography-plans.test.mjs` — **8 passed**.
- `node tests/owner-ai.test.mjs` — **7 passed**, covering verified paths/payloads, repeated stable request keys, entitlement and credit display, explicit four-credit confirmation, error/status messages, four image cards, guides, incomplete-batch hiding, and plan-card values/disabled Pro.
- `npm run build` — **passed** with Vite production build.
- `git diff --check` — **passed**.

No live Pollinations request, real credit use, subscription mutation, database connection, migration, or dependency installation was performed.

## Remaining backend dependencies and limitations

- Phase 1 owner endpoints must be deployed and reachable before these pages can operate. This task did not validate a running backend or live database.
- Recovery remains on demand after 30 minutes. Gallery shows recovery when eligible; it does not install or assume a scheduler.
- The generation-list API returns the most recent 20 records. The UI checks those records for pending batches and also handles a pending/conflicting generation returned by the POST contract.
- Project and share-link limits are display-only until backend Phase 2 enforces oldest-first preservation and read-only/disabled behavior. Usage counts are not supplied.
- Paid Pro payment and activation remain unavailable.
- A backend uncertain completion may leave private orphan image files. This frontend neither deletes files nor treats an uncertain response as success; server-side reconciliation remains pending.
- No API contract blocker was encountered for the Phase 1 integration. The UI does not call the alternative `/owner/ai/eligibility` alias because `/owner/entitlements` already returns the required entitlement fields.

## Manual browser verification

Use an isolated development backend and mocked provider responses. Do not submit a generation request to a live provider or a database containing real owner credits.

1. Sign in as a Studio Owner with completed onboarding. Confirm a Normal User or Admin session cannot enter the owner routes.
2. Open the dashboard and verify plan name, server credit balance, expiry/period date, project/share limits, and Generate Images navigation.
3. Open Subscription and verify Free Basic, Free Trial, and Paid Pro values. Confirm Pro remains disabled and trial begins only after explicitly selecting **Start Free Trial**.
4. Open owner AI generation. Create or select an owner photography plan, attach a mock reference photo if desired, and review the displayed four-credit charge before confirming.
5. In a mocked successful response, verify exactly four cards render, all Camera Setup Guides remain visible, the images download through the owner image endpoint, and the displayed credits refresh.
6. Mock HTTP 402, 409 with `generation_id`, 503 with/without `generation_id`, and 401/403. Confirm insufficient-credit and access messages, in-progress blocking, and uncertain-status handling. Retry only with the same request key and inputs.
7. Mock an incomplete completed response and a failed terminal response. Confirm neither shows successful image cards; only an explicitly new attempt gets a new key after a known terminal outcome.
8. Mock an overdue `owner_reserved` gallery item and use the explicit recovery button. Before the recovery deadline, verify the page does not automatically invoke recovery.
9. Run the existing Normal User generator/gallery flows against mocked endpoints and verify its one-successful-free-request behavior remains unchanged.

Do not use browser verification to test a real AI call, spend live credits, or mutate live subscription records.
