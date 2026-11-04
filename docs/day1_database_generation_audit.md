# Day 1 database and free-generation foundation audit

This audit used repository inspection and SELECT-only `information_schema`
queries against `frameora_db` and `frameora_migration_test`. No application row
contents were read or changed, and no DDL or migration was run.

## Database baseline and model comparison

| Evidence | Finding |
|---|---|
| `database/schema.sql` | Empty (0 bytes); it cannot serve as the 16-table baseline. |
| Live database table sets | Both databases report exactly the expected 16 base-table names, all InnoDB and `utf8mb4_0900_ai_ci`, on MySQL 8.0.46. No unexpected or missing tables were found. |
| Database metadata totals | Each has 127 columns, 26 foreign keys, and 10 checks. `frameora_db` reports 74 index-column entries; `frameora_migration_test` reports 78. |
| Index discrepancy | Read-only `information_schema.STATISTICS` and `SHOW CREATE TABLE` checks confirm four extra indexes in `frameora_migration_test`: `CreditTransaction.fk_credit_user`, `CustomerProject.fk_project_owner`, `Subscription.fk_sub_user`, and `ShareLink.fk_share_generation`. All four are single-column indexes whose columns are covered as leftmost prefixes by other composite indexes in both databases. The corresponding FKs exist in both schemas. Do not add, remove, or rename any of these indexes based on this finding. |
| `backend/app/models/` | Seven of the 16 baseline tables have non-empty mappings: `User`, `UserProfile`, `PhotographyPlan`, `AIGeneration`, `SubscriptionPlan`, `Subscription`, and `CreditTransaction`. The new proposed `FreeGenerationAllowance` mapping is eighth, but that table is absent from both databases. |
| Missing mappings | Eight existing model files are empty (`AIResult`, `CustomerProject`, `Equipment`, `MediaAsset`, `Notification`, `Payment`, `ResultRating`, `ShareLink`); no `PlanEquipment` model file is present. |
| Column comparison | Existing mapped columns match database column names/nullability. Type differences are dialect-equivalent `bool`/`tinyint(1)` and `numeric`/`decimal`. `User.auth_version` exists in the ORM mapping but is absent from both databases; the `AUTH_VERSION_ENABLED` feature gate is false. |
| Baseline assertion | `backend/migrations/003_owner_subscriptions.sql` asserts a 16-table set including `PlanEquipment`, verifies important table signatures, and adds owner subscription/credit behavior. It is an executable migration and was read only. |
| Migration history | 001 adds Google identity fields to `User`; 002 adds `auth_version`; 003 introduces owner subscription/credit structures; 004 proposes `UserProfile.studio_photo`. Migration comments require explicit operational approval and manual execution. |
| Connection safety | The SQLAlchemy engine connects lazily; its health probe is an explicit `SELECT 1`. This audit did not invoke it. Application startup does not create tables. |

The checked-in baseline DDL is absent. Aggregate table row counts could not be
obtained with the available database account; no application records were
returned. The index difference is consistent with the test database retaining
standalone FK-support indexes that are redundant given the composite left-prefix
indexes; available metadata cannot establish why one schema retained them and
the other did not. Migration 003's preflight expects those standalone indexes,
so its preflight signature does not match the current `frameora_db` index set.
Do not rerun or alter migration 003 to reconcile this. Before any production
migration, obtain approved row-count access and compare full table
definitions/index/FK/check signatures on both targets. Do not infer or
regenerate baseline DDL from partial ORM metadata.

## Existing feature compatibility

### AI generation

`AIGeneration` already represents one generation request and links it to a user
and a photography plan. However, the checked-in AI router, request schema, service,
provider, results model, frontend generator page/service, and AI test file are
empty. The existing generation table has no free-versus-subscription marker and
its status is an unconstrained string. Counting all old successful rows would
incorrectly consume a free allowance for paid or legacy requests.

The proposal adds a per-account `FreeGenerationAllowance` row. It is separate
from `AIGeneration`, so historical requests are not misclassified. Its unique
`user_id` primary key stores an in-progress reservation or a permanent consumed
state linked to one completed generation. Failed attempts return to `available`.
Reservation helpers lock the account row before the allowance row, serializing
concurrent requests across workers when run on the intended MySQL/InnoDB schema.
The allowance is keyed to the persistent `User.id`, not a JWT, browser session,
or device, so logout/login and device changes do not reset it.
The eventual generator must mark a request `completed` only after its complete
4–5-image result set is persisted and ready to preview.

