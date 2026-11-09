# Studio Owner credit enforcement — Backend Phase 1

Date: 2026-11-05 (Asia/Colombo)

## Status and scope

**Completed and tested:** owner-only entitlement/eligibility APIs, saved photography-plan inputs, four-credit batch reservation/settlement, current-period accounting, trial expiry into Basic, immutable idempotent results, bounded on-demand recovery, private owner gallery/image retrieval, and camera-guide metadata preservation.

**No schema change is needed for this implementation.** Existing `CreditTransaction`, `Subscription`, `SubscriptionPlan`, `AIGeneration`, `AIResult`, and `MediaAsset` fields represent its state. No application tables or columns were added. Normal User free-generation routes and allowance logic remain separate.

**Pending next phases:** Copilot frontend integration, CustomerProject management, project/share-link downgrade enforcement, paid checkout/activation, scheduled recovery orchestration and conservative orphan-file reconciliation. None is implicitly enabled by this phase.

**Blocked features:** none within the implemented Phase 1 scope required schema approval. There are operational limitations below; this is tested backend source, not a live deployment or a claim that the frontend is wired to it.

## Files changed in this phase

Earlier working-tree photography/camera-guide changes were preserved. This phase added or modified only these backend/report files:

| File | Change |
| --- | --- |
| `backend/app/services/owner_entitlement_service.py` (new) | Central effective-plan, dates, period, available balance, renewal and four-credit affordability resolver |
| `backend/app/services/owner_generation_service.py` (new) | Reservations, idempotency, settlement/refund/recovery and owner results |
| `backend/app/routers/owner_ai.py` (new) | Separate authenticated owner APIs and saved photography-plan input routes |
| `backend/app/schemas/owner_ai.py` (new) | Owner entitlement and generation response contracts |
| `backend/app/services/subscription_service.py` | Extract shared expiry transition; preserve existing selection API shape and behavior |
| `backend/app/services/credit_service.py` | Read allowances from stored catalogue; fail closed on a negative/corrupt computed balance |
| `backend/app/middleware/ai_upload_limit.py` | Apply the existing 6 MiB multipart body bound to the separate owner generation route |
| `backend/app/main.py` | Register owner router and no-store image/eligibility response protection |
| `backend/tests/test_owner_credits.py` (new) | Disposable SQLite/API/provider/persistence recovery tests |
| `backend/tests/test_owner_credit_mysql.py` (new) | Opt-in private-instance InnoDB concurrency, recovery and ownership FK tests |
| `docs/owner_credit_backend_phase1_report.md` (new) | This handoff |

No frontend source, package files, dependencies, configuration, secrets, production data or Git configuration was changed in this phase. No Git add, commit or push was run.

## Reused services

- Existing bearer/JWT authentication, current database role checks, authenticated-snapshot checks and `lock_profile` User-row lock.
- Existing subscription catalogue validation, explicit Basic/Trial selection, unique trial history, anniversary calculations and grant keys.
- Existing photography-plan repository/service and validation, including clothing, outfit, extra instructions and equipment.
- Existing `build_image_prompt` and `planned_shots`: four distinct specifications, including Camera Setup Guides.
- Existing configured Pollinations provider, model and reference-photo edit contract.
- Existing immutable private PNG storage (file and directory fsync), private retrieval, and generation view/metadata parsing.

## API contracts

All new routes require an authenticated `owner`. Normal Users and admins receive 403; missing authentication receives 401. The existing `/ai/*` and `/plans` Normal User role restrictions remain unchanged. Existing `/owner/plans` remains the subscription catalogue.

| Method/path | Purpose |
| --- | --- |
| GET `/owner/entitlements` | Effective subscription and credit state; read-only |
| GET `/owner/ai/eligibility` | Same detailed entitlement/affordability response |
| POST `/owner/ai/generations` | Reserve and generate a four-image batch |
| GET `/owner/ai/generations` | Most recent 20 owner-credit generation records |
| GET `/owner/ai/generations/{generation_id}` | Private result/status lookup, including pending recovery deadline |
| POST `/owner/ai/generations/{generation_id}/recover` | Recover an overdue reservation; terminal requests are unchanged |
| GET `/owner/ai/images/{asset_id}` | Private successful image bytes, compatible with authenticated blob downloads |
| POST/GET `/owner/photography-plans` | Create/list the owner's saved photography requirements |
| GET/PATCH `/owner/photography-plans/{plan_id}` | Read/edit the owner's saved requirements |

