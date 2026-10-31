# Current sprint verification — Step 221

Updated 2026-10-31 (Asia/Colombo). This section supersedes the historical release
status and test totals below. Historical execution evidence is retained, not rewritten
as newly executed verification.

## Current decision

**Ready for a scoped implementation commit with documented verification limitations;
not a claim of complete browser/network or MySQL concurrency sign-off.** No staging,
commit or push has been performed. Include the entire reviewed 50-file manifest below;
committing only tracked modifications would omit required modules and tests.

## Observed browser evidence (Step 220; not rerun in Step 221)

- PASS: authenticated Owner dashboard displayed saved studio details/photo, Free Trial,
  100 credits, expiry and catalogue limits. No personal contact information is reproduced here.
- PASS: authenticated Admin dashboard displayed 4 Normal Users and 3 Studio Owners;
  owner detail showed matching subscription information and photo.
- PASS: Admin navigating to `/owner/dashboard` redirected to `/admin/dashboard`.
- Earlier observed PASS: anonymous Owner/Admin dashboard navigation redirected to Login.
- BLOCKED / manual verification remains: tab-focus request methods/statuses, absence of
  write requests in the browser request log, Owner-to-Admin wrong-role navigation and
  natural subscription-expiry boundary refresh. Visible page contents do not prove these.
- No activation, save, upload or removal was performed during browser verification.

### Remaining manual Network checks

Use existing manually authenticated sessions. Open F12 > Network > Fetch/XHR, enable
Preserve log, and show Method and Status. Do not export HAR, copy headers, or expose tokens.

1. Owner dashboard: switch to another tab and return; expect fresh successful GET
   `/owner/plans` and `/owner/subscription`.
2. Admin: open View Details, switch tabs and return; expect GET `/admin/owners/{id}`
   and its photo GET when present. Current focus refresh applies to owner details,
   not the Admin summary/list counts.
3. In an Owner session, visit `/admin/dashboard`; confirm safe redirection and no Admin data.
4. Observe an existing natural expiry without changing clocks, records or activating plans;
   confirm effective fallback and displayed credits/period refresh.
5. Confirm no POST, PUT, PATCH or DELETE occurred during these read-only checks.

## Final safe checks executed in Step 221

| Check | Result |
|---|---|
| Selected backend regression suite below | **69 passed, 0 failed**, 29.794 seconds |
| `cd frontend && node tests/account.test.mjs` | **42 passed, 0 failed** |
| `cd frontend && npm run build` | **PASS**, Vite 6.4.5, 1708 modules |
| Python AST parsing of pending Python source/tests | **PASS** |
| `git diff --check` | **PASS** |
| Pending-file secret-pattern scan | No obvious credential URLs, private keys, JWT literals or secret assignments found; not an exhaustive security guarantee |
| Tracked/pending artifact exclusion check | No real .env, private uploads, virtual environments, node_modules, dist or Python cache files included |

Backend invocation (from backend; timeout 120 seconds):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests timeout 120s .venv/bin/python - <<'PYTEST'
import unittest
from unittest.mock import patch
import pymysql
with patch.object(pymysql.connections.Connection, 'connect',
                  side_effect=AssertionError('MySQL forbidden')):
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'test_users', 'test_owner_onboarding', 'test_studio_photo',
        'test_owner_subscriptions', 'test_privacy', 'test_profile_pictures',
        'test_admin', 'test_migration_safety'])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(not result.wasSuccessful())