The API currently exposes only an authenticated, read-only eligibility endpoint.
The reservation lifecycle is internal foundation code: no image generation
endpoint, image provider, persistence of generated image files, or external AI
call is enabled by this Day 1 change. The proposal migration has not been run,
so eligibility safely returns 503 until the table exists. A `reserved` claim left
by process termination needs explicit reconciliation; automatic expiry is
deferred until the future generation timeout/cancellation contract is defined.
The internal reconciliation helper consumes a linked successful terminal
generation, releases a linked failed generation, and leaves pending work reserved.
Recovery must first establish that an external provider job is no longer running;
age alone must never release a reservation. The helper is not exposed as an API.

### Subscriptions

The existing subscription catalogue and activation routes require the `owner`
role and use only owner catalogue entries. `SubscriptionPlan.user_role` can
represent other roles, but there is no Normal User subscription-selection or
activation flow in the checked-in frontend/backend. Therefore this work does
not infer that an owner plan is eligible for a Normal User, activate a
subscription, charge a user, or bypass a future generation gate. A later
subscription entitlement service must define and verify active Normal User
plans before joining it to generation authorization.

### Studio Owner upgrade

Studio onboarding and subscription activation operate on an existing owner.
The onboarding service checks `user.role == "owner"`; the frontend owner route
is also protected by the owner role. Studio details are stored in the separate
one-to-one `UserProfile`, and owner subscription activation advances the
onboarding state. There is no existing Normal User-to-Owner upgrade endpoint or
pending-role workflow. This Day 1 work does not change roles or user records.
Future upgrade work must preserve the same `User` ID and data and must not set
the role to `owner` before the complete approved onboarding transition.

### Frontend preparation

The empty AI generation page remains unchanged. A small service method reads
the new eligibility endpoint for future UI integration. No subscription,
payment, role-upgrade, or image-generation UI is added.

## Migration proposal

`backend/migrations/005_free_generation_allowance.sql` is proposal-only and is
never executed by application startup or tests. It adds one InnoDB table with:

- `user_id` as the primary key and FK to `User`, enforcing one allowance per account.
- A constrained `available` / `reserved` / `consumed` state.
- A random reservation token and reservation timestamp for request ownership.
- A state/reservation-time index to support bounded stale-request discovery.
- A unique FK to the completed `AIGeneration` row on successful consumption.
- No backfill, account update, subscription change, or change to the existing
  Photography Plan, AI generation, or authentication schema.
- No automatic rollback: after rollout, dropping the table would erase permanent
  consumption records. Disable new reservations and reconcile/preserve the ledger
  before considering a separately approved rollback.

Before any later approval, verify the live `User` and `AIGeneration` definitions,
FK targets, MySQL version, CHECK enforcement, storage engine, naming conflicts,
backup/restore, and migration ordering in an isolated MySQL rehearsal. Do not
execute this proposal against either protected database as part of this sprint.

## Review changes before Day 2

- Added `m005_ix_free_generation_state_reserved` so a future recovery worker can
  find old reservations without scanning every allowance row.
- A fresh metadata comparison confirms both existing schemas have 16 InnoDB
  tables, expected parent key types (`User.id` and `AIGeneration.id` are signed
  `INT`), and the required parent primary keys. Migration 005 uses only these
  parent keys and does not target subscription tables.
- The four index differences are redundant, left-prefix FK-support indexes in
  the migration-test schema; their foreign keys are present in both databases.
  No existing index was changed. The actual migration history behind the
  difference remains unknown.
- The runtime schema gate now checks the unique generation key, both foreign
  keys, required CHECK constraint, and InnoDB engine before using the allowance.
- Reservation, completion, release, and reconciliation lock the User row before
  the allowance row. The focused tests inspect generated MySQL `FOR UPDATE` SQL
  and verify that lock order.
- Completion is idempotent for a reservation already consumed; retrying a
  successful finalization does not create another allowance consumption.
- Added an internal terminal-state reconciler: linked completed requests consume
  the allowance, linked failed requests release it, and requests still marked
  `reserved` remain reserved. A future worker must confirm a provider task is
  stopped before marking it failed; age alone is not safe grounds to release it.

## Verification limitations

SQLite tests below validate the application contract only. SQLite does not prove
MySQL `SELECT ... FOR UPDATE`, cross-worker serialization, CHECK/FK enforcement,
or migration behavior. No separate disposable MySQL instance was provided, so a
MySQL DDL/concurrency rehearsal was not performed. The four-index difference
between the two existing databases also remains unresolved. Migration 005 is
ready for an isolated rehearsal, not production execution or approval; a
separately approved disposable MySQL rehearsal and baseline reconciliation are
still required before enabling generation.