The photography-plan endpoints do not implement CustomerProject management, public sharing or new subscription activation. They are necessary because existing Normal User plan routes intentionally reject owners.

### Entitlement response

Fields: `plan` (`basic`, `trial`, `pro`, or null), `status` (`active` or `unavailable`), `source_status` (`active`, `expired`, or `unavailable`), `previous_subscription_expired`, `subscription_id`, `subscription_start`, `subscription_end`, `remaining_credits`, `period_start`, `period_end`, `monthly_renewal_due`, `generation_allowed`, `batch_cost` (4), `reason`, `trial_available`, `max_projects`, `max_share_links`.

Dates follow the backend's existing naive-UTC convention. Limits are informational in Phase 1. `source_status=expired` explains a virtual Basic fallback before the expiry transition has been persisted. A virtual fallback can have `subscription_id=null`; generation materializes it atomically. `monthly_renewal_due` indicates an ungranted current Basic period; GET never inserts grants. Unavailable Pro is not returned as spendable credit.

### Generation request/response

Multipart fields, each at most once:
- `plan_id`: positive integer, must belong to the authenticated owner.
- `idempotency_key`: 16–128 ASCII letters/digits/underscores/hyphens. One stable key per logical request.
- `description`: optional, at most 2,000 characters; supplements the saved plan.
- `reference`: optional JPEG/PNG/WebP, at most 5 MiB, normalized through existing validation.

Unknown fields (including user IDs, subscription IDs, balances and credit amounts) and duplicate multipart fields are rejected. Query parameters follow the existing owner convention and are rejected. Client values never determine price, credits or subscription ownership.

Successful new generation returns 201. Replaying a terminal request returns 200 with the saved generation and `replayed=true`. Responses retain existing generation fields and `images[].guidance`, with additional `remaining_credits`, `reserved_credits`, `charged_credits`, `recover_after`, and `replayed`.

- `owner_reserved`: 4 credits reserved, no images, no settled charge; status lookup provides `recover_after`.
- `completed`: exactly four saved images and guides; charged credits = 4.
- `failed`: no images and charged credits = 0. A terminal failed key never starts generation again; a user-requested new attempt uses a new key.

Error behavior: 402 insufficient credits; 403 inaccessible plan/generation or unauthorized role (private image lookup uses existing non-enumerating 404); 409 conflicting inputs/in-progress key/too-early recovery or unavailable activation; 422 invalid fields; 503 provider/storage/database availability or uncertain completion. Generation-stage 503 and in-progress 409 include a safe `detail.generation_id` when known. A pre-reservation uncertain commit may return the existing generic database 503: retry the SAME key, never manufacture another key automatically.

## Credit lifecycle and concurrency

1. Authenticate and lock the actual User row. Current owner role/authentication is rechecked. All cooperating subscription/credit writers use that same first lock.
2. Hash the owner-scoped operation key. If it exists, compare the fingerprint of plan ID, trimmed additional description and normalized reference-image digest. Different inputs return 409. Matching input returns saved status; no new grant, debit or provider call occurs.
3. For a new request, verify plan ownership, recover up to 50 overdue reservations for that owner, resolve effective subscription and current credit period, and grant the current period only if needed.
4. Check available credits inside the serialized transaction. Insert `AIGeneration.status=owner_reserved` plus one `CreditTransaction` spend of -4 in that owner's subscription/period. Commit before any provider call. This spend is provisional until the generation becomes completed; it excludes reserved credits from available balance immediately.
5. Release database locks. Call the existing provider for four distinct images and write all four immutable private files durably. Partial/duplicate batches are failures, never completed results.
6. Reacquire the User lock, validate generation/debit/subscription ownership, pending status and recovery deadline. Persist four AIResult rows, four MediaAsset rows, per-image guidance and completed status in one transaction. Keep the original -4 entry; never add another settlement debit.
7. On a known pre-completion failure, roll back partial result rows and atomically set failed plus one +4 refund. Refund keys are deterministic per generation and owner, and the refund uses the ORIGINAL subscription and period. Replays cannot double-refund or regrant credits. Internal failure compensation locks the original account and validates the original debit even if the worker's authentication was revoked or the role changed during provider work; it cannot create new entitlements or publish results.

