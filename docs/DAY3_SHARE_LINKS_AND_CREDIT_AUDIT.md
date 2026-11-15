# Day 3 remaining work: Share Links and credit rules

## Implemented

The previously empty `frontend/src/pages/owner/SharedLinks.jsx` is now the single Owner management page at `/owner/share-links`, enabled through the existing Owner sidebar and role/onboarding route guards. It lists all owned project links (including inactive/archived history) and legacy unassigned links whose generation belongs to the Owner. Lists are paginated (50), support project filtering, and show project, original batch, status, dates and accessible numbered phases.

Copy uses the existing per-user/per-project session cache created by ProjectWorkspace. URLs are validated as same-origin `/sharing/{43-character-token}` paths. The API never exposes token hashes. Missing cached URLs are explicitly unavailable: one-way hashes cannot reconstruct original tokens. No token is rotated and no existing customer link is replaced. Persistent recovery of all old URLs is impossible with the current records; any future recoverable-token storage design would apply prospectively and needs separate security/schema review.

Activation reuses the existing token and grants, validates Owner/project/link ownership, rejects expired links and archived/read-only projects, and enforces the current active-link limit under the Owner lock. Deactivation uses the existing service. These actions do not grant credits. Expired URLs cannot be reactivated by extending expiry silently.

Completed unpublished phases can be published through the existing Day 2 endpoint, after confirmation. Already accessible phases are excluded from the picker. The existing server-side unique publication constraint and locking make retries idempotent. Original batches, existing comments, preview protection and share expiry remain in force. No new link is created by publishing a phase.

Unassigned legacy links are displayed but cannot be activated or published through project-scoped controls. The application does not invent their project association or broaden existing customer access.

The existing strict Owner query guard now accepts only `project_id`/`before` on the management GET, with no duplicates and positive integer validation. An essential Day 2 compatibility fix allows the existing project-gallery `before` parameter; the prior guard rejected it despite the endpoint supporting pagination. Other unsupported query fields remain rejected.

## Subscription/credit audit

| Rule | Actual result |
|---|---|
| Normal Free: four images once per account | Enforced by `free_generation_service` and `ai_service`; one reservation and one successful four-image request. Failed confirmed attempts release the allowance. Existing consumed/reserved history is unchanged. No monthly reset. |
| Free catalogue/display | Fixed the obsolete 10-monthly-credit promise. Shared JSON now describes zero credit allocation and four free images; UI says once per account. This is catalogue metadata, not a balance write. |
| Normal Starter | LKR 490/month, 40 credits per paid period, displayed only. Paid activation remains unavailable. |
| Normal Pro | LKR 990/month, 100 credits per paid period, displayed only. Paid activation remains unavailable. |
| Normal paid cost | Approved 2 credits/image documented in backend catalogue and UI. NOT operationally charged yet: there is no paid Normal User generation/reservation path. A four-image paid batch would require 8 credits when implemented. Free images are not charged. |
| Normal no carryover | Displayed/documented for future paid periods. No paid period allocation exists yet, so this is not presented as a live ledger feature. |
| Owner Basic | 10 credits per monthly subscription anniversary; 2 editable projects, 3 active links. Current-period sums prevent carryover. Unused old-period ledger rows are retained. |
| Owner Trial | Explicit activation only; one trial per account enforced by history/unique constraints. Exactly 14 days, 100 total credits, 10 projects, 20 active links. Expiry falls back to Basic without deleting history. |
| Owner Pro | Existing LKR 1500/month, 500 credits, 50 projects, 100 links preserved. Paid activation still disabled. |
| Owner batch/cost | `owner-generation.config.json` unchanged: 2 images / 2 credits. One credit/image Owner accounting is preserved; the 2-credit/image rule applies to the requested Normal User paid plans. |
| Owner deductions/refunds | Existing serialized reservation, request hash/idempotency keys, unique ledger operations, and original-period refunds preserved. Failed/overdue requests refund once; uncertain completion acknowledgements do not trigger unsafe extra generation/refunds. |
| Authorization | Existing JWT/current-account checks, server-derived roles, Owner onboarding/project access and subscription checks remain in force. Clients cannot activate paid plans by sending `paid`, role, balance or plan values. |

