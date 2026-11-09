# Studio Owner Customer Projects — Full Impact Audit

**Date:** 2026-11-05  
**Scope:** Read-only audit of existing Customer Project, AI asset, subscription-limit, and future sharing code and schema definitions. No source code or database changes, migrations, Pollinations calls, credit spending, or subscription changes were made.

## Executive summary

Customer Projects and sharing are **not implemented end to end** in the inspected repository. The frontend has zero-byte placeholder files for project CRUD and sharing, no project/share routes, disabled owner navigation items, and a dashboard placeholder. Backend model/schema/router/service/repository files for projects and sharing are also zero bytes. The backend application does not import or register project or sharing routers.

The existing database definitions appear to provide a starting point: `CustomerProject` has an owner FK and customer/event/date/requirements fields; `ShareLink` has project/generation references, a hashed token, active flag, and expiry. `PhotographyPlan.project_id` is present in the ORM mapping but deliberately not mapped as a SQLAlchemy FK; the repository always sets it to `NULL`. AI generations and media assets are stored separately and the current owner gallery is generation-based, not project-based.

The plan catalogue is code-validated for Basic (2 projects/3 links), Trial (10/20), and Pro (50/100); Pro activation is disabled. The entitlement resolver returns the current plan limits for display. **No project-count or share-link-count enforcement, downgrade preservation/read-only rules, CustomerProject CRUD API, customer-authenticated share viewing, or owner share-link lifecycle API was found.**

The inspected `CustomerProject` schema has no dedicated `project_title` or `location` columns. It has `event_type` and `requirements`, which may represent photography type and description only if product semantics approve that mapping. A migration is likely required for the missing title and location (and possibly a dedicated photography-type column if `event_type` is not equivalent). This is based on migration source, not a live `frameora_db` query.

## Findings by implementation status

| Area | Verified status |
|---|---|
| Subscription catalogue values | **Implemented in code:** the subscription service validates Basic 2 projects/3 links, Trial 10/20, and Pro 50/100. Pro checkout/activation remains disabled. Live database catalogue values were not queried. |
| Entitlement limits | **Partially implemented:** owner entitlement and dashboard responses expose plan maxima. These are informational; project/link usage counts are unavailable and the entitlement resolver does not enforce either limit. |
| CustomerProject table definition | **Exists in migration preflight contract:** expected columns include owner, customer, event type, shoot date and requirements. The SQLAlchemy model file is empty. The live table was not queried. |
| Project CRUD and ownership checks | **Missing:** project model/schema/repository/service/router files are empty; no project endpoint is registered. |
| Project form/pages/routes | **Missing:** frontend project pages/services are empty; no project routes exist. Owner sidebar project navigation is disabled and the dashboard “View All” is disabled. |
| AI image-to-project association | **Partially representable, not implemented:** a project may be referenced by a photography plan in the existing database design, then a generation references the plan, and media assets reference generations. The current repository sets every new plan’s `project_id` to `NULL`; no project API or project gallery view exists. |
| Downgrade project handling | **Missing:** no oldest-first entitlement selection, editability/read-only enforcement, or project preservation behavior exists in project APIs (there are no project APIs). |
| ShareLink table definition | **Exists in migration preflight contract:** project/generation references, `token_hash`, `is_active`, `expires_at`, and `created_at`. The SQLAlchemy model file is empty. The live table was not queried. |
| Owner link create/deactivate and customer login view | **Missing:** sharing model/schema/service/router and frontend files are empty; no route is registered. |
| Downgrade share-link handling | **Missing:** no active-link count enforcement or oldest-three preservation/deactivation behavior was found. |
| Project/share tests | **Missing:** no project- or sharing-specific backend/frontend test files were found. Existing photography-plan tests only verify personal plans and reject client-supplied project IDs. |

## Frontend files and routes

### Existing relevant surfaces

