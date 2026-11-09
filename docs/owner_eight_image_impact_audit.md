# Studio Owner Eight-Image Generation Impact Audit

**Date:** 2026-11-05  
**Scope:** Read-only source audit of the proposed Studio Owner change to exactly eight generated images per successful batch. No application code, database, migrations, or generation records were changed. No provider calls or secrets were accessed.

## Executive summary

The current Studio Owner path is consistently implemented for **four images at four credits per batch**. It reserves four credits before provider work, returns the debit as a refund if generation or persistence fails, and keeps the debit only after a complete batch is persisted. Generation metadata is stored per asset, and the gallery retrieves all assets for a completed generation; neither response schema nor the mapped asset tables impose a four-row database limit.

The eight-image requirement needs coordinated changes to the owner entitlement and generation services, shared shot planner/provider, owner UI and its tests. The shared provider and planner are also used by Normal User generation, which must remain four images with its existing one-successful-free-generation allowance. Keep that count explicit at each caller rather than globally changing the Normal User path.

**Migration assessment:** The inspected models and repository migrations show no per-generation four-image constraint, so eight assets and guides appear representable without a migration. This is a code/schema-definition finding, not verification of the currently deployed database. A live database schema was not queried. Also, the requirement that a batch be *reserved* and only *charged* after success needs a precise accounting interpretation: the existing ledger writes a negative `spend` row at reservation time and refunds it on failure. If reservation is an unavailable-credit hold and the spend is considered settled only after completion, current behavior can be adapted. If the ledger must contain no spend until completion, the current schema/ledger contract may need redesign and approval.

## Existing files and behavior

### Studio Owner backend

| File | Existing function/contract | Eight-image impact |
|---|---|---|
| [`backend/app/services/owner_entitlement_service.py`](../backend/app/services/owner_entitlement_service.py) | `BATCH_COST = 4`; `resolve_locked` exposes `batch_cost`, balance and `generation_allowed`. | Change owner batch cost to 8. Confirm all balance/eligibility consumers use this single value and do not hardcode a separate four-credit threshold. |
| [`backend/app/services/owner_generation_service.py`](../backend/app/services/owner_generation_service.py) | `request_hash`, `operation_key`, `_reserve`, `_refund_locked`, `_recover_expired_locked`, `_response_locked`, `generate`, gallery/read/recovery functions. Reserves a spend row, persists results and guides, refunds failed work, and fences late workers. | Reserve/refund/response accounting must use 8. Completion count, recovery deadline, comments and result validation must be updated. Preserve existing key/hash and recovery semantics. |
| [`backend/app/routers/owner_ai.py`](../backend/app/routers/owner_ai.py) | Owner-only multipart `POST /owner/ai/generations`; status, recovery, gallery and private image routes. | Request fields need not change if the API remains owner-authenticated and server-controlled. |
| [`backend/app/schemas/owner_ai.py`](../backend/app/schemas/owner_ai.py) and [`backend/app/schemas/ai.py`](../backend/app/schemas/ai.py) | `OwnerGenerationResponse` extends `GenerationResponse`; `images` is an unbounded list of `GeneratedImage`; guidance includes an optional `CameraSetupGuide`. | Schema shape already permits eight image entries. Consider enforcing owner successful cardinality in service/tests; do not make Normal User responses eight. |
| [`backend/app/services/generation_planning.py`](../backend/app/services/generation_planning.py) | `planned_shots` returns four pose/composition records. `_camera_setup` uses four-entry tuples indexed by shot number. `build_image_prompt` refers to a four-shot series. | Create exactly eight specifications and guide variants; every indexed guide value must cover all eight indices. Keep each pose/composition meaningfully distinct and ensure the prompt describes eight shots. |
| [`backend/app/services/pollinations_service.py`](../backend/app/services/pollinations_service.py) | `generate_images` requires four `shots`, then makes one serial provider request per shot (`n=1`), checks one valid image per response and rejects duplicate image bytes. Shared with Normal User generation. | Support the owner’s eight shots without changing the Normal User caller’s four. Retain one-image-per-shot validation and byte-level duplicate rejection. |
| [`backend/app/services/ai_service.py`](../backend/app/services/ai_service.py) | Shared result serialization, per-generation asset retrieval and private image fetch. Its Normal User `generate` uses `len(images) == 4`, writes each asset and a guide keyed by asset ID, and completes the free allowance atomically with the database rows. | This is the Normal User path and should remain four images. Avoid changing its free allowance or four-image completion rule to satisfy the owner requirement. Shared serialization already returns every associated asset. |
| [`backend/app/routers/ai.py`](../backend/app/routers/ai.py) and [`backend/app/services/free_generation_service.py`](../backend/app/services/free_generation_service.py) | Normal User-only `/ai/*` endpoints and the existing one-successful-free-generation allowance. | Preserve route separation and behavior; add regression tests proving a normal request remains four images and consumes its allowance only once on success. |

