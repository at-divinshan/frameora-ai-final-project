> Historical pre-Step-42 review. The zero-profile blocker below has now been corrected
> with explicit user authorization in migration 003. No MySQL execution has occurred.
> Current evidence and release gates: docs/step_42_final_verification.md.

# Admin UI corrections and Step 42 safe verification

## Isolation decision

**STATIC-ONLY migration review. No MySQL connection or SQL execution occurred.**
Repository configuration filenames, backend environment key names (not values), process
configuration key names, existing test fixtures and migration docs were inspected.
No explicit isolated MySQL credentials/target, disposable database declaration or
rehearsal provisioning configuration was found. Existing tests use disposable SQLite
and private temporary Redis/storage. A database name alone is not isolation evidence.
No existing database was created, dropped, truncated, overwritten or modified.

## UI changes

- Dashboard vs Studios uses pathname+hash matching; exactly one active gradient and
  aria-current link. Studios points to the existing dashboard section and scrolls there.
- Prominent API-derived counts, balanced metric cards, explicit loading/error states.
- Fixed column sizing, padded rows, readable one-line values with overflow/title text,
  aligned detail buttons, horizontal table scrolling. Full values remain in owner detail.
- Search no longer has the inherited disabled cursor; clear filters, readable selects,
  page totals/bounds and readable Pending Studio / Pending Plan / Completed labels.
- Existing API data, detail/photo access, role checks and disabled future features remain.

Files changed in this task:
- frontend/src/components/layout/AdminLayout.jsx
- frontend/src/pages/admin/Dashboard.jsx
- frontend/src/styles/account.css
- frontend/tests/account.test.mjs
- docs/admin_ui_migration_rehearsal_review.md (new)

Neither migration SQL file nor any backend/auth/config file was changed.

## Static migration review

| Area | Finding |
|---|---|
| 003 order | Procedure and preflights precede all application-table ALTERs; plan catalogue backfill follows all five ALTERs (003 lines 384–463). Run 003 before 004: 003 checks the exact UserProfile column list at lines 169–175 and would reject a photo column added first. |
| Baseline blocker | 003 lines 353–362 requires exactly 8 users, 3 owners, 1 Admin, and **all 3 owners lacking profiles**. Reported 4 users + 3 owners + 1 Admin fits the account count, but current profile counts were NOT queried. Any Studio Setup already saved causes the profile preflight to stop. Review/approve a baseline-guard revision if needed; never remove profiles or change real records to satisfy it. |
| Existing data | 003 lines 363–380 requires empty Subscription/CreditTransaction/CustomerProject/ShareLink and exact three catalogue rows. Nonempty tables require a separate backfill design, not automatic coercion. Existing accounts/studio fields are not written. 004 adds a nullable column with NULL default, no backfill. |
| Privileges | 003 lines 46–120 checks direct/enabled-role grants before trusting trigger metadata. Requires SELECT, ALTER, CREATE, INSERT, UPDATE, REFERENCES, TRIGGER and routine permissions at relevant scopes. Invisible/wildcard/partial-revoke grant evidence fails closed. Real role/privilege behavior remains untested. |
| FKs | 003 lines 270–351 rejects cross-database references and unexpected cascade actions. New ledger owner/subscription signed INT pair references unique Subscription(user_id,id), matching inspected mappings. Actual current FK types still need MySQL metadata verification. |
| Uniqueness | Stored generated trial-owner slot covers every trial status; active/pending slots enforce one per owner. Owner+activation digest and operation/grant-period keys guard duplicate activation/grants. Existing original indexes retained; added ordering indexes support later limits. |
| ORM compatibility | SubscriptionPlan currency CHAR(3), plan code length, nullable subscription end, signed INT FKs, binary key sizes and generated expressions align with planned SQL. UserProfile photo is deferred/omitted on legacy inserts. ORM metadata is not the complete migration DDL (CHECKs/collations/nonunique indexes must be verified from SQL); do not deploy via create_all. |
| 004 | Lines 7–10 add nullable ASCII/binary VARCHAR(68) and case-sensitive key CHECK. Application keys are 64 hex characters + .png. It is a single ALTER with manual preflight comments, not an automated isolation/version/privilege guard. Regex/CHECK acceptance has NOT been parsed on MySQL 8.0.46 here. |
| Idempotency | Migration files themselves are **not rerunnable/idempotent**. Duplicate/partial schema should fail. Do not use --force, automatic retries or migration globs. Application activation idempotency is a separate feature. |
| Atomicity/recovery | MySQL DDL implicitly commits; procedure creation and each successful ALTER can persist before later failure. ROLLBACK in 003 cannot reverse prior DDL. Helper routine can remain after failure. Stop, inspect reached state, prepare an approved forward repair or verified restore; do not drop columns/history as rollback. 004 is independent and not a transaction with 003. |
| Operational gate | Missing schema returns controlled unavailable responses. Presence checks do not replace full MySQL CHECK/index/expression verification and isolated concurrency testing. Paid Pro remains unavailable. No Admin mutation APIs exist. |

