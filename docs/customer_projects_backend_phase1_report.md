# Studio Owner Customer Projects Backend Phase 1

## Status

Implemented owner-only customer-project create, list, detail, and update APIs using the existing `CustomerProject` columns, including `project_title` and `shoot_location`. Project quotas and downgrade editability are enforced server-side. No delete, sharing, or AI-generation behavior was added.

The user confirmed that the live MySQL `CustomerProject` table has `project_title VARCHAR(150) NULL` and `shoot_location VARCHAR(255) NULL`. This update did not connect to `frameora_db`; that schema confirmation is user-provided and was not independently queried.

## Files changed

- `backend/app/models/customer_project.py` — maps the existing project columns, including title and location.
- `backend/app/schemas/project.py` — strict create, partial-update, and response contracts with title/location validation.
- `backend/app/repositories/project_repository.py` — owner-scoped active-project queries and insertion.
- `backend/app/services/project_service.py` — ownership, quota, editability, locking, and transaction rules.
- `backend/app/routers/projects.py` — owner-authenticated routes with no-store/query validation.
- `backend/app/main.py` — registers the projects router.
- `backend/tests/test_customer_projects.py` — disposable SQLite API/service regression tests, including title/location persistence, response, and validation.
- `backend/tests/test_owner_credit_mysql.py` — adds an opt-in InnoDB test for concurrent project creation. It only uses the explicitly validated disposable MySQL socket and skips without it.

## API endpoints

All routes require an authenticated Studio Owner; Normal Users and Admins are rejected. Responses omit owner IDs and soft-delete metadata.

| Method and path | Behavior |
|---|---|
| `POST /owner/projects` | Create a project; returns `201` and the created project. |
| `GET /owner/projects` | List the owner's active projects in `created_at ASC, id ASC` order. |
| `GET /owner/projects/{project_id}` | Retrieve one active project owned by the caller. |
| `PATCH /owner/projects/{project_id}` | Partially update an editable project. |

Create accepts `customer_name` (required), nullable `project_title` (max 150), `customer_contact`, `event_type`, nullable `shoot_location` (max 255), `shooting_date`, and `requirements`. Update accepts one or more of those same fields. Text values are trimmed, control characters are rejected, and empty optional title/location strings normalize to `null`. The response includes all stored fields, `id`, `created_at`, and computed `is_editable`. Create, update, list, and detail use the same schema/model fields.

Unknown fields continue to be rejected; no delete endpoint was added because deletion was not among the specified Phase 1 operations.

Typical errors are `401` unauthenticated, `403` wrong role, `404` missing/deleted/not-owned project, `409` missing subscription/project quota/read-only project, and `422` invalid or unsupported fields. Database failures use the application's existing sanitized error handling.

## Ownership and role security

- Router dependencies require the current database role to be `owner`; client-supplied IDs/roles are not accepted.
- The owner ID always comes from the authenticated user.
- Project detail and update queries include both project ID and owner ID. A cross-owner lookup returns `404`.
- Every create/update locks and revalidates the parent `User` row before entitlement resolution and project-count/editability checks.
- Project list and detail also derive editability only from the caller's own active projects.
- Project routes inherit the owner request's no-store headers and reject query parameters.

## Subscription limits and downgrade behavior

The implementation reuses the existing subscription catalogue and owner entitlement resolver. It does not activate subscriptions or issue credits.

- Free Basic: at most 2 active projects.
- Free Trial: at most 10 active projects.
- Paid Pro: at most 50 active projects when an active Pro subscription record exists; checkout/activation remains disabled.
- New projects are rejected when the number of non-deleted projects reaches the current plan's maximum.
- After trial/paid expiry resolves to Basic, all projects remain stored. Only the oldest two active projects, ordered by `created_at ASC, id ASC`, are editable; newer projects are returned with `is_editable: false`, and update attempts receive `409`.
- Soft-deleted rows are omitted from lists, return `404` on detail/update, and do not consume a project slot.
- Expiry is persisted only on create/update operations; project reads do not write or grant credits.

Creation and edits use the existing parent-user `SELECT ... FOR UPDATE` lock, so cooperating owner project writers serialize quota checks in MySQL. The SQLite test verifies the owner lock is acquired before the count check. An opt-in real InnoDB concurrent-create test was added, but was not run in this session because no explicit disposable MySQL socket was supplied.

## Database compatibility and migrations

- No table or column was added, removed, or altered. No SQL or migration was run.
- The model maps the existing fields: `id`, `studio_owner_id`, `customer_name`, `project_title`, `customer_contact`, `event_type`, `shoot_location`, `shooting_date`, `requirements`, `created_at`, and `deleted_at`.
- The existing owner/live-project ordering index is represented in the model mapping; no DDL is emitted by importing the model or starting the API.
- The current CRUD scope uses the user-confirmed existing `project_title VARCHAR(150) NULL` and `shoot_location VARCHAR(255) NULL` columns; no further migration is required for these fields, based on that confirmation.
- The 17-table schema is preserved. No live database query was performed, so the supplied table definition was not independently re-verified in this update.

## Test results

- Focused customer-project suite: **9 passed** on disposable SQLite, including title/location create, update, list/detail response, max-length, and control-character cases.
- Full backend suite: **179 passed, 6 skipped**. The skipped tests are opt-in MySQL tests that require the explicitly marked disposable MySQL socket.
- `compileall` for changed Python modules: passed.
- `git diff --check`: passed.
- Existing authentication, subscription, Normal User AI, and owner-credit regressions were included in the full suite.

No live Pollinations request, real credit spend, subscription mutation, or live database access was performed. Existing Starlette/httpx and Authlib/httpx deprecation warnings remain.

## Remaining work and dependencies

1. Implement the frontend project list/create/detail/edit flow against the four routes above; render `is_editable` as server-authoritative state.
2. Run the opt-in concurrent-create test against a separately provisioned disposable MySQL instance before deployment.
3. Sharing, project-to-photography-plan association, project image galleries, and a delete/archive API remain out of scope.

## Manual verification

Use an isolated test database and an owner test account only:

1. Select Basic and create two projects; verify a third returns `409`.
2. Start a Trial explicitly, create up to ten projects, and verify an eleventh returns `409`.
3. Expire the Trial in a test clock; confirm all rows remain, the oldest two are editable, and a later project update returns `409`.
4. Attempt to retrieve/update another owner's project; verify `404`.
5. Soft-delete a test row directly in the isolated database; verify it is hidden and no longer consumes a quota slot.
6. Confirm Pro checkout remains disabled; test the 50-project entitlement only with isolated seeded subscription data.