PYTEST
```

Tests use disposable SQLite and temporary files, never MySQL fixtures. The execution
sandbox blocks AnyIO socket wake-ups; the approved test process ran outside that
restriction with PyMySQL connections explicitly blocked. The existing TestClient
HTTPX deprecation warning remains. No package installation or upgrade was performed.
These 69 selected regressions are not a rerun of the historical full 93-test suite.
Frontend checks are SSR, pure-function and mocked-request tests, not browser E2E tests.

## MySQL and remaining scope

- User reports migrations 003/004 applied to original frameora_db. Earlier read-only
  inspection verified frameora_migration_test has 16 tables and migration columns/indexes.
- Earlier read-only evidence: 8 users, 3 plans, 2 profiles, 2 subscriptions and 2 credit
  grants totaling 110; no orphan credit ownership or duplicate grant groups. Relevant
  CHECK/unique/FK constraints were present/enforced and FKs referenced the test database.
- These observations are not proof of write persistence, rejection of invalid inserts,
  transaction rollback or concurrent activation/credit correctness. ORM/schema alignment
  has been inspected statically; no new MySQL runtime check occurred in this step.
- All MySQL writes, fixtures, cleanup, DDL and migrations remain prohibited. Do not rerun
  migration files merely because they are newly tracked in Git. Existing test data is
  nonempty and must not be assumed disposable.
- Project/share counts and enforcement, spending/refunds and payment integration remain
  deferred. No fake metrics or paid activation were introduced. Password/auth_version
  activation remains out of scope and configuration was not changed.

## Reviewed final pending-file manifest

M = modified tracked file; A = existing untracked file to include in the future commit.
Nothing is staged. All entries belong to the accumulated sprint, not just Step 221.
Only this verification document was edited in Step 221. Prior migration review documents
are historical preparation records, not permission to execute SQL.

- `M backend/app/main.py`
- `M backend/app/models/ai_generation.py`
- `M backend/app/models/credit_transaction.py`
- `M backend/app/models/profile.py`
- `M backend/app/models/subscription.py`
- `A backend/app/models/subscription_plan.py`
- `A backend/app/repositories/profile_repository.py`
- `M backend/app/routers/admin.py`
- `A backend/app/routers/owner.py`
- `M backend/app/routers/subscriptions.py`
- `A backend/app/schemas/admin.py`
- `A backend/app/schemas/owner.py`
- `M backend/app/schemas/subscription.py`
- `A backend/app/services/admin_service.py`
- `M backend/app/services/credit_service.py`
- `A backend/app/services/onboarding_service.py`
- `M backend/app/services/profile_image_storage.py`
- `A backend/app/services/studio_photo_service.py`
- `M backend/app/services/subscription_service.py`
- `A backend/migrations/003_owner_subscriptions.sql`
- `A backend/migrations/004_studio_photo.sql`
- `A backend/tests/test_admin.py`
- `A backend/tests/test_migration_safety.py`
- `A backend/tests/test_owner_onboarding.py`
- `A backend/tests/test_owner_subscriptions.py`
- `A backend/tests/test_studio_photo.py`
- `A docs/003_owner_subscriptions_review.md`
- `A docs/004_studio_photo_review.md`
- `A docs/admin_ui_migration_rehearsal_review.md`
- `M docs/api-documentation.md`
- `A docs/step_42_final_verification.md`
- `A docs/steps_38_39_verification.md`
- `A docs/steps_40_41_verification.md`
- `A frontend/src/components/common/StudioPhoto.jsx`
- `M frontend/src/components/layout/AdminLayout.jsx`
- `M frontend/src/components/layout/OwnerLayout.jsx`
- `M frontend/src/components/public/PublicSections.jsx`
- `M frontend/src/pages/admin/Dashboard.jsx`
- `M frontend/src/pages/owner/Dashboard.jsx`
- `A frontend/src/pages/owner/StudioSetup.jsx`
- `M frontend/src/pages/owner/Subscription.jsx`
- `M frontend/src/pages/public/Landing.jsx`
- `M frontend/src/routes/AppRoutes.jsx`
- `A frontend/src/routes/OwnerOnboardingRoute.jsx`
- `M frontend/src/services/adminService.js`
- `A frontend/src/services/ownerService.js`
- `M frontend/src/styles/account.css`
- `A frontend/src/utils/onboarding.js`
- `A frontend/src/utils/subscription.js`
- `M frontend/tests/account.test.mjs`

---

# Historical Step 42 record (superseded status; retained evidence)

# Step 42 — migration correction and final verification

## Scope and decision

**BLOCKED: isolated MySQL environment not approved.** No MySQL connection, migration,
live account operation or database provisioning was performed. The repository has no
explicitly approved disposable MySQL configuration; backend .env/.env.example and process
variable *names* expose no isolated/test/rehearsal database configuration. No credential
values were printed. Existing tests use SQLite, private Redis sockets and temporary storage.
A name, reachable server or ordinary development credential is not proof of disposability.

The existing Mafia Studio / pending_plan state is user-reported, not independently read
from frameora_db. This task made no connection to that database, so all eight real accounts,
that studio profile, other profiles, timestamps and relationships were untouched.

## Exact SQL correction

003 previously required `owners_without_profile = 3`, a stale historical assumption.
Studio Setup legitimately creates a profile before a subscription is selected. The
subscription migration does not alter UserProfile and has no need for this restriction.

Only lines 359–365 were revised: replace the missing-profile-count rejection with a
read-only orphan-reference check:

```sql
IF EXISTS (SELECT 1 FROM `UserProfile` p LEFT JOIN `User` u ON u.id = p.user_id
           WHERE u.id IS NULL) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: orphan profile reference; separate data review required';