Official references checked (documentation review is not a server rehearsal):
- [MySQL 8.0 implicit commits](https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/implicit-commit.html)
- [MySQL 8.0 generated columns](https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/create-table-generated-columns.html)
- [MySQL 8.0 CHECK constraints](https://docs.oracle.com/cd/E17952_01/mysql-8.0-en/create-table-check-constraints.html)

Historical review notes describing subscriptions as unimplemented predate Steps 36–39.
The code now exists; migration readiness and verified payments are still separate gates.
Admin photo read access was added in Step 40; photos remain unavailable publicly.

## Exact safe next actions — approval/provisioning required, NOT executed

1. Obtain a verified disposable MySQL **8.0.46** instance and restricted migration login
   that cannot access frameora_db. Record host/server UUID, database identity and explicit
   disposable ownership. Do not assume an existing similarly named database is disposable.
2. Have the operator provision `frameora_rehearsal_review` on that isolated instance and
   an approved mysql login-path `frameora-rehearsal`. Populate only schema and synthetic
   baseline fixtures via a separately reviewed setup; never copy real account credentials.
3. Review the owner-profile guard against the intended deployment baseline. Approve any
   necessary SQL revision explicitly before execution. Current SQL remains unchanged.
4. From the repository root, after isolation and fixture approval, use these commands
   individually. These are future commands, not permission to execute on development:

```bash
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --execute='SELECT VERSION(), DATABASE(), @@hostname, @@server_uuid, CURRENT_USER(), CURRENT_ROLE(); SHOW GRANTS;'
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --execute="SELECT COUNT(*) AS users, SUM(role='owner') AS owners, SUM(role='admin') AS admins FROM User; SELECT COUNT(*) AS owners_without_profile FROM User u LEFT JOIN UserProfile p ON p.user_id=u.id WHERE u.role='owner' AND p.id IS NULL; SHOW CREATE TABLE UserProfile;"
```

Verify identity against the operator's record, all 16 table definitions, effective
privileges, plan catalogue and empty-business-table preconditions in the original
review. Stop on any mismatch. Only after approval and positive preflight evidence:

```bash
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --show-warnings < backend/migrations/003_owner_subscriptions.sql
```

Stop and inspect after 003. Run the postchecks in docs/003_owner_subscriptions_review.md;
confirm all 7 CHECKs, 8 unique/5 nonunique indexes, 4 generated columns and ownership FK.
After those pass and 004 preconditions are verified:

```bash
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --show-warnings < backend/migrations/004_studio_photo.sql
mysql --login-path=frameora-rehearsal --database=frameora_rehearsal_review --batch --execute='SHOW CREATE TABLE UserProfile; SELECT COUNT(*) AS profiles, SUM(studio_photo IS NOT NULL) AS photo_references FROM UserProfile;'
```

Then perform isolated MySQL negative/duplicate/concurrent activation, credit grant,
expiry and photo persistence checks. Rehearse partial-failure recovery separately.
Only after successful rehearsal, a fresh approved live metadata review, verified backup
and writer quiescence should a **separate explicit approval** authorize deployment to
frameora_db. Configure private persistent photo storage with restrictive permissions.
Keep AUTH_VERSION_ENABLED=false and PASSWORD_MANAGEMENT_ENABLED=false; do not run 002.
No automatic subscription/photo activation or environment changes are part of this task.

## Browser checks still required

At desktop and 375px widths, switch Dashboard/Studios/Profile/Settings and verify exactly
one gradient, hash scrolling, table horizontal scrolling, readable names, detail/photo
views, theme contrast, keyboard focus, filter clearing and pagination. SSR/build checks
cannot establish actual browser layout or overflow. Use existing data read-only or
isolated fixtures; do not perform live activation/upload tests.

## Executed verification

- Backend: `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`
  from backend: **89 passed, 0 failed**. Includes Admin authorization/list/detail/photo,
  missing 003/004, read-only Admin access, owner isolation, Basic/Trial rules, onboarding,
  profile/photo/privacy and existing auth/Google regressions. No live MySQL testing.
- Frontend: `node tests/account.test.mjs` from frontend: **38 passed, 0 failed**.
  Added SSR checks for exactly one active sidebar link (Dashboard, Studios hash, Profile,
  Settings), current-link accessibility, real/zero metrics, loading/error and status labels.
  Existing route, activation/eligibility, locked hero and API payload checks remain passing.
- Frontend: `npm run build`: **PASS**, Vite 6.4.5 / 1708 modules.
- Repository: `git diff --check`: **PASS**.
- Browser pixel/layout checks, MySQL parsing/DDL/rehearsal/concurrency: **NOT TESTED**.

frameora_db and all real accounts were untouched; no migrations or live SQL executed,
no packages installed, no flags changed, no commits or pushes.
