# Step 33 — core owner subscription migration review

**Prepared for review only. No SQL from this migration or this document has been executed.**

Files in scope:
- `backend/migrations/003_owner_subscriptions.sql`
- `docs/003_owner_subscriptions_review.md`

This step does not implement backend behavior, activate a plan, create a profile,
seed accounts, change Payment, or enable password management. Keep
`AUTH_VERSION_ENABLED=false` and `PASSWORD_MANAGEMENT_ENABLED=false`.
Never include `002_user_auth_version.sql` in this rollout.

## Evidence and freshness

The baseline is the actual MySQL `SHOW CREATE TABLE`, `information_schema` results,
plan catalogue and aggregate counts inspected in the immediately preceding
read-only design audit on 2026-10-29. This preparation step deliberately did not
execute SQL again because its instructions prohibit SQL execution.

Verified in that audit:
- MySQL 8.0.46; InnoDB; utf8mb4_0900_ai_ci.
- 16 tables, eight users, three owners without UserProfile records.
- Subscription, CreditTransaction, CustomerProject and ShareLink were empty.
- Owner plans: 1 / Free Basic / LKR 0 / 10 credits / 2 projects / 3 links;
  2 / Free Trial / LKR 0 / 100 credits / 10 projects / 20 links / 14 days;
  3 / Paid Pro / LKR 1500 / 500 credits / 50 projects / 100 links.
- Both Day 4 activation flags were false.

The executable preflight must revalidate this baseline during any future approved
execution. A changed baseline is a STOP condition, not permission to delete data,
relax checks, seed plans, or substitute assumed values.

## Scope and expected changes

| Table | Proposed changes | Preserved |
|---|---|---|
| SubscriptionPlan | Nullable ASCII/binary `code`, allowed-code CHECK, unique `(user_role, code)`; fill exactly IDs 1/2/3 with basic/trial/pro after guarded identity checks | All existing catalogue fields, prices and limits |
| Subscription | Nullable end_date for indefinite Basic; immutable service-managed plan_kind; activation digest; generated trial/active/pending owner slots; uniqueness, date/status checks; owner/id candidate key; lookup index | Existing columns and FKs |
| CreditTransaction | Subscription and period attribution, operation/request digests, generated grant-period slot, sign/period checks, uniqueness and owner-matching composite FK | Existing user/generation FKs and ledger fields |
| CustomerProject | Nullable deleted_at; `(studio_owner_id, deleted_at, created_at, id)` index | All projects; no deletion |
| ShareLink | Two nonunique generation/active indexes for expiry filtering and deterministic ordering | Existing token uniqueness, flags, expiry and FKs |

No ALTER targets User, UserProfile, Payment, AIGeneration or any other table. No
new table is created. There is no auth_version statement. The only DML is a
three-row plan-code backfill; no subscription or credit grant is created.

The nullable plan code permits unrelated future plan families, but the service
must require a recognized non-null owner code. Do not interpret NULL as Basic.
The current three owner codes are verified after migration.

## Preflight and fail-fast behavior

A short-lived procedure, `frameora_m003_owner_subscriptions`, contains **all**
preflight checks and table alterations. SIGNAL aborts the procedure body before
later ALTERs can execute. Procedure creation is itself DDL, but creates no table
and changes no existing table or row. The helper uses SQL SECURITY INVOKER.

Preflight requires:
1. A selected database, exact reviewed MySQL 8.0.46 version, strict SQL mode,
   NO_ZERO_DATE/NO_ZERO_IN_DATE, autocommit=1, foreign_key_checks=1, unique_checks=1
   and group_concat_max_len>=1024.
2. Exclusive acquisition of a named migration advisory lock.
3. The exact 16-table name set and the expected relevant InnoDB/collation values.
4. Exact ordered column names, types, nullability, defaults and EXTRA metadata for
   User, UserProfile, SubscriptionPlan, Subscription, CreditTransaction,
   CustomerProject, ShareLink and AIGeneration. This also rejects an already or
   partially applied migration and an unexpected auth_version column.
5. Exact existing index signatures for the seven core/account tables, including
   uniqueness, column order, BTREE type, full-column coverage and visibility.
