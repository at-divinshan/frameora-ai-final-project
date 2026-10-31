# Steps 40–41 implementation and verification

## Admin APIs (GET only)

All use existing JWT/database `require_roles('admin')`, including the unchanged
single-admin policy. No grants, approval, account edits, deletions or payment actions.
- `/admin/summary`: actual counts for role user and owner.
- `/admin/owners`: q (max 100 characters), onboarding status, page (1–10000),
  page_size (1–50, default 20). Literal escaped search on name/email/studio/city;
  deterministic created_at DESC, id DESC ordering. Unknown query fields rejected.
- `/admin/owners/{id}`: safe account/studio fields, optional photo availability,
  shared effective subscription snapshot and credits. Unapplied 003 -> unavailable,
  not zero or fake subscription. Missing profiles -> pending_studio, no row created.
- `/admin/owners/{id}/photo`: authorized private PNG from existing storage; no-store,
  nosniff; no raw filename or arbitrary path accepted. Unapplied 004 -> controlled 503.

Owner list uses allowlisted account columns and Pydantic response schemas. Private
studio fields are returned only to Admin or existing owner self APIs. Public privacy
responses are unchanged. Subscription inspection calls existing read-only snapshot;
no new entitlement rules, background jobs or database changes are introduced.

UI reuses AdminLayout, existing tables, theme variables and gradient buttons. Search,
filter, pagination, loading/errors/retry/empty state and detail panel are implemented.
Studio details and subscription/photo information are loaded on explicit View details.
Unsupported account management actions remain absent/disabled.

## Landing asset and content

Used `/images/landing/hero-dark.png`, physical path:
`frontend/public/images/landing/hero-dark.png` (existing clean local mountain sunset).
Inspected `/home/uki-jaffna/Documents/landing page hero bg img change.png`: this is a
flattened full-page reference with old text, logo, navigation and buttons baked in.
It was not copied or rendered as a background to avoid duplicate/incorrect text and
logo. If that exact scene is required instead, provide its text-free background export
as `frontend/public/images/landing/hero-approved.png` for a separately reviewed swap.
No replacement image was downloaded, generated or edited.

Exact hero strings:
- AI POWERED PHOTOGRAPHY PLATFORM
- Create Beautiful Moments with AI
- From shoot planning to pose ideas and AI-generated visuals, Frameora AI helps you capture every moment better.
- Get Started
- Login

Hero links are /register and /login; existing PublicAuthRoute redirects authenticated
visitors to their role dashboard. Landing title is Frameora AI. Other public-page title
behavior is unchanged. Existing overlays support light/dark contrast; logo, navbar,
footer and responsive CSS remain. Planned AI tools are explicitly labelled planned.

## Files changed this sprint

Created:
- backend/app/schemas/admin.py
- backend/app/services/admin_service.py
- backend/tests/test_admin.py
- docs/steps_40_41_verification.md

Modified:
- frontend/src/services/adminService.js (previously empty)
- backend/app/routers/admin.py (previously empty)
- backend/app/main.py (register Admin router)
- frontend/src/pages/admin/Dashboard.jsx
- frontend/src/components/layout/AdminLayout.jsx
- frontend/src/pages/public/Landing.jsx
- frontend/src/components/public/PublicSections.jsx
- frontend/src/styles/account.css
- frontend/tests/account.test.mjs

Pre-existing uncommitted Steps 34–39 changes are retained. Migrations 003/004 and
password/auth-version flags are untouched. No packages, commits or live DB access.

## Manual checks (not executed)

Use isolated backend/fixtures only for test accounts. No real account modifications.
1. Sign in as Admin; open /admin/dashboard. Compare counts with isolated fixtures.
2. Search name/email/studio/city; filter each onboarding status. Page forward/back;
   test zero results. No-profile owners show pending studio.
3. Open owner details: name/email/date, studio fields, subscription state, credits,
   private photo. Missing migrations show unavailable without breaking the list.
4. With isolated approved schema, view Basic and expired Trial entitlement snapshots.
   Verify visits create no subscription/grant/profile records.
5. As anonymous/User/Owner, request all /admin paths: 401/403. Target non-owner IDs
   as Admin: 404. Verify no UI mutation buttons or secret fields appear.
6. Landing: check all five exact strings, title Frameora AI, local background and
   original logo. Get Started -> registration; Login -> login; signed-in visitors
   follow existing dashboard redirects.
7. Check desktop and 375px width, keyboard navigation, light/dark contrast, loading,
   network errors/retries, and protected photo refresh. Inspect public navigation
   and existing owner studio/subscription/dashboard/profile flows.

Real MySQL concurrency, migrations and browser visual verification remain untested.

## Executed results

- Backend: `.venv/bin/python -B -m unittest discover -s tests -p 'test_admin.py' -v`
  initially passed 7 tests; one photo test was then added and included in the full run.
- Backend: `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`
  **89 passed, 0 failed**, including 8 Admin tests and all prior owner/auth regressions.
  Tests used disposable SQLite and private temporary Redis/storage, production engine blocked.
- Frontend: `node tests/account.test.mjs`: **36 passed, 0 failed** (SSR, mocked Axios,
  pure validation/redirect tests; not an interactive browser test).
- Frontend: `npm run build`: **PASS**, Vite 6.4.5, 1708 modules.
- Root: `git diff --check`: **PASS**.

An initial frontend run caught a malformed option closing tag; corrected before the
successful final tests/build. Existing dependency deprecation warnings remain; no
packages installed or changed. No browser visual, live MySQL or real Google flow tests ran.
