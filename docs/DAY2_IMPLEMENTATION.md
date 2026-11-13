# Day 2: project galleries and published revision phases

## Behavior

- Both private galleries now show owned project folders with private cover thumbnails and full image counts. Folder contents retain newest-generation-first ordering, page in batches of 20, and use the existing preview/download components. Unknown, absent, deleted or foreign project relationships are grouped under **Unassigned Images** without disclosing another account's project name.
- Normal Users currently have no independent project-creation system. Their existing images therefore remain Unassigned unless an actual owned project relationship exists; no projects or associations are invented.
- After migration 010, each successfully completed Owner project generation receives the next persistent phase number in the same transaction as its images and success status. The existing owner lock and an additional project lock serialize allocation; unique constraints prevent duplicate generation/phase assignments. Retries return the original phase, failures consume no phase number, and unassigned generations receive no phase.
- Numbers reflect successful completion order, not timestamps. Existing batches are **Legacy batch #ID**. No historical parent/revision relationships or phase numbers are inferred or backfilled. The first new successful project batch after enabling this schema starts Phase 1, even when the project has legacy batches.
- The Owner project workspace shows phases and explicitly publishes a selected phase to an existing active link, after confirmation. Publication is idempotent and records the publisher and time. It does not create another link or bypass existing subscription/project/share limits.
- Existing links retain their original generation grant. Only additional phases explicitly associated with that link become visible. New generations are never automatically published. Link deactivation/expiry applies to every published phase. Customers still need authentication, receive protected previews, cannot download originals, and can comment only on authorized images. Existing feedback status/revised-image workflows remain in place.
- Prior images and phase records remain intact. Feedback's existing revised-image pointer is not treated as an authoritative phase history; immutable generation-phase records provide the batch history.

## Migration dependency — NOT executed

`backend/migrations/010_project_generation_phases.sql` adds only `ProjectGenerationPhase` and `ShareLinkPhase`, their foreign keys and unique constraints. `CREATE TABLE IF NOT EXISTS` permits repeat application when the existing schema matches. It does not repair incompatible pre-existing tables. Existing records are not updated.

Without these tables, galleries and original share links continue working. New generations still work but remain unnumbered legacy batches. Explicit phase publication returns HTTP 503. Apply the migration before generating batches that must have permanent phase history. There is no automatic catch-up/backfill.

### Manual steps (operator only)

1. Back up the intended database and verify the backend's database name/host. Review the SQL and existing `CustomerProject`, `AIGeneration`, `ShareLink` and `User` tables/foreign-key types. Do not substitute a production database accidentally.
2. From the project root, using an authorized database account, run the following **manually** (replace `DB_USER`):

   ```bash
   mysql -u DB_USER -p frameora_db < backend/migrations/010_project_generation_phases.sql
   ```

   Add the appropriate `-h HOST` if the intended database is not local. Password is prompted, not embedded in the command.
3. Verify manually:

   ```sql
   SHOW CREATE TABLE ProjectGenerationPhase;
   SHOW CREATE TABLE ShareLinkPhase;
   ```

   Confirm unique `(project_id, phase_number)`, unique `generation_id`, unique `(share_link_id, phase_id)` and the foreign keys. Do not insert or backfill historical rows.
4. Restart/deploy the backend and built frontend for the code changes. Schema detection is not cached, so the migration itself does not require cache invalidation.

## API changes

- `GET /ai/gallery/folders`: authenticated Normal User/Owner; scoped folder summaries.
- `GET /ai/gallery/folders/{key}?before=ID`: scoped paginated contents; `key` is a real project ID or `unassigned`.
- `PUT /owner/projects/{project_id}/share-links/{link_id}/phases/{phase_id}`: Owner-only explicit publication.
- Generation responses add nullable `phase_id`/`phase_number`.
- Project generation listing accepts `before` pagination.
- Shared gallery responses add `phases` while retaining the existing original `images`/`generation_id` fields for compatibility. Shared preview and comment authorization use the same allowed-generation set.

## Files created

- `backend/migrations/010_project_generation_phases.sql`
- `backend/app/models/project_generation_phase.py`
- `backend/app/services/project_phase_service.py`
- `backend/app/services/gallery_service.py`
- `backend/tests/test_project_phases.py`
- `frontend/src/components/ai/ProjectFolders.jsx`
- `frontend/tests/project-gallery.test.mjs`
- `docs/DAY2_IMPLEMENTATION.md`

## Files modified

- `backend/app/routers/ai.py`
- `backend/app/routers/owner_ai.py`
- `backend/app/routers/sharing.py`
- `backend/app/schemas/ai.py`
- `backend/app/schemas/sharing.py`
- `backend/app/services/ai_service.py`
- `backend/app/services/owner_generation_service.py`
- `backend/app/services/share_service.py`
- `backend/app/services/feedback_service.py`
- `frontend/src/pages/user/AIResults.jsx`
- `frontend/src/pages/owner/AIResults.jsx`
- `frontend/src/pages/shared/SharedGallery.jsx`
- `frontend/src/components/projects/ProjectWorkspace.jsx`
- `frontend/src/services/projectService.js`
- `frontend/src/services/shareService.js`
- `frontend/src/styles/ai.css`

## Manual browser verification

1. Sign in separately as a Normal User and Owner; open each Gallery. Verify folder titles/counts, Unassigned Images, covers, Back navigation, Load more, and existing downloads/previews in both themes/mobile sizing.
2. Open an Owner project and confirm all historical batches remain available as legacy batches. Verify another account cannot read its folder or publish to its links.
3. With mocked generation in a test environment, complete two new project batches and retry the first request. Expect Phase 1/2, the same phase on retry, unchanged originals and no duplicated charge. Failed generation should not allocate a phase.
4. Open an existing link as a signed-in customer: only its original batch is visible. Explicitly publish Phase 2 to that link as Owner. Refresh as customer: the original batch plus Phase 2 appear, but unpublished Phase 1 does not. Verify comments on published images and rejection of unpublished image URLs.
5. Verify protected customer previews versus Owner original downloads, retained feedback, and expired/deactivated link rejection. Repeating publication must not duplicate the phase.

No browser verification or real MySQL concurrency test has been performed. No live AI requests are needed for these isolated checks; any eventual live generation needs separate approval and uses existing credits/batch sizes.

## Verification results

- Final backend run: `test_project_phases.py`, `test_ai.py`, `test_owner_credits.py`: **47 passed, 7 subtests passed**. Isolated SQLite only, providers mocked, production connections guarded.
- Compatibility run: all **42** tests collected from sharing, feedback, feedback-revision and dual-reference suites passed. That run also caught a new publication test returning 409 before ownership validation; validation order was corrected, and all five Day 2 tests passed in the final run above.
- Frontend: `project-gallery.test.mjs`, `customer-projects.test.mjs` (7 tests), `feedback.test.mjs`, `ai.test.mjs`, and `owner-ai.test.mjs` (14 tests) all passed.
- Final `npm run build`: passed. Existing >500 kB chunk advisory remains. Backend dependency deprecation warnings and existing frontend SSR controlled-field warnings are non-blocking.
- The initial sandboxed backend invocation was interrupted because the known TestClient sandbox hang prevented progress; isolated tests completed outside that sandbox.
