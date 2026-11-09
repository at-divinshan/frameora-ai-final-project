# Per-image Camera Setup Guide — 2026-11-05

## Files changed for this task

Earlier workflow changes in the working tree were preserved. This task changed:

- `backend/app/services/generation_planning.py`: extends each of the four actual shot specifications with practical camera setup fields and seven numbered steps. Uses the saved angle, lighting, device/lens, and people count; enriches subject positioning.
- `backend/app/schemas/ai.py`: adds the optional `CameraSetupGuide` response contract with 5–7 steps, preserving compatibility with earlier guidance.
- `frontend/src/components/ai/GeneratedImageCard.jsx`: shows the camera guide inside its matching image card, in a keyboard-accessible native disclosure. Keeps the large image and download functionality, and explicitly labels unverified guidance.
- `frontend/src/styles/ai.css`: responsive guide presentation using existing theme tokens, readable numbered steps, independent card heights, and the existing gradient download button.
- `backend/tests/test_ai.py`: verifies specifications, guide fields, approximate suggestions, equipment/light/group adaptations, storage/retrieval with fresh authentication, old metadata compatibility, and malformed legacy preferences using mocks.
- `frontend/tests/ai.test.mjs`: checks complete guide rendering, disclosure, numbered steps, escaped text, and older-image fallback.
- `docs/camera_setup_guide_report.md`: this implementation report.

## Completed behavior and persistence

Every newly generated image has its own pose name, camera angle, approximate distance, shot type, suggested height, direction/tilt, suggested lens or smartphone zoom, lighting direction, subject position, and seven ordered setup steps. Standing, seated, walking, and over-the-shoulder shots have different positions, framing, distances, lighting advice, and capture instructions. Low/high/eye-level/side preferences shape the same specifications used for generation.

The complete guide is part of the shot JSON sent through the existing Pollinations request. The existing generation service saves that exact specification under the corresponding media asset ID in `AIGeneration.guidance_text`. Reads return the saved snapshot rather than regenerating it from the current plan. It is independent of browser state and survives gallery navigation, refresh, and a fresh authenticated session. No migration or real database update was needed or performed.

The configured provider model, reference image request path, four-image count, private download path, authentication/ownership checks, and successful-free-generation accounting are unchanged. No additional API or paid vision integration was introduced. No live Pollinations calls, credit use, dependency updates, secrets exposure, or Git add/commit/push occurred.

## Example generated English guide

The following example is taken directly from the default seated shot specification, without making an image-generation request.

**Pose Name:** Seated portrait

**Camera Angle:** Eye Level · Three-quarter view

**Shot Type:** Medium portrait

**Camera Height:** Suggested height: At the subject's eye level while they are seated.

**Camera Distance:** Approximate starting distance: 1.5–3 metres from the subject; adjust for your lens and framing.

**Camera Direction and Tilt:** From 45 degrees to the subject's front, aim toward the face and keep the camera level.

**Suggested Lens or Smartphone Zoom:** Suggested starting point: 50–85 mm full-frame equivalent on a camera, or 2× optical if available; otherwise 1× and crop later on a smartphone. These are approximate framing suggestions, not measured image settings.

**Lighting Direction:** Suggested direction: Use soft daylight or a window about 45 degrees to the subject's face and slightly above eye level.

**Subject Position:** Sit comfortably, rest the hands on the lap and turn the torso slightly toward the camera; look toward the lens. Keep the saved pose style, outfit and extra preferences.

1. Position yourself 45 degrees to the subject's front. Choose a clear, stable place to stand in the saved location.
2. Hold or mount the camera at the subject's eye level while they are seated. Keep it steady.
3. From 45 degrees to the subject's front, aim toward the face and keep the camera level.
4. Approximate starting distance: 1.5–3 metres from the subject; adjust for your lens and framing. Suggested starting point: 50–85 mm full-frame equivalent on a camera, or 2× optical if available; otherwise 1× and crop later on a smartphone. These are approximate framing suggestions, not measured image settings.
5. Sit comfortably, rest the hands on the lap and turn the torso slightly toward the camera; look toward the lens. Keep the saved pose style, outfit and extra preferences.
6. Frame from the waist or chest upward; leave space above the head and avoid cutting through the hands. Suggested direction: Use soft daylight or a window about 45 degrees to the subject's face and slightly above eye level. Adjust the subject or light if the face is too dark.
7. Focus on the nearest eye, ask the subject to pause briefly and take a few photographs. Review the result and adjust the framing before taking another photograph.

## Test results

- Backend: `PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests/test_ai.py backend/tests/test_photography_plans.py backend/tests/test_suggestions_provider.py backend/tests/test_free_generation.py -q` — **48 passed, 35 subtests passed**. Tests use disposable SQLite/private temporary files and mocked provider/HTTP responses. Existing Starlette/httpx deprecation warning only.
- Frontend, from `frontend`: `node --test tests/ai.test.mjs tests/photography-plans.test.mjs tests/account.test.mjs` — **all 3 test files passed**.
- Production build, from `frontend`: `npm run build` — **passed** with Node.js 22.23.4/npm 10.9.9.
- `git diff --check` — **passed**.

Mocked provider tests compare the complete submitted shot specification, including camera setup steps, with the planned guide for each image. Persistence tests compare returned guidance with those specifications, edit the plan in disposable SQLite, then retrieve the unchanged gallery under fresh authentication. Unauthenticated requests remain rejected. Existing reference upload, image privacy, duplicate protection, provider failure/cleanup, and free-generation tests pass.

## Limitations

- Guides describe generation specifications, not measurements or visual analysis of the returned pixels. Provider results may differ. No perfect visual correspondence is claimed.
- Distances, camera height, lens/zoom, and lighting are practical starting suggestions. Actual framing depends on subject size, group size, sensor/lens, available space, and equipment. The UI labels the approximate recommendations.
- Previously saved images without camera setup metadata retain their original guidance and show an explanatory message; they were not backfilled or modified.
- Browser UI testing could not run: connecting to the existing gallery tab again failed inside the browser connector with `Cannot read properties of undefined (reading 'timeoutMs')`. Automated rendering tests and the build passed, but no live browser visual pass is claimed.

## Manual browser testing steps

Use a disposable account/database with mocked Pollinations responses; do not use the live credit-bearing provider for these checks.

1. Create a plan using an angle preference, lighting preference, and optional equipment. Confirm existing clothing and extra-instruction fields still save/edit normally.
2. Generate the four mocked previews, with and without a reference image. Confirm only one generation submission and four saved cards, with no additional vision request.
3. In My Gallery, open Camera Setup Guide below each image. Check all requested metadata and seven numbered steps. Verify each card differs appropriately for standing, seated, walking, and over-the-shoulder shots and matches that mocked request's specification.
4. Check low/high/side angle plans, smartphone and camera/lens plans, and groups using separate disposable test accounts as required by the one-successful-request rule.
5. Refresh the gallery, navigate away/back, then log out and log back in. Confirm the same guides remain; edit the plan and confirm prior image guides remain unchanged.
6. Download each image. Test a previous image without the new metadata and confirm its old guidance/download still works without an invented detailed guide.
7. Check both themes at desktop and narrow/mobile widths. Expand/collapse with keyboard Enter/Space, confirm visible focus, readable steps, no horizontal overflow, large previews, and the download control below each guide.