### Studio Owner frontend

| File | Existing four-image assumption |
|---|---|
| [`frontend/src/pages/owner/Dashboard.jsx`](../frontend/src/pages/owner/Dashboard.jsx) | “Generate four images” action label. The credit cost is already read from the server. |
| [`frontend/src/pages/owner/AIGenerator.jsx`](../frontend/src/pages/owner/AIGenerator.jsx) | Plan summary, result validation/display, confirmation copy/button, review button, loading copy, and success heading require exactly four images or four credits. |
| [`frontend/src/pages/owner/AIResults.jsx`](../frontend/src/pages/owner/AIResults.jsx) | Gallery considers only completed generations with exactly four images complete. |
| [`frontend/src/services/ownerAiService.js`](../frontend/src/services/ownerAiService.js) | Insufficient-credit and pending status messages say four-image/four-credit; completed status validation requires four images. |
| [`frontend/src/components/ai/GenerationLoader.jsx`](../frontend/src/components/ai/GenerationLoader.jsx) | Shared skeleton has exactly four cards and default Normal User copy says four; owner currently supplies its own four-image message. Make the owner count configurable or pass an owner-specific count while preserving the Normal User default. |
| [`frontend/src/components/ai/GeneratedImageCard.jsx`](../frontend/src/components/ai/GeneratedImageCard.jsx) | One image card renders its own saved guide and authenticated download. No four-image limit here; reuse for all eight. |
| [`frontend/src/routes/AppRoutes.jsx`](../frontend/src/routes/AppRoutes.jsx), [`frontend/src/components/layout/OwnerLayout.jsx`](../frontend/src/components/layout/OwnerLayout.jsx) | Existing owner generation/gallery routes and navigation already exist; no count limit identified. |

The owner route contract in [`backend/app/routers/owner_ai.py`](../backend/app/routers/owner_ai.py) remains multipart `plan_id`, `idempotency_key`, optional `description`, optional `reference`. The response extends the common generation object with `remaining_credits`, `reserved_credits`, `charged_credits`, `recover_after`, and `replayed`; successful `images[]` entries each contain an ID, private URL and guidance. The entitlement response supplies `remaining_credits`, `generation_allowed`, and `batch_cost`. No new client-supplied credit field should be added.

## Reservation, settlement, idempotency and recovery

