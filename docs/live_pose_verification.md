# Live Pose Guide — implementation and verification

Routes: `/user/live-pose`, `/owner/live-pose`. Admin is denied on both API endpoints.
Camera preview, local multi-body detection and photo downloads work without AI.
The manual practice grid is removed. Analyze Scene captures a still for explicit
approval, then shows one real AI recommendation at a time with Next Suggestion.
No AI fallback, mocked user-visible results or manual target selection. Matching
stays neutral until a successful AI analysis supplies supported targets.

## Deployment gates (not performed)

- Review and approve `backend/migrations/006_live_pose_sessions.sql` before applying
  it to an isolated MySQL rehearsal, then separately approve any real database change.
  Existing subscription schema migration 003 is required. No migrations auto-run.
- The configured `openai/gpt-5.4-nano` has documented multimodal image input in
  https://github.com/pollinations/pollinations/blob/main/gen.pollinations.ai/src/docs/apidocs-recipes.md
  (checked 2026-11-10). Actual key/model vision behavior has NOT been tested.
- `LIVE_POSE_VISION_ENABLED=false` by default. Explicitly enable only for approved
  live verification, with existing `POLLINATIONS_ENABLED` and server-only API key.
  Unknown configured chat models fail closed. No provider calls during development.
- Test over HTTPS on Android Chrome and iOS Safari: permissions, front/rear switching,
  orientation changes, full-body tracking, 0.9-second green stability, 3-second photo
  capture/download, background/unmount cleanup, denied permissions and model failure.
  Tune the normalized 2D joint tolerance against real bodies/cameras. No accuracy claim.
- Second-phone mode is independent photography while this phone guides; no pairing,
  synchronized remote shutter or transfer to another device is implemented.

## Multi-person tracking

MediaPipe `numPoses=4`: three scored bodies plus one overflow detection (not identity IDs):
https://developers.google.com/edge/api/mediapipe/js/tasks-vision.poselandmarkeroptions
The lite model runs at at most ~7 FPS, adapting downward for slower inference.
Per-person normalized joint errors and separate 0.9-second holds drive red/green.
Initial association takes 0.6 seconds. Gray means absent/unsupported target,
insufficient visibility, overlap, missing people or uncertain association.
Geometric nearest-assignment retains left-to-right slots across detector-array
reordering; crossings, gaps and large movement reset holds and reacquire slots.
No identity recognition; indistinguishable people exchanging positions between
frames cannot reliably be identified. Keep people in their assigned positions.

Structured vision results include framing, count, and 3–5 suggestions. Each has
one supported template/instruction per person, plus optional group spacing/advice.
No-person and >3-person snapshots are rejected without usage. Unsupported, missing
or duplicate person targets fail validation before accounting. Next Suggestion
uses the existing result and makes no API call. Old result formats fail closed.

Only approximate adjacent hip spacing, normalized by torso length, is evaluated
for groups of similar apparent depth. It is displayed separately from posture;
perspective/occlusion disables group scoring. Composition prose is not scored.
Real-device work must cover solo, pairs, triples, partial bodies, crossings,
foreground/background people, crowded scenes, camera mirroring and thermal/FPS
behavior. Groups over three are unsupported. The local count is capped at four (the fourth disables matching),
so it is not a general crowd counter. Live Pollinations vision still needs approved
account/model testing and scene/person-count accuracy checks.

## Usage semantics

Separate successful-session ledger; image allowances/credits are untouched. One UUID
per approved snapshot; duplicate requests replay the stored result, changed snapshots
with the same UUID conflict. Results persist, photographs do not. A User row lock spans
quota check, bounded provider work and result commit. Failures roll back all usage.
This MVP serializes that user's requests; the lock can delay their other writes.
A crash before commit may require another provider call, but never adds duplicate usage.

Monthly pose limits reset on the first of the month in UTC (independent of image-credit
anniversaries). Usage in that month counts across plan changes; downgrades cannot reset
it. User Free is one lifetime **free** success; Trial counts during its 14-day interval.
Owner Basic is 5/month. Other requested limits are proposed and encoded separately.
Normal-user paid plan activation is not implemented in the existing app; migration 003
currently restricts subscription codes to owner plans. Starter/Plus/Premium mappings
are future-ready policy only, tested with isolated fixtures; enabling user paid plans
needs its own approved subscription schema/product work. Paid checkout stays disabled.

## Assets

MediaPipe Tasks Vision 0.10.32, Apache-2.0, from npm. WASM is copied into
`frontend/public/mediapipe/wasm`; the pose model is Google's version 1 lite float16:
https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
Frames are processed locally. Static model/WASM assets are served by Frameora.


## Final camera experience

The main screen is camera-first: Analyze, Capture (3s), Flip, Hide Guidance and
optional next pose. Plan/camera details are collapsed. There are no skeletons,
manual pose cards, technical counters or recommendation panels in the camera UI.

Target human shapes are geometric illustrations generated from the exact supported
pose joints, with approximate body proportions. They are not segmented people or
AI-generated pixels. Automatic layout uses the valid recommendation's group size
and spacing class; it is not a precise scene-depth reconstruction. Position and
apparent torso scale are now scored as well as posture. Very wide groups that
cannot fit at a reliable size request landscape orientation instead of showing
unmatchable targets. Front-facing standing templates remain the supported scope.

`outputSegmentationMasks=true` enables REAL per-pose masks in the existing model.
Contour pixels come from mask boundaries (neutral/red/green); a union of masks
composites sharp people over a subtly blurred frozen inference frame. No mask,
invalid masks or unsupported Canvas filter means no fake blur/outline fallback.
Masks are consumed within the MediaPipe callback, without retaining resources.
Mask edges are downsampled for mobile performance; hair, fingers, overlaps and
occlusions will be approximate. Preview blur updates at the inference rate and
can lag or look less fluid than raw video; users can turn it off. Pose detection
can miss people and cannot protect unrecognized people from background blur.

Video and overlay share object-fit:contain and one mirroring transform. Target
text uses the same contain rectangle. Aspect changes clear association history.
Hide Guidance clears all visual effects immediately. Downloads always use raw
video pixels, without target shapes, labels, contours or preview blur.

Verified by pure rendering/geometry tests and component SSR checks; no physical
camera, actual model segmentation quality, mobile Canvas performance or live AI
was verified. Test front/rear cameras and rotation on Android/iOS, fast movement,
three people, loose clothing, hair boundaries, capture timing and hidden guidance
before enabling this experience for production. Migration and live vision gates
above remain unchanged.