6. Exact FK targets for those tables and AIGeneration; every FK in the selected
   database must reference the same database, including prerequisite ownership
   tables. No unexpected cascading actions are allowed.
7. No unreviewed triggers on affected tables, no existing CHECKs on affected
   tables, and no schema-level constraint name starting `m003_`.
8. Eight users; exactly three owners and one Admin; supported roles only. Existing
   profiles are allowed and must reference an existing User. The earlier zero-profile
   assumption was removed in Step 42; exact schema/FK/unique guards remain intact.
   Counts do not replace a backup of actual data.
9. Empty Subscription, CreditTransaction, CustomerProject and ShareLink.
10. Exactly three catalogue rows, matching ID, exact case-sensitive name/role,
    price, currency, credits, limits, trial days and active status.

The exact definition comparisons are intentionally conservative. Even a harmless
new index causes a stop and review. Signature strings are below the required
1024-byte GROUP_CONCAT limit; no session configuration is changed by this file.

**Writer quiescence is mandatory.** Stop API processes, workers, scheduled tasks
and administrative writes for the entire migration. GET_LOCK coordinates only
cooperating migration clients. It does not stop application inserts or prevent
another client changing data between preflight and a DDL implicit commit.

The selected database name is not hard-coded so an isolated rehearsal is possible.
The operator must confirm the intended target and identity using separate approved
read-only checks. Matching schema/counts do not prove database identity.

## Effective privilege preflight (revised)

Before consulting TRIGGERS or other filtered metadata, the procedure builds a
principal set from CURRENT_USER() and information_schema.ENABLED_ROLES. Only those
principals may supply global, exact-database or whole-table grants. Inactive roles
are excluded. ROLE_TABLE_GRANTS is also filtered against enabled role identities;
a role merely available to an enabled role is not sufficient evidence.

Required privileges are checked for every affected table: ALTER, CREATE, INSERT
and TRIGGER; UPDATE for the catalogue; REFERENCES for existing/new FK targets;
SELECT on all 16 tables for complete metadata visibility; and database/global
CREATE ROUTINE, ALTER ROUTINE and EXECUTE. CREATE/INSERT are MySQL ALTER TABLE
requirements even though the migration creates no application table or records.
TRIGGER is necessary to prove an empty TRIGGERS result means no triggers.

This is deliberately conservative: only visible grant evidence qualifies.
Wildcard schema grants, column-only grants and routine-only grants are not used
as substitutes for the required exact-scope grants. Invisible role grant metadata
causes a stop, not guessed access. partial_revokes=ON is rejected because positive
global grant rows alone cannot prove unrestricted effective privileges.
No grants, role activation, grant-table reads or configuration changes are made.

Before future execution, inspect SHOW GRANTS for the invoking account with its
actual enabled roles and confirm metadata visibility. Do not enable all available
roles automatically or grant application users migration privileges. If role
metadata is not visible, obtain a separately reviewed migration-account setup.
Routine creation itself precedes the in-procedure guard, so lack of CREATE ROUTINE
can fail even earlier. Missing DROP/ALTER ROUTINE capability must be identified
before starting, not discovered after the committed backfill.

Required isolated tests include direct grants; enabled-role grants; nested enabled
roles; inactive-role rejection; missing TRIGGER/CREATE/INSERT; partial revokes;
role metadata visibility; and cross-database FK rejection (including AIGeneration).
These SQL privilege/rehearsal cases have NOT been executed in this implementation.

References: MySQL 8.0 manuals for privileges-provided, information-schema-enabled-
roles-table, information-schema-role-table-grants-table and information-schema-
triggers-table on dev.mysql.com. Grant and metadata checks must run in the same
session/security context as the actual migration; do not change roles mid-run.

## Constraints and compatibility rationale

- Every new FK component is signed INT, matching the inspected existing keys.
- The composite CreditTransaction `(user_id, subscription_id)` FK references the
  new UNIQUE Subscription `(user_id, id)` key. A ledger entry cannot point to a
  subscription owned by a different account.
- MySQL unique indexes permit multiple NULLs. Generated slots are populated only
  for trial history, active status or pending-payment status respectively.