- [`frontend/src/components/layout/OwnerLayout.jsx`](../frontend/src/components/layout/OwnerLayout.jsx): “Customer Projects” and “Share Links” are disabled buttons marked coming soon. The project search control is also disabled.
- [`frontend/src/pages/owner/Dashboard.jsx`](../frontend/src/pages/owner/Dashboard.jsx): Active Projects and Active Share Links metrics are `Unavailable`. “Recent Customer Projects” is an empty-state placeholder; View All is disabled. Project/share maxima are shown as informational only.
- [`frontend/src/pages/owner/Subscription.jsx`](../frontend/src/pages/owner/Subscription.jsx): displays server catalogue maxima and preserves explicit Start Free Trial behavior. Pro activation remains disabled.
- [`frontend/src/pages/owner/AIResults.jsx`](../frontend/src/pages/owner/AIResults.jsx): owner gallery lists generations and their images/guides, not Customer Projects. It has no project filter, grouping, or project association control.
- [`frontend/src/pages/owner/AIGenerator.jsx`](../frontend/src/pages/owner/AIGenerator.jsx): uses owner photography plans and creates generations; no project selection/association field is sent.
- [`frontend/src/routes/AppRoutes.jsx`](../frontend/src/routes/AppRoutes.jsx): authenticated owner routes exist for profile, settings, setup, subscription, AI generation, gallery, and dashboard. No `/owner/projects`, project detail/edit, or owner share-link route exists. There is no customer-only shared-image route.

### Empty frontend placeholders

The following paths exist but contain zero lines:

- [`frontend/src/pages/owner/Projects.jsx`](../frontend/src/pages/owner/Projects.jsx)
- [`frontend/src/pages/owner/CreateProject.jsx`](../frontend/src/pages/owner/CreateProject.jsx)
- [`frontend/src/pages/owner/SharedLinks.jsx`](../frontend/src/pages/owner/SharedLinks.jsx)
- [`frontend/src/services/projectService.js`](../frontend/src/services/projectService.js)
- [`frontend/src/services/shareService.js`](../frontend/src/services/shareService.js)
- [`frontend/src/components/sharing/ShareLinkCard.jsx`](../frontend/src/components/sharing/ShareLinkCard.jsx)
- [`frontend/src/components/sharing/ShareModal.jsx`](../frontend/src/components/sharing/ShareModal.jsx)
- [`frontend/src/pages/public/SharedPreview.jsx`](../frontend/src/pages/public/SharedPreview.jsx)

No related project/share frontend tests were found. Do not treat empty placeholders as working CRUD or sharing functionality.

## Backend files and endpoints

### Existing related behavior

- [`backend/app/services/subscription_service.py`](../backend/app/services/subscription_service.py): validates the owner catalogue’s exact maxima and exposes them in catalogue responses. Trial expiry/fallback changes the effective plan to Basic, but does not process projects or links.
- [`backend/app/services/owner_entitlement_service.py`](../backend/app/services/owner_entitlement_service.py): returns `max_projects` and `max_share_links` for the effective plan. It has no project/share counts, editability calculation, or enforcement.
- [`backend/app/models/photography_plan.py`](../backend/app/models/photography_plan.py): includes nullable `project_id`; comments explain that CustomerProject is not mapped in the application and its FK remains database-managed.
- [`backend/app/repositories/plan_repository.py`](../backend/app/repositories/plan_repository.py): `create_for_user` explicitly writes `project_id=None`; current plan creation cannot associate a plan with a project.
- [`backend/app/services/owner_generation_service.py`](../backend/app/services/owner_generation_service.py): generation ownership is tied to the authenticated owner and saved photography plan; private gallery behavior is generation-based. There is no project CRUD or project membership logic.
- [`backend/app/models/ai_generation.py`](../backend/app/models/ai_generation.py) and [`backend/app/models/media_asset.py`](../backend/app/models/media_asset.py): mappings include generation user/plan IDs and media asset user/plan/generation IDs. They do not include a direct `project_id` field.

### Missing backend implementation

These existing files are zero bytes:

