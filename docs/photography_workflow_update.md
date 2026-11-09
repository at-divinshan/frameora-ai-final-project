# Photography workflow update — 2026-11-05

## Implemented behavior

- Preserved the existing photography type, people count, environment, location, shoot date/time, style, lighting, pose, camera angle, outfit color, and equipment fields.
- Added optional Clothing Style, Outfit Details, and multiline Extra Instructions to the shared create/edit form, validation, saved preferences, and plan cards.
- AI Suggestions and image generation share the saved plan context. Generation loads the authenticated user's plan on the backend, includes the optional additional description, and keeps internal prompts out of API responses/UI.
- Each plan card links to `/user/ai?plan=<id>`. The generator preselects that plan and displays saved details; direct access still supports manual selection and the existing reference photo upload.
- Generation uses four explicit shot specifications (pose, camera angle, shot type, camera position, instructions). The same specifications are sent to Pollinations and saved by media asset ID for gallery display. Camera height and side-view variations follow the saved angle preference.
- Four responsive skeleton cards, shimmer, spinner, accessible status text, and reduced-motion support replace plain generation text. Existing theme tokens and gradient buttons are retained. A synchronous submission guard supplements the existing server allowance protection.
- Gallery cards retain image loading, retry, and downloads, and now show saved guidance. Guidance is explicitly described as planned, not visually verified. Older results remain readable and show a missing-guidance message rather than invented guidance.

## Storage and safety

No migration is needed: plan additions use `PhotographyPlan.preferences`; versioned per-image guidance uses the existing `AIGeneration.guidance_text` column and is committed with images and allowance completion. No schema or real data was changed during implementation/testing. Existing results were not backfilled.

The configured Pollinations model and generation/edit endpoints are unchanged. No live Pollinations calls, credit use, dependency changes, secret changes, Git configuration changes, staging, commits, or pushes were performed. The existing authentication, role restrictions, ownership checks, image storage, and one-successful-free-request lifecycle remain in place.

## Files changed

Backend implementation:
- `backend/app/schemas/photography_plan.py` — optional preference validation, including multiline text.
- `backend/app/services/photography_suggestions.py` — shared saved-plan context and new fields.
- `backend/app/services/generation_planning.py` (new) — internal prompt and four shot specifications.
- `backend/app/routers/ai.py` — additional description is optional; existing maximum remains compatible.
- `backend/app/schemas/ai.py` — optional structured image guidance response.
- `backend/app/services/ai_service.py` — owned plan lookup, prompt construction, atomic guidance persistence and legacy-safe reads.
- `backend/app/services/pollinations_service.py` — use the supplied shot specifications for all four requests.

Frontend implementation:
- `frontend/src/components/photography/PlanForm.jsx` — create/edit fields and mapping.
- `frontend/src/components/photography/PlanCard.jsx` — saved preference display and Generate Images link.
- `frontend/src/pages/user/AIGenerator.jsx` — preselection, saved-plan summary, optional short description and duplicate-submit guard.
- `frontend/src/services/aiService.js` — default omitted description to empty text.
- `frontend/src/components/ai/GenerationLoader.jsx` — four skeleton cards and status.
- `frontend/src/components/ai/GeneratedImageCard.jsx` — per-image guidance and legacy fallback.
- `frontend/src/styles/ai.css` — responsive guidance/loading styles and reduced motion.
- `frontend/src/styles/dashboard.css` — textarea and multiline preference presentation.

Tests and documentation:
- `backend/tests/test_ai.py`
- `backend/tests/test_photography_plans.py`
- `frontend/tests/ai.test.mjs`
- `frontend/tests/photography-plans.test.mjs`
- `docs/photography_workflow_update.md` (this report)

## Verification

Passed:
- `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_ai.py backend/tests/test_photography_plans.py backend/tests/test_suggestions_provider.py backend/tests/test_free_generation.py -q`: **46 tests and 35 subtests passed**. Existing Starlette/httpx deprecation warning only. Tests used disposable SQLite/private temporary files, production database connection guards, and mocked HTTP/provider responses. The sandboxed attempt stalled; the permitted run outside the sandbox completed successfully.
- From `frontend`: `node --test tests/ai.test.mjs tests/photography-plans.test.mjs tests/account.test.mjs`: **3 test files passed**. Includes field round trips/rendering, plan link, optional description, four skeletons, guidance/legacy cards, API behavior, and account regression checks.
- From `frontend`: `npm run build`: **passed**, using Node.js 22.23.4/npm 10.9.9.
- `git diff --check`: **passed**.

Backend tests cover saved-plan prompt fields, omitted/additional descriptions, preference create/read/edit/clear, invalid values, all camera preference variants, provider specifications matching saved guidance, gallery refresh after plan edits, legacy guidance, four distinct results, reference-photo handling, private retrieval, authorization, failure cleanup, duplicate prevention, and allowance consumption/recovery.

## Browser checks and limitations

Manual browser checks were attempted but could not execute: both opening a preview tab and binding the existing Frameora tab failed inside the browser connector with `Cannot read properties of undefined (reading 'timeoutMs')`. No browser-based verification or visual verification of generated images is claimed.

Remaining manual checks should use a disposable account/database and mocked Pollinations responses:
1. Create and edit a plan with all three new optional fields, including multiline instructions; confirm values survive refresh.
2. Open Generate Images from a plan card; confirm preselection and saved detail summary. Open the generator directly and select a different plan.
3. Submit without an additional description, with a description, and with a reference photo. Confirm one generation request and four loading cards on desktop/mobile in both themes.
4. Confirm the four saved gallery cards show their corresponding specification, download correctly, and retain guidance after refresh and later plan edits.
5. Check older gallery images, failed generation retry, and the used allowance state.

Actual provider output quality and adherence to all free-text preferences remain unverified because live generation was intentionally not performed. Shot guidance describes requested specifications, not analysis of output pixels. No additional subscription or background-only workflow was introduced.