- The trial slot applies to **every** trial status: expiry/cancellation does not
  restore eligibility. The service must never delete trial history or change its
  user/kind. No cascading deletion is added.
- Basic permits active/superseded/cancelled with NULL end_date. Trial permits
  active/expired/superseded/cancelled with end=start+14 days. Pro permits those
  lifecycle states plus pending_payment with a strictly later end date.
  Trial/Basic can never be pending_payment.
- The active slot is based on stored status, not current time. Before creating a
  replacement active subscription the service must mark the previous row
  expired/superseded within the same owner-locked transaction.
- Activation and operation keys must contain exactly 32 digest bytes. Column
  capacities leave room for a later reviewed change but CHECKs currently enforce
  SHA-256-sized keys. Store binary digests, not 64-character hexadecimal text.
  request_hash is the SHA-256 digest of a canonical validated request.
- Credit signs are grant/refund > 0 and spend < 0; zero/unknown entries are rejected.
  The unique grant slot permits one grant per owner/subscription/period start.
  Expiry and canonical period calculations remain service responsibilities.
- Existing generation ownership is not enforced by the new composite subscription
  FK; the service must separately validate any generation_id belongs to the user.
- The ShareLink expiry index aids generation-scoped eligibility scans. The second
  index aids created_at/id ordering without placing an expiry range first. Neither
  guarantees a sort-free owner-wide query across several generations; EXPLAIN in
  isolated MySQL must validate access plans. Existing AIGeneration.user_id indexing
  provides the ownership join; no duplicate owner column is added.
- All new CHECK/unique/FK/index names use `m003_`, are below MySQL's 64-character
  identifier limit, and are checked against the baseline.

This SQL has received static review only. No MySQL parser/DDL rehearsal was run in
Step 33. Successful isolated rehearsal on the exact server version is a release
gate, especially for stored generated columns and CHECK/FK interactions.

## Business behavior that SQL alone does NOT implement

Future services must lock User first, then consistently lock subscription/ledger
rows, compute server UTC time once for the decision, and commit related writes
atomically. Handle deadlocks with bounded retries using the same operation keys.

- Studio name/phone/address/city required; description optional; no approval.
- Profile state pending_studio -> pending_plan -> completed is server-managed.
- Explicit first trial only, including for an existing Basic owner: one subscription
  and one +100 grant in the same transaction, never login-triggered.
- Trial periods exactly match their subscription start/end. Basic/Pro periods are
  computed from original monthly anniversary anchors, with month-end clamping
  without cumulative date drift. No carryover or grant of missed historical periods.
- Current spendable balance excludes expired periods and superseded entitlements.
  Refunds reference the original debit via a server-derived unique operation key,
  cannot exceed it and cannot resurrect credits into a later period.
- Repeated Basic selection returns the current Basic subscription; no new anchor
  or grant. A new Basic episode after trial/Pro expiry is anchored to that exact
  expiry, not the next request. Derive a stable fallback activation key from the
  expiring subscription identity to prevent duplicate fallback episodes.
- Unique operation keys prevent duplicate matching operations, but not two
  unrelated spends exceeding the balance. Owner-row serialization is still needed.
- Trial expiry resolves immediately to Basic even if stored statuses are stale.
- Non-deleted projects ordered by created_at ASC, id ASC: oldest two editable on
  Basic; excess remain readable. Deletion frees a slot; restoration checks limits.
- Eligible active, unexpired links use the same ordering: oldest three accessible
  on Basic. Deny excess links immediately in public access checks and persist
  deactivation during reconciliation; do not delete them or silently reactivate.
- Generation/project ownership must match for links. No widening of public profile
  responses or privacy access is authorized by this migration.
- Paid Pro remains disabled. A code or a pending-payment slot is not payment proof.
  No generic endpoint may activate Pro; verified payment integration requires a
  separately reviewed implementation and migration.

## Backup, rehearsal and later approved execution

1. Obtain explicit migration execution approval. This preparation is not approval.
2. Back up schema and data privately; verify restoration into a separate MySQL
   instance/database. Keep credentials and backup contents out of logs/chat/Git.
