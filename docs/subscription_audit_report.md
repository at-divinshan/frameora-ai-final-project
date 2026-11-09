# Subscription and Credit Management Audit

**Audit date:** 2026-11-05  
**Scope:** Read-only review of the Frameora AI project for the requested subscription and credit rules. This report was created as the requested deliverable; no source code or database objects/data were changed.

## Executive summary

The project already contains a substantial **Studio Owner subscription-selection and entitlement foundation**: plan catalogue definitions, Basic and one-time Trial activation, monthly/trial credit balance display, idempotency, lazy expiry fallback, owner onboarding, and a frontend plan-selection page. Paid Pro checkout is deliberately unavailable.

This is **not yet a complete subscription/credit-management system**. There is no credit-spend/debit path for owner AI usage, no project/share-link entitlement enforcement, and no implementation that preserves the oldest projects/links while restricting the rest. The project/share-link backend model, route, and service files are empty. Normal Users have a separate, implemented one-successful-generation allowance.

The current MySQL schema could not be inspected from this environment. Therefore, whether the live `frameora_db` has 17 tables, whether migrations 003/005 have run, and which columns are actually present remain **unverified**. The report distinguishes migration/model evidence from live-database facts below.

## Existing files and implementation status

| Area | Files | Status and verified findings |
|---|---|---|
| Owner plan catalogue | `backend/app/models/subscription_plan.py`, `backend/app/schemas/subscription.py`, `backend/app/services/subscription_service.py` | **Implemented in code.** Defines Free Basic (10 credits/month, 2 projects, 3 share links), Free Trial (100 total credits, 14 days, 10 projects, 20 links), and Paid Pro (LKR 1,500/month). The code/migration additionally specify Pro as 500 monthly credits, 50 projects, and 100 links; those Pro allowances were not included in the confirmed rules in the audit request and should be product-confirmed before activation. |
| Subscription records and credit ledger | `backend/app/models/subscription.py`, `backend/app/models/credit_transaction.py`, `backend/app/services/credit_service.py` | **Partially implemented.** Subscription history, owner uniqueness fields, current-period balance calculation, monthly anniversary periods, trial-total period, and idempotent grant insertion are represented. `credit_service.balance()` reads and grants; no credit-spend/debit operation or AI-generation linkage to owner credits was found. |
| Owner subscription API | `backend/app/routers/subscriptions.py`, `backend/app/services/subscription_service.py` | **Implemented in code, schema-gated.** Owner-only GETs expose catalogue/status. POST activation exists for Basic and Trial; no Pro activation endpoint is exposed. The service validates expected catalogue values, uses the account row lock and subscription uniqueness constraints, checks trial history, and uses an idempotency key. It fails closed if required schema is absent. |
| Trial start and expiry | `backend/app/services/subscription_service.py`, `frontend/src/pages/owner/Subscription.jsx` | **Partially implemented.** Trial starts only through the explicit activation POST used by the “Start Free Trial” button; history prevents a second trial. Expiry is recognized by timestamp. A GET computes a virtual Basic fallback without persisting the expired/Basic records; a later activation POST can persist the transition. A durable scheduled expiry transition is not present. |
| Studio Owner onboarding | `backend/app/services/onboarding_service.py`, `backend/app/routers/owner.py`, `backend/app/schemas/owner.py`, `frontend/src/routes/OwnerOnboardingRoute.jsx`, `frontend/src/utils/onboarding.js` | **Implemented.** Studio details move onboarding from `pending_studio` to `pending_plan`; successful subscription activation completes onboarding. Owner role is checked on the API and frontend route tree. |
| Normal User free generation | `backend/app/models/free_generation_allowance.py`, `backend/app/services/free_generation_service.py`, `backend/app/routers/ai.py`, `backend/app/services/ai_service.py` | **Implemented separately from owner credits.** A Normal User gets one account-scoped reservation. A failed generation releases it; a completed generation consumes it. The generation endpoint creates four images per generation request, but the allowance is per successful request, not per image. The service rejects non-Normal-User roles and fails closed if the allowance schema is absent. No Normal User subscription pricing was found or introduced. |
| Owner frontend | `frontend/src/pages/owner/Subscription.jsx`, `frontend/src/pages/owner/Dashboard.jsx`, `frontend/src/services/ownerService.js`, `frontend/src/utils/subscription.js` | **Partially implemented.** Plan cards display credits/limits, trial availability, and disabled Pro payment/activation; activation calls the existing owner API. Dashboard displays plan/credit information, but project and link counts are unavailable and their product surfaces are marked unavailable/coming soon. |
| Project and share-link management | `backend/app/models/customer_project.py`, `backend/app/models/share_link.py`, `backend/app/routers/projects.py`, `backend/app/routers/sharing.py`, `backend/app/services/project_service.py`, `backend/app/services/share_service.py` | **Missing in application code.** All six listed files are zero bytes. No project-limit or share-link-limit enforcement was found. The owner project/share pages are not mounted as active routes in `frontend/src/routes/AppRoutes.jsx`; the dashboard controls indicate these features are unavailable. |
| Payment | `backend/app/models/payment.py`, `backend/app/routers/payments.py` | **Missing in application code.** Both files are zero bytes. Pro payment checkout is appropriately disabled in the current subscription UI/API. |
| DDL and checked-in schema | `backend/migrations/003_owner_subscriptions.sql`, `backend/migrations/005_free_generation_allowance.sql`, `database/schema.sql` | **Migration artifacts exist; live application is unverified.** Migration 003 alters existing plan/subscription/ledger/project/link tables and does not create a table. Migration 005 is explicitly marked proposal-only and creates `FreeGenerationAllowance`. The checked-in `database/schema.sql` is empty (0 bytes), so it cannot establish the live schema. |