- `BATCH_COST` is 4. `_reserve` locks the owner, checks plan ownership, performs expiry/recovery/credit resolution, persists the idempotency debit and commits before contacting the provider. That is the atomic balance protection point.
- The debit is a `CreditTransaction` of type `spend`, currently `-4`, and also serves as the reservation. Success retains it; failure inserts one idempotent refund to the debit’s original subscription/period. Responses report pending credits as `reserved_credits`, completed credits as `charged_credits`, and failed charges as zero.
- `operation_key` is a SHA-256 digest scoped to `owner-generation:v1:` and unique per user. `request_hash` fingerprints the submitted plan ID, normalized description and optional reference bytes’ SHA-256. A matching key replays the saved terminal result or returns in-progress; a changed fingerprint conflicts. The saved plan’s later edits do not change the existing request hash. Failed keys remain terminal; a deliberate new attempt uses a new key.
- Recovery is on demand after `RECOVERY_AFTER` (30 minutes). Expired pending work is fenced as failed and refunded once. A late worker cannot publish after the fence. Uncertain completion commits retain files and are checked by generation ID/key rather than refunded speculatively; the documented backend limitation is possible private orphan files requiring later reconciliation.
- The current provider makes four serial calls. `pollinations_timeout_seconds` defaults to 180 seconds and is configurable up to 300. Eight serial calls can therefore take up to 40 minutes at the configured maximum, exceeding the current 30-minute recovery fence. The owner Axios timeout is 1,300,000 ms (21m40s), less than eight calls at even the current 180-second default (24 minutes), before overhead. The recovery deadline, HTTP client timeout and any deployment proxy/request timeout must be made compatible with the intended eight-call upper bound. An expired fence during a legitimate eight-image request could refund/fail work that is still running.

## Pose planning, persistence and gallery

- Existing `planned_shots` has four pose variants (standing, seated, walking and over-the-shoulder) and a special four-item side-angle variant. `_camera_setup` has four-item distance, lens/zoom, lighting-direction, framing and focus tuples addressed by index. Simply requesting eight shots would not create eight valid plans and can index past those tuples.
- Each shot dictionary currently includes a `pose_name`, `camera_angle`, `shot_type`, `camera_position`, `instructions`, and a full `camera_setup` with seven steps. One guide is saved for each asset in `AIGeneration.guidance_text`, keyed by asset ID, and `GeneratedImageCard` renders an independent guide and download per image. Keep the eight shots, images and asset IDs paired in the same order; test all eight guide associations.
- Owner generation checks image-byte uniqueness, writes each normalized private image before database finalization, then inserts one `MediaAsset` and one `AIResult` per image. It commits all rows, metadata and completed status together. The gallery list returns the latest 20 owner generations, not a capped number of images inside each generation; private image retrieval checks owner and successful status.
- Byte uniqueness only proves the files differ, not that the provider followed eight distinct poses/compositions. The UI explicitly describes guidance as planned and not visually verified. Distinct shot specifications can be tested deterministically; semantic image diversity requires a separate product/quality review and cannot be guaranteed by current response validation.

## Existing tests and mocks affected

- [`backend/tests/test_owner_credits.py`](../backend/tests/test_owner_credits.py) mocks `pollinations_service.generate_images` with the shared four-image `IMAGES` fixture. Relevant cases include `test_basic_two_batches_then_insufficient_no_provider`, `test_incomplete_duplicate_provider_and_storage_failure_refund_once`, `test_same_key_success_replays_and_changed_inputs_conflict`, `test_trial_total_expiry_and_monthly_no_carryover`, `test_interrupted_reservation_deadline_refund_and_late_worker_fence`, `test_success_commit_ack_loss_never_refunds_or_regenerates`, and `test_uncommitted_completion_is_recovered_without_repeating_provider`. Assertions currently expect four images, four credits, and four stored files.
- [`backend/tests/test_owner_credit_mysql.py`](../backend/tests/test_owner_credit_mysql.py) is opt-in against a marked disposable MySQL instance and mocks the provider with the same four-image fixture. Its parallel-batch test starts with 10 Basic credits and expects two successful four-credit requests and eight total assets. At eight credits per batch, that fixture should expect one success, one 402 and eight assets; use a separately seeded balance of at least 16 to test two concurrent successful eight-credit batches.
- [`backend/tests/test_ai.py`](../backend/tests/test_ai.py) supplies the Normal User fixture (`IMAGES` contains four PNGs) and mocks the same shared provider. `test_success_persists_four_and_consumes_once_with_private_retrieval`, failure/partial-output cases, the four-distinct-prompts provider contract, guide tests, and no-retry tests are important Normal User regression coverage. Keep these expectations at four.
- [`frontend/tests/owner-ai.test.mjs`](../frontend/tests/owner-ai.test.mjs) currently mocks `batch_cost: 4`, checks four-credit confirmation, creates four image fixtures, expects four cards/guides, and verifies incomplete three-image batches are hidden. Update owner mocks/expectations to eight; add exact-eight and seven-image incomplete checks.
- [`frontend/tests/ai.test.mjs`](../frontend/tests/ai.test.mjs) explicitly expects four Normal User skeletons and verifies card/download/guide behavior. It should remain four and continue to pass unchanged (or be extended only with owner-specific loader coverage).