- [`backend/app/models/customer_project.py`](../backend/app/models/customer_project.py)
- [`backend/app/models/share_link.py`](../backend/app/models/share_link.py)
- [`backend/app/schemas/project.py`](../backend/app/schemas/project.py)
- [`backend/app/routers/projects.py`](../backend/app/routers/projects.py)
- [`backend/app/routers/sharing.py`](../backend/app/routers/sharing.py)
- [`backend/app/services/project_service.py`](../backend/app/services/project_service.py)
- [`backend/app/services/share_service.py`](../backend/app/services/share_service.py)
- [`backend/app/repositories/project_repository.py`](../backend/app/repositories/project_repository.py)

[`backend/app/main.py`](../backend/app/main.py) registers auth, users, admin, subscription, plan, Normal User AI, and owner AI routers. It does not import/register project or sharing routers. Consequently no implemented project endpoints, owner share-link endpoints, or authenticated-customer shared viewing contract were found.

The current implemented `/owner/photography-plans` APIs are not CustomerProject CRUD. The personal-plan schemas forbid unknown input fields, including `project_id`, and repository creation always sets it to null. Existing `backend/tests/test_photography_plans.py` confirms the Normal User plan APIs reject client-supplied project IDs; it does not test Customer Projects.

## Database structure and migration compatibility

### Source-defined structure (not live-database verified)

[`backend/migrations/003_owner_subscriptions.sql`](../backend/migrations/003_owner_subscriptions.sql) verifies the pre-existing table set and exact preflight column/FK signatures. It does not create CustomerProject or ShareLink. Its expected `CustomerProject` columns are:

`id`, `studio_owner_id`, `customer_name`, `customer_contact`, `event_type`, `shooting_date`, `requirements`, `created_at`.

Its expected `ShareLink` columns are:

`id`, `project_id`, `generation_id`, `token_hash`, `is_active`, `expires_at`, `created_at`.

The same migration checks these relations:

- `CustomerProject.studio_owner_id -> User.id`.
- `ShareLink.project_id -> CustomerProject.id` (nullable column) and `ShareLink.generation_id -> AIGeneration.id`.
- `AIGeneration.plan_id -> PhotographyPlan.id` and `AIGeneration.user_id -> User.id`.
- `PhotographyPlan.project_id` is described in the ORM source as an existing database-managed FK to CustomerProject, but the currently inspected SQLAlchemy mapping intentionally does not declare it.
- MediaAsset mapping includes user, plan and generation IDs; migration 003’s verified FK list does not establish its database constraints. Inspect the live schema before relying on any additional FK or uniqueness behavior.

Migration 003 also adds `CustomerProject.deleted_at` and an owner/deleted/created ordering index, plus ShareLink generation/active/expiry and generation/active/creation ordering indexes. Those changes support tombstones and ordered link queries, but do not implement CRUD or downgrade enforcement. Project title and location are absent from the expected CustomerProject signature. `requirements` could hold a description and `event_type` might hold photography type, but those mappings need product approval and do not supply a project title or location.

**Likely migration requirement:** Add dedicated project title and location columns; add a separate photography type column if `event_type` is not the agreed equivalent. If association requirements demand a direct project FK on MediaAsset or AIGeneration rather than the existing plan→project→generation chain, that would be an additional schema/design decision. The existing nullable PhotographyPlan.project_id and ShareLink project reference alone do not ensure project and generation belong to the same owner.

**Live database caveat:** No live `frameora_db` read-only query was made for this audit. Table existence, installed migration state, exact live definitions, engine/constraints, data quality, and whether migration 003 has run remain unverified. The findings above are from SQLAlchemy source, migration preflight contracts, code comments and tests, not live metadata.

## Project limits and downgrade rules

Plan values are enforced as catalogue consistency checks in [`backend/app/services/subscription_service.py`](../backend/app/services/subscription_service.py):

| Plan | Configured project maximum | Configured active-link maximum | Activation |
|---|---:|---:|---|
| Free Basic | 2 | 3 | Available |
| Free Trial | 10 | 20 | Explicit user activation; one trial |
| Paid Pro | 50 | 100 | Disabled |