The existing unique operation and grant keys plus composite subscription-owner foreign key are reused. Backend checks additionally enforce generation and plan ownership. InnoDB tests confirm real User-row serialization, rather than relying on a process-local mutex or SQLite behavior. Negative computed balances fail closed; there is no client-supplied balance.

Database deadlocks/unavailability return the existing safe 503; there are no unbounded internal retry loops. Clients may retry with the same key using bounded backoff. No provider request is automatically retried for an existing key.

## Expiry, renewal and paid-plan behavior

- Trial starts only through the existing explicit Start Trial API, remains 100 total credits, and never refreshes monthly.
- At `now >= end_date`, protected new generation operations resolve Basic and persist the old subscription as expired plus one Basic subscription. Basic starts at the exact previous expiry timestamp, not the later request time. Existing deterministic fallback keys and active-slot uniqueness prevent concurrent duplicate fallback activations.
- Read endpoints describe this fallback without writing. Expired trial credits are excluded immediately.
- Basic receives 10 per current monthly anniversary period, with month-end clamping and no carryover or missed-period grants. Allowance values come from the existing validated plan records.
- A batch reserved while its subscription was valid may complete after a period/trial boundary within its recovery window. Its charge remains in its original period. A failed batch's refund likewise remains there and cannot resurrect expired credit into Basic or a later month.
- Pro checkout and activation remain disabled. No payment is simulated and no catalogue record is changed.
- Project/share-link limits are returned for future UI use; enforcement is deliberately pending Phase 2.

## Bounded recovery and uncertain outcomes

- Reservation recovery becomes available after 30 minutes from the generation's UTC creation timestamp. This exceeds the existing provider's maximum four sequential 300-second calls.
- Recovery is on demand: explicit owner recovery, retrying that key, or a new owner generation request (up to 50 expired reservations per request). GET endpoints do not mutate. No background scheduler was installed; an abandoned account may retain the reservation until one of these recovery paths runs.
- Recovery locks the owner and request, atomically marks failed and refunds the original period. A late worker checks the same persisted status and cannot publish after that fence. A generation that committed successfully is never refunded by recovery.
- A lost reservation commit acknowledgement never launches provider work; the same key resolves the record if committed, otherwise can reserve normally.
- A lost completion commit acknowledgement never triggers immediate refund or file deletion. GET/replay returns committed success if it exists. If the transaction did not commit, the pending request is recovered after its deadline without repeating provider work.
- After a crash/uncertain commit, up to four private files per attempt can remain without media references. They are not served by an incomplete generation. Automatic orphan deletion is intentionally not implemented: a separately reviewed reconciler must check durable references before removal. Known failure cleanup is performed only after failed/refund commit is confirmed.
- Remote provider output may exist even when a local batch is failed/refunded. The server never claims exactly-once remote delivery or cancellation; it guarantees no second provider invocation for the same persisted logical request key and fences local publication.

## Automated test results

All provider calls were mocked; no live Pollinations request or real credit use occurred.

- Full existing backend regression run: **161 passed, 3 skipped, 94 subtests passed**. The skipped tests were the first three opt-in MySQL tests before an explicit test socket was supplied. Existing authentication, JWT, Google OAuth, subscriptions, onboarding, Normal User free generation, gallery guidance and privacy checks passed.
- Updated owner/subscription focused run: **23 passed** (includes the added persistence fault tests).
- Final owner lifecycle run after refund-integrity and role-change compensation checks: **12 passed**.
- Final separate real-MySQL suite: **5 passed** — parallel overspend prevention; duplicate-key single provider call; concurrent expiry with one Basic activation/grant; concurrent recovery with one refund; cross-owner ledger foreign-key rejection.
- `git diff --check`: passed.

These counts describe separate runs and overlap; they are not an additive unique-test total. Existing Starlette/httpx and Authlib/httpx deprecation warnings remain. No dependency installation or upgrade was performed.