Sources inspected: `free_generation_service.py`, `ai_service.py`, `subscription_service.py`, `owner_entitlement_service.py`, `credit_service.py`, `owner_generation_service.py`, subscription/credit/payment models, subscription routes/catalogues, migration 003, frontend subscription displays/configuration, and their existing tests.

## Day 4 Stripe dependencies — not implemented

- Server-selected prices/roles and verified signed webhooks. Never activate from a frontend success page, checkout selection or client-supplied amount.
- Persist unique provider event IDs and paid invoice/payment IDs to prevent replay and duplicate period allocation. Bind payments to the authenticated account and approved plan.
- Add an approved schema design for Normal User Starter/Pro subscriptions and credit periods. Migration 003 currently restricts plan codes/kinds to `basic`, `trial`, `pro`, and credit services explicitly require Owner plans; reusing them unchanged for Normal Users is unsafe.
- Existing `Payment` records expose only user/subscription, amount, status and timestamp. They do not provide a sufficient provider-event/payment identity ledger for Stripe replay protection.
- Implement Normal paid generation reservations at 2 credits/image, unique request deductions, confirmed-failure refunds to the original period, expiry checks and one allocation per verified paid period. Preserve the independent one-time free allowance.
- Define free-versus-paid use ordering, proration/upgrades, cancellations, payment failures, refunds/chargebacks and out-of-order webhook handling before implementing them.

No Stripe integration, new payment migration, paid grants or payment transactions were added. No migration is needed for this management page/catalogue correction. Phase publication still depends on the already-prepared Day 2 migration 010; the UI reports its absence. No migrations were executed.

## Files changed

- `backend/app/services/share_service.py`
- `backend/app/services/user_subscription_catalogue.py`
- `backend/app/schemas/sharing.py`
- `backend/app/routers/sharing.py`
- `backend/app/routers/owner.py`
- `backend/tests/test_share_management.py` (new)
- `backend/tests/test_user_subscription_catalogue.py`
- `user-subscription-plans.json`
- `frontend/src/pages/owner/SharedLinks.jsx` (existing placeholder completed)
- `frontend/src/pages/user/Subscription.jsx`
- `frontend/src/components/layout/OwnerLayout.jsx`
- `frontend/src/routes/AppRoutes.jsx`
- `frontend/src/services/shareService.js`
- `frontend/tests/share-management.test.mjs` (new)
- `frontend/tests/user-subscription.test.mjs`
- `docs/DAY3_SHARE_LINKS_AND_CREDIT_AUDIT.md` (new)

## Endpoints

- New `GET /owner/share-links?project_id=ID&before=ID`: Owner-scoped management/history.
- New `PATCH /owner/projects/{project_id}/share-links/{link_id}` with strict `{ "is_active": true|false }`: reactivate or deactivate existing link.
- Reused `PUT /owner/projects/{project_id}/share-links/{link_id}/phases/{phase_id}` and existing project create/list/deactivate endpoints. No duplicate publication API.

## Manual checks still needed

Browser/mobile/theme verification was not performed. Check project filtering and Load more; cached versus unavailable URL display; activation/deactivation confirmation; expired/quota-blocked actions; unpublished-phase picker updates; repeated publication; and customer refresh showing only explicitly authorized phases. Use isolated/mocked data for generation checks. MySQL concurrency was not exercised against the real database.

## Verification results

- Focused subscription, credit/refund, free-history and management regression run: **50 passed**. After adding unassigned legacy-link coverage, the final management suite: **6 passed**.
- Sharing/phase/catalogue compatibility run: **29 passed**.
- Frontend management and user-subscription scripts passed; customer-project tests **7 passed**, Owner AI tests **14 passed**. Production build passed.
- Initial failures (query guard rejection and an accidental catalogue edit affecting Pro) were corrected and rerun successfully. Pro is LKR 990 / 100 credits; Owner configuration remains exactly two images.
- Non-blocking dependency deprecations, existing SSR controlled-field warnings and the Vite >500 kB chunk advisory remain.
- All backend writes were confined to disposable SQLite fixtures with production connections guarded. No real MySQL writes, migrations, live AI calls, payment transactions or Git commands were performed.