These are configured/catalogue values, **not operational enforcement**. The project and sharing modules are empty. No service checks project creation against current limits, counts active links, or marks entities editable/read-only.

Required behavior not implemented:

- Keep all projects on downgrade; never delete projects or images.
- Define “oldest” deterministically, recommended by `created_at ASC, id ASC`.
- Keep only the oldest two projects editable on Basic; make all others read-only. Trial and Pro limits are 10 and 50 respectively when those plans are actually available.
- Keep the oldest three active share links on Basic; deactivate the rest. Trial and Pro allowances are 20 and 100. Preserve inactive records/history.
- Enforce editability on every backend write endpoint, not only by disabling frontend controls.
- Serialize concurrent project creation and share-link activation against the same owner lock/transaction so simultaneous requests cannot exceed limits.
- Define how a downgrade (including trial expiry fallback) is applied when current project/link usage exceeds the new limit. A computed oldest-first policy can preserve records without persisting an editable flag, but must be enforced consistently at read/write time or materialized atomically.

No project or link count fields are supplied by the owner entitlement endpoint; dashboard values “Unavailable” are accurate for current code.

## Ownership and security risks

No active project/share endpoints were found, so there is no verified runtime implementation to certify as secure. The future API needs explicit protections:

- Require authenticated `owner` role for project CRUD and link management; derive owner identity from authenticated context, never a request body owner ID.
- Scope list/detail/update/delete operations by both resource ID and owner ID. A missing and another owner’s resource should not reveal existence.
- Validate project ownership for every photography plan, generation and asset association. The schema’s separate FKs do not by themselves guarantee that a ShareLink’s project and generation belong to the same owner.
- Enforce limits and read-only state server-side under concurrency control. Frontend-disabled buttons are not authorization.
- Preserve records on downgrade. “Read-only” must block create/edit/delete actions as specified while still allowing safe viewing and image retrieval.
- Store only a cryptographically strong token hash in ShareLink; avoid returning hashes, internal IDs, or storage keys unnecessarily. Use no-store/referrer protections and non-enumerating failures for private endpoints.
- For future shared viewing, require an authenticated customer and validate the authenticated customer’s authorization for the project/link. Possession of a link alone must not disclose images. Confirm the customer-to-project relationship rule before implementation.
- Link creation/deactivation must verify owner ownership across the link, project, generation and each image. Active-link counts must account for expiration and deactivation consistently.
- Never expose private image storage paths or bypass the existing authenticated private image retrieval protections.

## Gallery and future sharing dependencies

The current Owner Gallery returns owner-credit generations and image metadata, with authenticated owner image retrieval. It has no project query, project grouping, or association controls. A future project gallery will need a clear association path—e.g. project → owned photography plans → generations → assets—and checks that every edge belongs to the same authenticated owner. Existing plans are currently detached (`project_id=None`), and the current plan create/patch contracts do not expose project association.

Future sharing is not implemented. The database design provides a `ShareLink` token hash, active/expiry state, project reference and required generation reference, but no API or user-facing page uses it. The required customer login gate, project/customer authorization, owner create/deactivate flow, private image serving, Basic/Trial/Pro active-link quotas, and oldest-three-on-downgrade policy remain design and implementation dependencies.

## Recommended implementation phases