### Expiry and downgrade detail

When an active time-bounded subscription expires, `subscription_service.snapshot()` calculates a Basic fallback anchored at the expiry time. For a read-only GET that fallback is virtual (not inserted, and the old row is not marked expired). When an activation POST is processed, the service can persist the expired state and Basic record. The project has no expiry worker/scheduler. This is a partial match for “expiry downgrades to Free Basic,” not a durable automatic transition.

## Database findings

### Live database verification

**Not verified.** A read-only connection attempt to `frameora_db` was made, but it did not connect. Python SQLAlchemy is not installed in the current environment, and the MySQL client returned a non-zero connection result. No credentials or secrets were printed. No SQL writes, migrations, or database mutations were attempted.

Consequently, these are **not claimed as live-database facts**:

- Actual database engine/version, exact table count, and whether the current schema has 17 tables.
- Whether `SubscriptionPlan`, `Subscription`, `CreditTransaction`, `FreeGenerationAllowance`, `CustomerProject`, and `ShareLink` currently exist.
- Their current columns, constraints, indexes, data, and migration state.
- Whether the current plan rows match the expected catalogue.

### Code/migration-only schema evidence

- The SQLAlchemy mappings expect `SubscriptionPlan.code`; `Subscription.plan_kind`, activation key and generated owner slots; and subscription/period/idempotency fields in `CreditTransaction`.
- Migration 003 adds those fields and constraints, adds `CustomerProject.deleted_at` plus an ordering index, and adds share-link indexes. It alters five existing tables and creates no table.
- Migration 005 creates a separate per-Normal-User `FreeGenerationAllowance` table. Its SQL comments explicitly say “PROPOSAL ONLY”; its test checks the SQL text statically and does not execute it.
- The migration review document reports a previous, read-only MySQL audit from 2026-10-29 with a 16-table baseline and says migration 003 had not been executed at that time. This is historical documentation, not evidence of the current database state.
- Migration 003 has strict preflight expectations, including a particular 16-table baseline and empty business tables. It is not safe to infer that it can be applied to the current database, or replayed, without fresh DBA verification.

## Business-rule coverage

| Agreed rule | Current status |
|---|---|
| Free Basic: 10 credits/month; 2 editable projects; 3 active links | Plan values and UI display are present. Project/link enforcement is missing. Monthly balance is calculated, but there is no credit debit path. |
| Free Trial: 100 total credits; 14 days; 10 projects; 20 links | Catalogue and explicit one-time activation are present. Credit balance period is trial-bounded. Project/link enforcement is missing. |
| Trial starts only on owner click and is available once | **Implemented in code** through explicit POST activation, frontend button, subscription history, and uniqueness constraints. Live schema enforcement is unverified. |
| Paid Pro: LKR 1,500/month; checkout disabled | Price is shown and activation is disabled/not routed. Code also defines 500 credits/month and limits of 50 projects/100 links; those values need confirmation against the agreed product definition. |
| Expiry downgrades to Basic | **Partial:** GET reports a Basic fallback; persistence is lazy and occurs on a later activation POST, not via a scheduled transition. |
| Do not delete projects/images; preserve oldest two editable projects and oldest three active links; excess become read-only/disabled | No project/share application code or enforcement was found. Migration 003 itself contains no project/link deletion DML, but no runtime preservation/restriction behavior exists to verify. |
| Monthly credits do not carry over | **Partially represented:** balance queries are period-scoped and the UI says no carryover. No owner-credit spending implementation exists to verify deductions/rollover end to end. |
| Normal User retains one successful free generation | **Implemented separately** through reservation/completion state. This is not a subscription plan or pricing system. |

## Migration assessment