SQLite/API tests cover 10 -> 6 -> 2 balances and third-request rejection, 1–3-image/duplicate failures, reference upload, provider/storage/database failures, idempotent success and conflicts, original-period refunds, trial expiry/no carryover, monthly renewal, Pro rejection, forged fields/roles, guide retention, missing provider locks, interrupted work, lost commit acknowledgement, late-worker fencing, and publication rejection with safe compensation after a mid-request role change.

### Database safety

The live `frameora_db` was not connected to or changed during this implementation. Existing fixtures block the production SQLAlchemy engine. SQLite tests use disposable databases and image directories; OAuth fixtures use isolated Redis.

Real MySQL tests used the already-installed MySQL 8.0.46 binary with `--no-defaults`, a newly initialized data directory under `/tmp/frameora-owner-credit-y0cvvpe6`, `--skip-networking`, `--mysqlx=0`, and a private socket. The directory is mode 0700. No existing credentials/configuration/data directory was used. The test verifies its marker and `@@datadir` before creating a uniquely named test schema and mapped fixture tables on that disposable server only. No production migration file was executed. The isolated MySQL process was stopped after testing; its temporary directory remains available for inspection.

For a future isolated run, prepare a fresh marked temporary instance with networking disabled, then run:

```sh
FRAMEORA_TEST_MYSQL_SOCKET=/tmp/frameora-owner-credit-<temporary-id>/mysql.sock \
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_owner_credit_mysql.py -q
```

Without this explicitly supplied, validated temporary socket the suite skips; it never falls back to configured production MySQL. Do not point tests at the production socket.

## Pending Copilot frontend work

- Use `/owner/photography-plans` for owner requirements; leave Normal User routes untouched.
- Read effective entitlements and display current balance, period, expiry, and unavailable/insufficient/in-progress states. Treat returned limits as informational until Phase 2 enforces them.
- Generate one stable client request key per intended submission. Retain it across network failures; repeat the identical request or GET the returned generation ID. Never silently generate a new key on a timeout.
- Wire owner generation/gallery/image URLs, render the same per-image Camera Setup Guides, use authenticated blob downloads, and show four-card loading without fake progress.
- Handle 409 and 503 status lookup/recovery. A terminal failed replay is not a success; let the user explicitly start a new attempt with a new key.
- Keep Pro checkout disabled and do not implement client-side credit authority, automatic trial activation, or project/share enforcement as a substitute for backend checks.

## Manual verification instructions

Use an isolated test backend/database with an injected mocked provider. Do not test the following mutations against `frameora_db` or a live Pollinations account without separate authorization.

1. Create an owner test account, finish studio setup, explicitly select Basic, and create a saved photography plan through the owner endpoints.
2. GET eligibility: expect Basic, balance 10, cost 4, generation allowed. Submit two distinct keys: expect four private images each and balances 6 then 2. A third key must return 402 with zero provider calls.
3. Replay a completed key: same generation/images, no new debit/grant/provider request. Change its description/reference: expect 409. Try a second owner's plan/result and forged balance/subscription fields: expect rejection.
4. Mock 1–3 images, a timeout and a storage failure: expect 503, no published partial images, and one original-period refund. Replay the failed key: terminal failed response, no new generation.
5. In fixtures, reserve a request then stop its worker. Before 30 minutes, replay/recovery is 409. Advance the fixture clock past the deadline, recover twice, and verify only one refund. Resume a simulated late worker and confirm no publication.
6. Select Trial on a separate test owner. Verify one 100-credit grant. Advance the test clock to expiry, request a new batch, and verify Basic is anchored to exact expiry with 6 current credits after success. The old trial balance is never carried forward. Advance to the next Basic period and verify 10 before a new charge.
7. Simulate completion COMMIT acknowledgement loss: status/replay must return saved success without refund, or pending until recovery if COMMIT did not occur. Do not delete retained private files speculatively.
8. Refresh/re-authenticate and fetch owner gallery/images: the original four guides remain available. Verify Normal User free-generation routes/allowances remain unchanged and Pro activation remains unavailable.

No manual browser generation or live deployment was performed. Frontend work is deliberately deferred.
