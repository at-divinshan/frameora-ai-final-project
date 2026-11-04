# Day 2: private AI generation integration

## Inspected baseline

The checkout had an authenticated `GET /ai/free-generation/eligibility` endpoint
and the Migration 005 reservation/completion/release/reconciliation service.
`AIGeneration` was mapped; `AIResult`, `MediaAsset`, the provider/service,
generator/results components, and `database/schema.sql` were empty. There was
no implemented gallery data flow or provider credential setting. The Day 1
working changes were retained.

Read-only live MySQL metadata inspection confirmed 17 tables. `AIResult` has
`id` and `generation_id` only. `MediaAsset` has `id`, `user_id`, nullable
`plan_id` and `generation_id`, `asset_type`, `file_url`, and `created_at`.
The added ORM mappings reflect those columns; existing MySQL foreign keys remain
database-managed. No schema changes, migrations, or application-data writes
were performed during development.

## Provider contract and configuration

Source verified November 4, 2026:
https://gen.pollinations.ai/openapi.json

The official image API uses `POST /v1/images/generations` and
`POST /v1/images/edits` (plural). The earlier Hoppscotch `/v1/images/edit`
spelling is not used because the official specification establishes `/edits`.
Both use Bearer authentication, `model`, `prompt`, `n: 1`, and
`response_format: "b64_json"`. Edits accept `image: [{image_url: <data URI>}]`.
The adapter uses that documented JSON format. Four sequential requests use a
shared subject description and reference image with four distinct compositions.
No chat-completion call is necessary for this workflow. No unsupported identity
parameter or face-matching guarantee is introduced.

`backend/.env.example` lists:

- `POLLINATIONS_ENABLED=false` (default; must explicitly enable later)
- `POLLINATIONS_API_KEY` (secret, excluded from settings repr)
- `POLLINATIONS_IMAGE_MODEL=openai/gpt-image-1-mini`
- `POLLINATIONS_TIMEOUT_SECONDS=180` (per image, maximum 300)
- optional `AI_IMAGE_DIR` (absolute private directory)

Process environment takes precedence over `backend/.env`. Existing `.env`
contents were not changed. No key is put in browser configuration, logs, URLs,
source, or response objects. Missing/disabled configuration returns 503 before
reservation. The default model is the official edits default; deployments must
choose an image-input-capable model available to their key.

No real provider generation calls were made. Tests replace the provider HTTP
transport or generation function. Real output quality, model availability for
the user's key, latency, and face consistency remain unverified.

Only connection establishment is retried once. POST read timeouts, provider
errors and ambiguous responses are not retried, avoiding duplicate billed work.
Responses are bounded and decoded/validated, and provider error bodies are
never forwarded. URLs returned instead of base64 are rejected, preventing
server-side URL fetching. Four identical outputs or an incomplete set fail.

Pollinations documents public media cache links even with base64 responses.
Frameora never exposes those links and cannot enforce provider-side retention
or privacy. Reference input goes directly as a data URI, without a public
reference-image upload. The UI explains provider processing/retention.

## Application contract

All routes require authenticated Normal Users:

- `POST /ai/generations`: multipart `plan_id`, `description` (3–2000 characters),
  optional `reference` (JPEG/PNG/WebP; max 5 MiB, nonanimated, max 16 megapixels).
  Returns 201 with generation ID, plan ID, status, timestamp, and four image
  objects containing an ID and authenticated application path. No prompts or
  provider metadata are returned.
- `GET /ai/generations?before=<id>`: owner-scoped history, 20 rows per page.
- `GET /ai/images/{id}`: owner-scoped private PNG bytes; no-store/nosniff.
- Existing read-only eligibility contract is unchanged.

A 6 MiB request-body bound is enforced before multipart parsing, including
chunked requests. Decoding strips image metadata. Reference bytes are not
persisted. Output files use random immutable names, private directories (0700),
private files (0600), fsync, and no symlink following. `MediaAsset.file_url`
stores an opaque local key; no static-file mount serves the directory.

## Allowance and persistence

The existing user-row-first locking and reservation token are reused. No second
allowance ledger, browser limit, or schema field was added. Normal-user plan
ownership is checked by the existing reservation helper before provider work.
The service releases the database transaction before network calls.

Four valid, distinct images are written durably before result persistence. Four
`AIResult` rows and four `MediaAsset` rows link to the single `AIGeneration`.
The status/timestamp, result rows, and allowance consumption commit in one
transaction through `complete_free_request`, after an explicit flush for the
production session's `autoflush=False` behavior.

Known failures before finalization roll back result rows, remove staged files,
and invoke the existing failure-release helper. A lost final commit
acknowledgement retains files and the claim: deleting files or releasing the
allowance could corrupt a committed success. The existing terminal reconciler
runs before another generation attempt. Duplicate successful submissions cannot
consume another allowance or call the provider again.

Process termination or ambiguous finalization may leave a reserved request and
private orphan files. There is deliberately no age-based release. An operator
must establish the old worker/provider work has stopped, inspect the generation
and its assets, and use the existing release/reconcile helpers with the stored
reservation identity as appropriate. Do not mark an incomplete generation
completed or delete files referenced by committed MediaAsset rows. Automatic
cross-process job recovery and orphan collection are not introduced in this
schema-preserving integration.

## Frontend

`/user/ai` and `/user/gallery` use the existing role guard, dashboard layout,
theme variables, and cyan → purple → pink → warm orange buttons. My Plans
links to both pages; navigation and other pages are not redesigned. The gallery
loads authenticated blobs and revokes object URLs on cleanup. It supports
empty, pending, failed, loading, refresh, pagination, image retry, and download
states. No sample image results are included in the application.

## Verification

Mocked provider and disposable SQLite tests cover complete/partial/duplicate
sets, failure release, disabled configuration, active reservation conflicts,
commit acknowledgement loss, ownership, upload limits and malformed uploads,
private serving, and the official provider request/response shape. Existing
allowance tests retain account-lock ordering and idempotent completion checks.
SQLite cannot establish real MySQL cross-worker locking; no live MySQL
concurrency test or provider test was performed.

Verification results: the full unittest discovery run passed 128 tests; after
adding the final request-size and partial-write cases, the affected AI,
allowance, profile-image, and photography-plan modules passed 48 tests. All
three frontend Node test files passed. Vite's production build passed using
`node node_modules/vite/bin/vite.js build` (the host npm launcher reported an
invalid installed npm package configuration). Browser visual QA could not run:
the browser tool failed to create a tab. Temporary mocked preview files were
removed and the owned preview server was stopped.

Deployment remains disabled. Before later enabling, configure the key securely,
verify provider-side privacy is acceptable, ensure private storage is durable
and shared by backend workers, and allow sufficient reverse-proxy request time
for four sequential calls. A hard worker termination retains a reservation for
operator reconciliation; this implementation does not claim a durable job queue.