1. **Are existing tables sufficient?** The *designed table set* is sufficient for subscription records, plan values, and credit history, with existing project/share tables used for their respective limits. The Normal User allowance has its own proposed table in migration 005. Sufficiency of the *live* tables cannot be confirmed.
2. **Are columns missing?** In the pre-migration definitions described by migration 003, yes: the code requires the fields listed in “Code/migration-only schema evidence.” Whether those columns are missing from the current database is unknown.
3. **Is a new migration required?** Cannot determine without live schema inspection. The repository already contains migration 003 for subscription/ledger/limits metadata and migration 005 for the Normal User allowance. If both are already correctly applied, this audit identifies no additional table requirement. If not, the existing reviewed migrations may be pending; do not create or run another migration on assumption alone.
4. **Can the existing 17-table schema be preserved?** **Conditionally.** Migration 003 creates no table. Migration 005 creates one table. If the current 17-table schema already contains the allowance table and the required 003 changes, no additional table is indicated by the reviewed design. If the allowance table is absent, applying 005 increases the count by one. The live count and migration state are unverified, so preservation cannot be guaranteed from this audit.
5. **Safest implementation order:** (1) Have a DBA run approved read-only metadata/plan checks and confirm the exact database and migration state. (2) Back up and rehearse the precise migration sequence on a disposable MySQL copy. Respect migration 003’s strict baseline and table-count checks; do not replay it or apply it after incompatible schema changes. (3) Only after schema approval, implement/test transactional credit debits, idempotency, project/link entitlement enforcement, and persistent expiry downgrade. (4) Add MySQL concurrency/authorization coverage. (5) Complete frontend usage/status surfaces against stable APIs. Keep Pro checkout disabled until payment and entitlement behavior are approved and tested.

## Missing work classification

### A. Safe tasks for GitHub Copilot

- Refine subscription plan cards and explanatory text using only confirmed plan values.
- Improve loading/error/retry/accessibility states on the existing subscription page.
- Show available owner subscription and usage data through existing APIs; add frontend forms or API integration once the backend contract is approved.
- Complete frontend subscription tests and disabled/coming-soon states without enabling payment or inventing Normal User pricing.
- Add project/share usage displays only after an authorized backend API supplies the counts.

### B. Tasks for Codex

- Database migration review/application, based on a fresh read-only live-schema audit and approved MySQL rehearsal.
- Owner credit spending/debit/refund transaction logic, request idempotency, ledger balance validation, and monthly grant behavior.
- Trial/paid expiry persistence and downgrade semantics.
- Project and share-link enforcement, including stable oldest-first preservation and read-only/disabled behavior without deleting data or images.
- Enforcement on every relevant backend route; owner scoping, authentication/authorization, row-lock ordering, concurrency controls, and security-sensitive tests.
- MySQL-specific migration/concurrency validation and ensuring all code paths use the same entitlements. Keep paid checkout disabled unless separately approved.

## Existing tests and validation limits

Relevant tests present:

- `backend/tests/test_owner_subscriptions.py`: disposable SQLite tests for catalogue/Pro unavailability, Basic activation, idempotency, one-time Trial, expiry fallback, monthly anniversaries, and schema fail-closed behavior.
- `backend/tests/test_owner_onboarding.py`: onboarding state, role checks, validation, and locking-related tests.
- `backend/tests/test_free_generation.py`: Normal User allowance reservation/completion, failed attempts, interrupted work, role/account isolation, and fail-closed schema behavior.
- `backend/tests/test_free_generation_migration.py` and `backend/tests/test_migration_safety.py`: static/SQLite checks of migration text; they explicitly do not execute migrations or prove live MySQL DDL behavior.
- `backend/tests/test_ai.py`: AI generation flow tests include allowance lifecycle cases.
- `frontend/tests/account.test.mjs`: subscription-card rendering, trial state, activation requests, onboarding, and dashboard refresh cases.

No tests were run for this audit. Backend execution was unavailable because SQLAlchemy is not installed in the current Python environment. The frontend package manifest has no test script. Tests that would call the real image provider were not run; no Pollinations API call was made.

## Risks and dependencies

- Live migration/schema state is unknown; historical migration review evidence is not a substitute for fresh verification.
- Migration 003 is deliberately fail-closed and assumes a narrowly defined baseline. If the business tables are non-empty or the schema has drifted, it may stop and require a separately reviewed backfill plan.
- SQLite tests and MySQL dialect compilation do not demonstrate actual MySQL locking or concurrent-request behavior.
- Credit balance/grant code without a spend path does not yet provide usable owner credit management.
- Missing project/share-link application code prevents enforcement of plan limits and downgrade retention requirements.
- Pro allowance values beyond its monthly price are present in code but not specified in the confirmed rule set.
- The worktree contained unrelated uncommitted changes before this report was created; they were not modified by the audit.