1. **Approve domain mapping and migration scope:** confirm project title/location fields; decide whether `event_type` is photography type; specify description semantics; decide whether an explicit customer-to-project access relation is required; confirm the currently deployed schema read-only before drafting migrations.
2. **Implement backend project foundation:** map CustomerProject; add request/response schemas and repository/service/router; owner-scoped create/list/detail/edit operations; validate dates/text; make project association writes owner-safe; implement deterministic project order and server-side downgrade editability policy.
3. **Implement quota-safe lifecycle:** enforce Basic/Trial/Pro project limits during creation and edits; serialize concurrent changes; preserve every project on downgrade and reject edits to excess projects; define expiry-trigger behavior and clear API errors.
4. **Integrate photography plans and AI assets:** add owner plan-to-project association with authorization checks; connect plan/generation/assets in the project view without changing AI batch size/cost, generation endpoints, or Normal User behavior. Preserve existing generations and images.
5. **Implement future sharing separately:** add secure owner create/list/deactivate APIs, token hashing and expiry; customer-authenticated view authorization; project/generation/asset ownership consistency; active-link quotas and oldest-three downgrade deactivation.
6. **Build frontend project UI:** owner project list/empty state, create/edit/detail forms, project gallery association, read-only rendering, quota/limit messaging, and navigation; reuse approved AccountLayout/card/theme/gradient patterns. Add link UI only after sharing API contracts are finalized.
7. **Verify and roll out:** isolated backend/database tests, full frontend mocks/build, migration rehearsal/backup and review, then staged deployment. No live database writes should occur during audit or test setup.

## Copilot-safe work versus security-sensitive work

### Suitable for Copilot after API contracts are approved

- Owner project list/detail/form UI, loading/error/empty states, and approved Frameora styles.
- Forms that validate locally for usability but rely on backend validation.
- Typed/service wrappers using finalized project endpoints; mock rendering and frontend tests.
- Display of server-returned project counts, limits and read-only flags.
- Project gallery presentation of server-authorized associated image metadata.

### Security-sensitive backend work for Codex/review

- Database mapping/migrations and ownership/foreign-key relationship decisions.
- Project CRUD authorization, cross-owner isolation, input validation and safe error contracts.
- Atomic quota enforcement, downgrade oldest-first policy, and immutable project/image preservation.
- Project-plan-generation-asset association checks.
- Share-link token generation/hashing, customer authentication/authorization, deactivation, expiry and quotas.
- Any changes to authentication, access-control, concurrency, or private image routes.

Copilot should not invent endpoint contracts or implement frontend-only quota/read-only logic as a substitute for backend enforcement.

## Required tests

### Backend

- Owner-only project create/list/detail/update; anonymous, Normal User, Admin, missing-ID and cross-owner IDOR cases.
- Input bounds and allowed fields; client-forged owner IDs and invalid project associations rejected.
- Basic creates at limit and over limit; Trial/Pro configured limits; paid activation remains unavailable.
- Concurrent project creation at limit never exceeds cap.
- Downgrade/expiry preserves all project rows and media; exactly the oldest two remain editable under Basic; deterministic timestamp ties; edit/delete attempts on excess projects fail.
- Project-to-plan-to-generation-to-asset association persists; cross-owner and mismatched project/generation associations fail.
- Owner gallery lists only authorized project images and download endpoints enforce owner access.
- Sharing: token entropy/hash storage, no raw token/hash leakage, only authenticated authorized customer views, cross-customer/project/generation isolation, owner-only create/deactivate, expiry, duplicate/replay behavior, and private image checks.
- Active link count at quota, concurrent activations, expiry/deactivation count semantics, downgrade preserves oldest three active links and deactivates the rest without deleting rows.
- MySQL migration/constraint/index tests on a disposable instance matching the live schema; no test may default to production credentials.

### Frontend

- Role-gated routes, owner project empty/list/detail/edit/create states, validation and API error handling.
- Server-returned plan limits and counts; limit reached, read-only older projects after downgrade, no destructive UI.
- AI gallery images appear only in the correct project and retain per-image guides/download behavior.
- Future share-link UI enforces no client-side authority, handles authenticated customer access/deactivated/expired links, and displays link limits.
- Existing owner AI generation and Normal User four-image/free-allowance regression tests remain unchanged.
- Production build and theme/accessibility checks.

## Audit boundaries

Findings are from repository source, zero-byte file checks, migration preflight signatures, route registration, and existing tests. No application source was changed; no database was queried or modified; no migration, generation, subscription mutation, or provider call was made. Existing schema descriptions are **not** live-database verification. The planned eight-image owner AI work was not modified or assessed beyond confirming this audit does not change it.