3. Prepare a separate MySQL 8.0.46 rehearsal database with the inspected 16-table
   schema and disposable fixtures matching the baseline counts/catalogue. Never
   use the existing eight real accounts as mutation-test fixtures.
4. Confirm the migration role has needed SELECT, ALTER, CREATE, INSERT, UPDATE,
   REFERENCES, TRIGGER, CREATE ROUTINE, EXECUTE and ALTER ROUTINE privileges; do not add application
   privileges or disable FK/unique checks. Creating/dropping the helper requires
   routine privileges; lack of privileges is a blocker, not permission to weaken
   guards.
5. Rehearse preflight failures: nonempty business table, altered plan, extra column,
   unexpected index, wrong counts/version, partial migration. Confirm no affected
   table alteration occurs on these failures (helper routine may remain).
6. Rehearse success, postchecks, and interruption between ALTERs. Test trial-slot,
   active-slot, pending-slot, cross-owner FK, credit-key/grant and invalid-date/sign
   rejection using disposable accounts only. Include concurrent transactions.
7. Quiesce every development-database writer; confirm target and fresh backup.
   Confirm both Day 4 flags are false outside SQL without exposing secrets.
8. Run **only** 003 using a fresh mysql batch connection. Never use --force, SOURCE
   from a continuing interactive script, a migration glob, or automatic retries.

Illustrative future command (replace placeholders, approval required; not run):

```bash
mysql --user=MIGRATION_USER --password --database=APPROVED_DATABASE --show-warnings < backend/migrations/003_owner_subscriptions.sql
```

The password option prompts; never put a password in the command. Configure secure
transport through the approved local client setup where applicable.

9. Complete every postcheck before resuming writers or deploying dependent code.
   Generated-column additions may rebuild/lock tables; no INSTANT/LOCK=NONE promise
   is made. The empty-table precondition reduces work but not metadata-lock risk.

## Proposed post-migration verification SQL — NOT EXECUTED

Run in the approved database. These queries expose catalogue/schema/counts only,
not passwords, hashes, Google subjects, tokens or private studio details.

```sql
SELECT VERSION(), DATABASE();
SELECT COUNT(*) AS table_count
FROM information_schema.TABLES
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE';
-- Expected: 16.

SELECT COUNT(*) AS user_count,
       SUM(role='owner') AS owners,
       SUM(role='admin') AS admins
FROM `User`;
-- Expected: 8, 3, 1. No user UPDATE is present in the migration.

SELECT COUNT(*) AS owners_without_profile
FROM `User` u LEFT JOIN `UserProfile` p ON p.user_id=u.id
WHERE u.role='owner' AND p.id IS NULL;
-- Expected: identical to the recorded pre-migration count (0–3), not necessarily 3.
-- Compare all profile fields/timestamps to the protected pre-migration snapshot.

SELECT id,name,user_role,code,price,currency,monthly_credits,
       max_projects,max_share_links,trial_days,is_active
FROM `SubscriptionPlan` ORDER BY id;
-- Exactly the original 3 rows; codes basic/trial/pro only are new values.

SELECT (SELECT COUNT(*) FROM `Subscription`) AS subscriptions,
       (SELECT COUNT(*) FROM `CreditTransaction`) AS credit_entries,
       (SELECT COUNT(*) FROM `CustomerProject`) AS projects,
       (SELECT COUNT(*) FROM `ShareLink`) AS links;
-- Expected: 0,0,0,0; there are no seed/activation inserts.

SHOW CREATE TABLE `SubscriptionPlan`;
SHOW CREATE TABLE `Subscription`;
SHOW CREATE TABLE `CreditTransaction`;
SHOW CREATE TABLE `CustomerProject`;
SHOW CREATE TABLE `ShareLink`;
-- Compare all columns/indexes/generated expressions/FKs/CHECKs to the file.

SELECT TABLE_NAME,CONSTRAINT_NAME,CONSTRAINT_TYPE,ENFORCED
FROM information_schema.TABLE_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA=DATABASE() AND LEFT(CONSTRAINT_NAME,5)='m003_'
ORDER BY TABLE_NAME,CONSTRAINT_NAME;
-- Expected: 7 CHECK constraints, all ENFORCED=YES;
-- 8 UNIQUE constraints and 1 FOREIGN KEY (16 m003_ constraints total).

SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,SEQ_IN_INDEX,COLUMN_NAME,IS_VISIBLE
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA=DATABASE() AND LEFT(INDEX_NAME,5)='m003_'
ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX;
-- Expected: 13 named indexes: 8 unique + 5 nonunique.

SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,GENERATION_EXPRESSION
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE()
  AND TABLE_NAME IN ('Subscription','CreditTransaction')
  AND GENERATION_EXPRESSION<>'';
-- Expected: 4 generated columns (3 subscription slots and 1 grant slot).

SELECT COUNT(*) AS auth_version_columns
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='User' AND COLUMN_NAME='auth_version';
-- Expected: 0. Flags remain false; SQL cannot verify application flags.

SELECT COUNT(*) AS helper_routines
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_NAME='frameora_m003_owner_subscriptions';
-- Expected: 0 after successful batch completion.
```

