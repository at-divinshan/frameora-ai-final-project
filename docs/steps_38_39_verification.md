# Steps 38–39 review and manual verification

No live MySQL connection, migration execution, account changes or environment activation
was performed. Existing working-tree changes were retained; migration 003 was not edited.

## Review findings

- Fixed: completed owners were redirected away from Subscription Selection, preventing
  Basic owners from explicitly starting unused trials. Sidebar subscription link was disabled.
- Fixed: guard state was keyed only by user, so route navigation did not revalidate onboarding.
  Unknown status previously threw during render; it now becomes a controlled retry state.
- Fixed: subscription schema inspection dereferenced SQLAlchemy FK target columns for the
  unmapped AIGeneration table. It now compares declared target names without requiring an
  unrelated ORM mapping. Schema/column/unique/FK checks still gate subscription access.
- Preserved: owner JWT scoping, strict studio allowlist, parent User locks, no-row GET,
  server UTC dates, anniversary clamp without drift, explicit one-time trial, no paid route,
  migration-unavailable 503s, read-only effective fallback on GET and atomic grants on POST.
- Blocked: actual migration 003/004 rehearsal, InnoDB concurrent requests/deadlocks and live
  Google/MySQL behavior have not been verified. SQLite tests do not prove InnoDB locking.
- Idempotency keys persist across retries in the mounted UI, not browser restarts. Backend
  uniqueness prevents repeated lifetime trials; repeating Basic cannot reset its anchor.
- Future spending and project/share enforcement remain outside this sprint. Counts display
  unavailable; the dashboard does not claim downgrade enforcement for future endpoints.

## Manual browser checks (NOT executed here)

Use an isolated deployment, disposable owners and private test storage. Rehearse/apply
003 and 004 there only after separate approval; never use live accounts for write checks.
1. With migrations absent, sign in as a disposable owner without a profile. Confirm setup
   opens with no dashboard flash, photo upload unavailable, and no records created by GET.
2. Check blank/invalid fields. Submit valid details with 0771234567, then +94771234567.
   Confirm subscription page opens and shows controlled 503/retry while 003 is absent.
3. After isolated approval/application of 004, choose JPEG/PNG/WebP: preview, upload,
   replace and remove. Check SVG, malformed bytes, animated images and >5 MiB are rejected.
   Reload and confirm persistence. Edit details and verify the existing image remains.
4. With isolated migration 003 applied and verified catalogue, confirm three real cards,
   current-plan label, and disabled Pro. Visit/reload without clicking: no activation.
5. Choose Basic once; double-click/retry with same key. Verify one subscription/grant,
   completed onboarding and dashboard with actual studio and 10-credit allowance.
6. Revisit Subscription from sidebar; explicitly start unused Trial. Verify 100 total
   credits and 14-day expiry. Retry same request; attempt another key -> no second trial.
7. Use isolated service clock tests for expiry; never change production clocks/rows.
   Verify exact-expiry Basic anchor, no carryover, and end-of-month anniversary behavior.
8. Verify dashboard photo/details, current credits/period/limits; counts unavailable.
   Confirm project creation/payment are disabled and no sample data appears.
9. User/Admin/anonymous cannot reach owner pages/APIs; another owner's token cannot
   fetch or replace this owner's photo. Query/body owner IDs are rejected.
10. Check light/dark themes, mobile width 375px and desktop; keyboard labels/focus,
    loading/errors/retry states; refresh/back navigation; existing login/Google/logout,
    profile/settings and public pages. Visual/browser checks require manual execution.

Automated checks use disposable SQLite, temporary files and mocked frontend requests;
existing security tests additionally use isolated Redis sockets and locally signed JWTs.
Production build verifies compilation, not visual fidelity or real browser interaction.

## Executed checks

From `backend` (production engine blocked by fixtures):
- `.venv/bin/python -B -m unittest discover -s tests -p test_owner_subscriptions.py -v`: initial 7/7 passed.
- `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`: 80/80 passed.
- `.venv/bin/python -B -m unittest discover -s tests -p test_studio_photo.py -v`: 6/6 passed after adding the final decoded-limit/path-reference test.
  Five overlap with the full run: 81 distinct backend tests passed across these final runs.
  The initial sandboxed TestClient attempt stalled; completed runs used approved execution
  outside that sandbox with the same isolated fixtures. No live MySQL tests ran.
From `frontend`:
- `node tests/account.test.mjs`: 32/32 passed (SSR, pure state decisions and mocked Axios).
- `npm run build`: passed, Vite 6.4.5, 1707 modules.
From project root: `git diff --check`: passed.
No failures remain in completed runs. Dependency deprecation warnings remain; no packages changed.

## Files changed in Steps 38–39 (earlier working-tree changes retained)

Created:
- backend/app/services/studio_photo_service.py
- backend/migrations/004_studio_photo.sql
- backend/tests/test_studio_photo.py
- frontend/src/components/common/StudioPhoto.jsx
- frontend/src/utils/subscription.js
- docs/004_studio_photo_review.md
- docs/steps_38_39_verification.md

Modified (some already untracked/modified when this sprint began):
- backend/app/models/profile.py
- backend/app/routers/owner.py
- backend/app/services/profile_image_storage.py
- backend/app/services/subscription_service.py
- backend/tests/test_owner_subscriptions.py
- frontend/src/components/layout/OwnerLayout.jsx
- frontend/src/pages/owner/Dashboard.jsx
- frontend/src/pages/owner/StudioSetup.jsx
- frontend/src/pages/owner/Subscription.jsx
- frontend/src/routes/OwnerOnboardingRoute.jsx
- frontend/src/services/ownerService.js
- frontend/src/utils/onboarding.js
- frontend/src/styles/account.css
- frontend/tests/account.test.mjs
- docs/api-documentation.md