## Database compatibility and migration assessment

Source inspection of [`backend/app/models/ai_generation.py`](../backend/app/models/ai_generation.py), [`backend/app/models/ai_result.py`](../backend/app/models/ai_result.py), [`backend/app/models/media_asset.py`](../backend/app/models/media_asset.py), [`backend/app/models/credit_transaction.py`](../backend/app/models/credit_transaction.py), and [`backend/migrations/003_owner_subscriptions.sql`](../backend/migrations/003_owner_subscriptions.sql) found:

- `AIGeneration.guidance_text` maps to MySQL `LONGTEXT`; it stores per-image guidance JSON and is not constrained to four entries.
- `AIResult.generation_id` is a non-unique association. `MediaAsset.generation_id` is nullable and has no per-generation unique/cardinality constraint in the inspected model.
- The ledger’s unique owner/operation key allows one spend per logical idempotent batch; its one-to-one grant uniqueness is scoped to a grant period and does not limit image rows.
- These definitions support eight assets and eight guide entries without a structural schema change. There is no inspected constraint requiring an image-count column or a separate guide table.

**No migration is indicated for image cardinality alone.** The current installed `frameora_db` structure was not queried, so deployment compatibility must be confirmed against the real schema before rollout. If “charge only after save” means the database must not record a `spend` until completion, the current reservation-as-spend ledger does not encode a distinct hold/settled state; resolve that accounting requirement before declaring no migration necessary.

## Risks and blockers requiring approval

1. **Accounting semantics:** Confirm whether a negative spend transaction at reservation is an acceptable hold, with `charged_credits=8` only after successful commit, or whether the ledger must defer the spend transaction itself until success. The latter is a design/schema decision, not a UI-only change.
2. **Provider cost and latency:** Eight sequential provider requests approximately double provider calls, request latency, memory retained for images, private storage writes, and potential partial-failure cost compared with four. Confirm provider budget/throughput and acceptable maximum wait/recovery interval. No live provider call was made for this audit.
3. **Partial provider success:** If any call fails after earlier calls succeed, the batch must be non-billable and all 8 images hidden; the reservation must refund once. Provider charges already incurred for partial calls may not be refundable. Do not retry failed batches automatically with a new idempotency key.
4. **Durability boundary:** Filesystem fsync and database commit are separate durability systems. The existing uncertain-commit behavior intentionally avoids deleting/refunding when commit outcome is unknown. Eight outputs increase orphan-file/space exposure and the need for later reconciliation.
5. **Timeout agreement:** Choose recovery/request/proxy timeout bounds that accommodate the maximum configured provider time for eight serial calls. If product expects a shorter wait, approve a concurrency or cancellation design; do not silently let the existing 30-minute recovery fence race the longer work.
6. **Meaning of “distinct”:** Confirm that eight deterministic prompts/specifications and unique returned files are the acceptance criterion, or require a separate visual quality review. Existing code does not perform semantic/visual validation.

## Implementation classification

### Codex — backend/security-sensitive work