Compare private backup/schema manifests for User, UserProfile, Payment and all
untargeted tables. Aggregate counts alone cannot prove every existing value is
unchanged. Do not publish credential-bearing records or fingerprints. Preserve
all original account IDs, credentials, roles, profile values and relationships.

## Failure/recovery considerations

This migration is **forward-only, not atomic, not automatically reversible**.
MySQL commits before/after DDL. Each successful ALTER remains after a later failure.
The handler's ROLLBACK affects only uncommitted DML. The plan-code UPDATE is last,
in its own transaction, and must affect exactly three guarded rows.

On any failure:
- Stop; keep writers paused. Do not automatically rerun or remove guards.
- Capture sanitized error/statement details and inspect actual metadata.
- The helper routine may remain after a batch abort. Its existence deliberately
  blocks a naive rerun. Routine cleanup/remediation requires separate approval.
- A partial-schema rerun must fail exact baseline checks. Prepare a reviewed
  forward repair from the actual reached state, or restore the verified backup
  while all writers remain stopped. Neither action is provided/executed here.
- A lost connection after COMMIT may mean success: verify state before any retry.
- Once real subscription/credit history exists, never drop unique trial keys or
  accounting columns as an application rollback. Disable new features and retain
  evidence; deleting trial history could re-enable trials.
- If a client continues after CALL fails, the final DROP can remove the helper,
  but cannot run any later table ALTER: all mutations are inside the procedure.
  Nevertheless --force/continuing clients are prohibited so the exit result remains
  reliable and failures receive review.

## Remaining gates

- Fresh preflight at approved execution time; any baseline difference needs review.
- Successful isolated MySQL syntax/constraint/negative/concurrency rehearsal.
- Validated backup and target identity; routine privileges; a writer-free window.
- Basic/Trial and photo code exists; MySQL rehearsal and live deployment are pending.
- Verified payments remain unimplemented; Paid Pro activation stays disabled.
- No deployment should infer operational subscription support from this migration.


## Step 42 correction — existing profiles permitted

The earlier three-missing-profiles check was a historical baseline assumption, not a
subscription-schema requirement. The owner-reported existing Mafia Studio profile
(pending_plan) is valid and must survive. Only this block in 003 was replaced with
an orphan-reference SELECT check. No profile field, timestamp, owner/account record,
role/FK/unique/index constraint, catalogue guard, DDL or backfill statement was changed.
Zero through three existing owner profiles are permitted; the migration neither creates
nor normalizes them. Unknown application states are not silently repaired by migration.
The original 2026-10-29 evidence above is historical, not a current live inspection.
No current live database queries or migrations were executed for this correction.

Rehearsal fixtures must now include one synthetic owner with complete required studio
fields and pending_plan, plus two owners without profiles, and preserve all original
16 table definitions. Snapshot all profile columns before/after both migrations. Do not
use real studio names, account passwords, email addresses or Google subjects in fixtures.
Run 003 before 004: the exact UserProfile baseline deliberately excludes studio_photo.
See docs/step_42_final_verification.md for release gates and future commands.