END IF;
```

Zero through three existing owner profiles are allowed. No profile data is changed,
normalized, reset or backfilled. No application-state promotion occurs. Existing exact
UserProfile schema, UNIQUE user_id and same-schema FK guards remain, as do all account,
role, catalogue, trigger, privilege, generated-slot, credit and empty-business-table guards.
An orphan stops migration for separate review; it is not repaired automatically.

003 before SHA256: `791d8c48e42b2991404f90ea00691c76f72d3b0e6a258000f97e5f9fcfb50e97`
003 after SHA256: `cc70ac2c3899b81812971804f2e8fd44e61692d893f905757ad910cf5730edd9`
004 unchanged SHA256: `d05ee738c72c5b969099d32c8dc0b770be924551f735d44a579c2e83b6e9b3e7`
A focused test reverses only this block and confirms the original 003 digest, proving
all other SQL bytes remain unchanged. This is a static regression check, not SQL execution.

## Static review result

- **003: reviewed, profile incompatibility corrected; MySQL execution NOT VERIFIED.**
  Requires MySQL 8.0.46, 16 exact tables, 8 users / 3 owners / 1 Admin, supported roles,
  exact three owner plans, and empty Subscription/CreditTransaction/CustomerProject/ShareLink.
  Existing profiles are now supported. Unexpected definitions, indexes, triggers, roles,
  grants or cross-database FKs remain fail-closed.
- **004: unchanged; MySQL execution NOT VERIFIED.** Nullable ASCII/binary VARCHAR(68)
  matches the deferred ORM mapping and generated 64-hex-plus-.png keys. Manual target,
  version, privileges, current columns/check names and engine verification is mandatory;
  comments are not executable guards. Regex/CHECK acceptance still requires MySQL rehearsal.
- Order is **003 -> post-verification -> 004 -> post-verification**. Applying 004 first
  fails 003's exact UserProfile baseline. Do not run migration 002 or a migration glob.
- 003 adds 7 CHECKs, 8 unique and 5 nonunique indexes, 4 generated columns and the signed-INT
  composite ledger-owner/subscription FK. Stable owner codes basic/trial/pro are backfilled
  only for guarded IDs/names/roles. Trial uniqueness includes all historical trial states;
  active/pending slots and activation/operation/grant keys remain intact.
- Models bind compatible column types; ORM metadata is not a replacement for the full
  migration DDL (CHECKs/collations/indexes must be inspected from MySQL). Never use create_all
  to apply this schema. Presence gates are not proof of full SQL constraint compatibility.
- Files are forward-only and **not rerunnable**. Preflight is before application-table DDL,
  but helper creation and each ALTER can commit independently. A failure may leave a helper
  routine or partial schema. Never auto-retry, use --force, drop history, or assume ROLLBACK
  undoes completed DDL. Keep writers paused, inspect state and obtain a reviewed repair or
  restore plan. Inspect ambiguous lost-connection outcomes before retrying.

## Application behavior retained

No application, frontend, configuration, dependency or authentication code was changed.
Existing service/tests cover password login, mocked Google/OIDC/linking, JWT/Admin policy,
owner role isolation, phone validation, no-profile onboarding, private photo normalization,
replacement/removal, Basic anniversary/no carryover, Basic-to-Trial, one-time 100-credit
14-day Trial, exact expiry fallback (including expired Pro), read-only Admin details,
public privacy, dashboard mapping and migration-unavailable errors. Paid Pro activation
and password/auth_version activation remain disabled. Actual Google browser/provider flows,
InnoDB races/deadlocks, real MySQL persistence and interactive visual checks are not proven
by these tests. Future spending/project/share endpoint enforcement remains outside scope.

## Files changed in this task

- backend/migrations/003_owner_subscriptions.sql — only profile preflight correction.
- backend/tests/test_migration_safety.py — new static and in-memory predicate checks.
- docs/003_owner_subscriptions_review.md — corrected baseline and verification expectations.
- docs/004_studio_photo_review.md — clarified current deferred model and ordering; SQL unchanged.
- docs/admin_ui_migration_rehearsal_review.md — historical-review supersession notice.
- docs/step_42_final_verification.md — this consolidated report/procedure.

All earlier working-tree changes retained. No commits or pushes.

## Next: isolated rehearsal (NOT executed)

1. Obtain explicit approval for a disposable MySQL 8.0.46 **instance/target**, its server
   UUID and an appropriately restricted migration account that cannot access frameora_db.
   Do not create/drop databases automatically. Operator provisions the approved target.
2. Provision an approved mysql login-path `frameora-rehearsal` and database
   `frameora_rehearsal_review`. Credentials stay in the private client configuration.
3. Load a separately reviewed synthetic 16-table baseline: 4 users, 3 owners, 1 Admin;
   one owner with complete synthetic studio details and pending_plan; two owners without
   profiles; exact three catalogue rows; empty business tables. No real passwords, account
   records or studio details. Record all synthetic profile values/timestamps privately.
4. After approval, from repository root, verify the target and grants (read-only):

```bash
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --execute='SELECT VERSION(), DATABASE(), @@hostname, @@server_uuid, CURRENT_USER(), CURRENT_ROLE(); SHOW GRANTS;'
```

Match these results to the approved identity. Verify all table definitions and enabled-role
privileges using docs/003_owner_subscriptions_review.md. Then run each command separately:

```bash
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --show-warnings < backend/migrations/003_owner_subscriptions.sql
```

Stop and execute every 003 postcheck from its review. Preserve all baseline profile/user
values; owners_without_profile is now expected to equal its recorded before value, not 3.
After successful verification and 004 prerequisites:

```bash
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --show-warnings < backend/migrations/004_studio_photo.sql
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --execute='SHOW CREATE TABLE UserProfile; SELECT COUNT(*) AS profiles, SUM(studio_photo IS NOT NULL) AS photo_references FROM UserProfile;'
```

Verify unchanged original profile data and NULL new references before test uploads.
Use disposable accounts/private storage for real MySQL idempotency, two-session concurrent
trial/basic activation, duplicate grant, cross-owner FK, invalid status/date/sign/key,
trial/Pro expiry, month-end anniversary and photo persistence tests. Verify preflight
failures and partial-DDL recovery on separately approved disposable targets, never by
resetting an existing live database. Confirm paid activation stays absent.

## Later fresh backup and development migration (separate approval REQUIRED)

Only after isolated rehearsal succeeds:
1. Obtain approval for read-only live metadata checks and a fresh private backup. Confirm
   server/database identity, all counts, expected columns and no partial migrations. Review
   any drift; do not change real data to fit preflight. Stop all writers for the maintenance
   window, including studio/photo operations and scheduled workers.
2. Configure approved private mysql login paths `frameora-backup` (read-only backup privileges)
   and `frameora-migration` (reviewed migration grants). Never print credentials or put a
   password on the command line. Example future backup commands, NOT executed:

```bash
umask 077
backup_dir=$(mktemp -d "$HOME/Documents/Final/frameora-backups/step42.XXXXXX")
mysqldump --login-path=frameora-backup --single-transaction --routines --triggers --events --hex-blob --no-tablespaces --set-gtid-purged=OFF frameora_db > "$backup_dir/frameora_before_003_004.sql"
```

Verify command success, privately check the backup, and prove restoration in a separately
approved protected recovery environment. Do not import real account data into disposable
application-test fixtures or print backup contents. Preserve before/after schema and data
manifests securely, including Mafia Studio, every profile column and timestamps.
3. Present the reviewed SQL digests, successful rehearsal, backup verification, target
   identity and maintenance window for **explicit live migration approval**.
4. Only after that approval, run 003 on development, stop for all postchecks, then 004 and
   its postchecks. These are future commands, not authorization to execute now:

```bash
mysql --login-path=frameora-migration --database=frameora_db --batch --show-warnings < backend/migrations/003_owner_subscriptions.sql
```

After 003 is verified:

```bash
mysql --login-path=frameora-migration --database=frameora_db --batch --show-warnings < backend/migrations/004_studio_photo.sql
```

Never chain these blindly or use --force. Stop on error and inspect the actual state;
recovery requires explicit review. Compare all eight account records and original studio
profile fields privately against the backup; verify 16 tables and no unexpected writes.
5. Verify private persistent storage and permissions; keep both auth flags false. Resume
   writers only after checks. Test browser flows with separately authorized disposable
   accounts/environment, not existing accounts without permission. Check Google chooser,
   login/linking, all role routes, setup->plan->dashboard, photo operations, Admin read-only
   views, exact landing copy, mobile/desktop themes and disabled Paid Pro.

## Release decisions

- GO: targeted correction and continued isolated testing/rehearsal preparation.
- **NO-GO: enable subscriptions or studio-photo persistence on development now.**
  Isolated MySQL rehearsal, metadata/backup verification and explicit live approval remain.
- **NO-GO: declare all 42 steps fully complete.** Interactive browser, live Google/provider
  and MySQL release verification are still pending. Safe implementation/testing progress
  does not constitute approval or evidence of live deployment.

## Executed checks — final results

| Command/check | Result |
|---|---|
| backend: `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v` | **93 passed, 0 failed**, 133.162 seconds |
| frontend: `node tests/account.test.mjs` | **38 passed, 0 failed** |
| frontend: `npm run build` | **PASS**, Vite 6.4.5, 1708 modules |
| Python `ast.parse` over backend/app and backend/tests | **87 files passed**, no imports/connections |
| root: `git diff --check` | **PASS** |
| MySQL migration parser/DDL/concurrency/persistence rehearsal | **BLOCKED — isolated target not approved** |
| Interactive browser / real Google provider verification | **NOT TESTED** |

The backend suite includes four new migration-safety checks: accepting 0/1/2/3 profiles
without mutations, orphan detection without repair, proving only the 003 guard changed,
and proving 004 is unchanged. The extracted SELECT runs only against a minimal in-memory
SQLite fixture. Neither full SQL migration is executed; this is not a 16-table MySQL
rehearsal. Existing security fixtures use locally signed JWTs, mocked provider exchanges,
disposable SQLite, and private Redis sockets/storage. Production connections are blocked.
Frontend checks use SSR/pure decisions/mocked Axios, not live browser automation.
Existing dependency deprecation warnings remain; no dependencies were installed/changed.