- Update owner-only `BATCH_COST`, atomic reservation/refund accounting and completed-charge response to exactly 8, preserving original-period refund, idempotency, subscription expiry, owner checks and concurrency protections.
- Expand the owner shot planner to eight distinct poses/compositions and eight compatible per-shot Camera Setup Guides. Keep the Normal User planner/provider call at four.
- Make the shared provider accept the explicit caller’s shot count while preserving four for Normal Users; enforce exactly one valid, distinct output per shot and exactly eight for owner success.
- Update owner completion persistence and response validation to publish/charge only a complete eight-image set with eight matching guide records. Preserve all-or-nothing database visibility and private media handling.
- Reconcile the 30-minute recovery fence with configured provider maximum and end-to-end HTTP/proxy timeouts. Preserve fencing, terminal idempotency and recovery behavior.
- Determine whether reservation-as-spend meets the approved charge rule. If not, design/approve the ledger/schema change before implementation or migration.
- Add backend regression and concurrency tests, including no overspend, one refund, recovery/late-worker behavior, uncertain commit behavior and Normal User isolation.

### Copilot — safe frontend work after backend contract is finalized

- Update owner-only copy and use server `batch_cost` for confirmation and credit display; show an eight-card loading skeleton and exactly eight completed cards/guides in both generator and gallery.
- Keep incomplete batches hidden, preserve private downloads, idempotency/status/recovery UX and the existing owner routes.
- Keep Normal User copy, four skeletons, four result cards, routes and free allowance unchanged.
- Update mocked frontend tests for eight owner images and run existing Normal User regression tests and production build. Do not invent a new API field or client-side credit calculation.

## Recommended test strategy

1. **Planning:** Assert exactly eight shot specifications, unique pose names and composition/position pairs, valid seven-step guide schema on every shot, and correct ordering/pairing. Include each saved camera-angle preference and multi-person plans.
2. **Provider:** With mocked HTTP responses, assert exactly eight sequential requests, one output each, correct shot prompt per request, complete-count enforcement, duplicate image rejection, and no extra calls on idempotent replay. Never call Pollinations in tests.
3. **Credits and persistence:** Mock eight images and assert one atomic `-8` reservation, eight `MediaAsset` and `AIResult` rows, eight guide entries, successful charged count 8 and correct remaining balance. Test insufficient balance causes no provider call.
4. **Failure boundaries:** Fail or return incomplete/duplicate output at each position 1–8; inject each image-write failure and database flush/commit failure. Assert no partial success is visible, a single original-period refund restores all 8 credits, and uncertain commits retain files/status for same-key checking without unsafe refund/deletion.
5. **Concurrency/idempotency/recovery:** Concurrent requests at balances 8 and 16; same key concurrent replay; changed inputs conflict; one refund on repeated recovery; late worker fenced; expiry during generation; timeout/recovery boundary beyond the longest valid eight-call request.
6. **Normal User regression:** Exercise existing `/ai/generations` with four mocked images, check four cards/guides and verify failed requests preserve the one-successful-free-generation allowance while successful requests consume it once.
7. **Frontend mocks:** Confirm server batch cost 8, insufficient-credit state, explicit 8-credit confirmation, stable same-key retries, in-progress/uncertain handling, 8 loading skeletons, exactly 8 image cards and guides in generator/gallery, incomplete result suppression, image download behavior and unchanged Normal User four-card behavior.
8. **Database:** Run isolated MySQL tests on a disposable instance matching the deployment schema. Verify row counts, existing foreign/unique constraints and transaction rollback. Independently inspect live schema read-only before release; do not run migrations as part of this audit.

## Audit boundaries

The backend and frontend reports read for this audit are [`owner_credit_backend_phase1_report.md`](./owner_credit_backend_phase1_report.md) and [`owner_frontend_integration_report.md`](./owner_frontend_integration_report.md). This report is based on repository source, model/migration definitions, test code and those reports. No live database query, provider request, source edit, migration, or generation was performed. The frontend/backend reports describe a four-image implementation and will need a future, separately approved update after the eight-image feature is implemented and verified.
