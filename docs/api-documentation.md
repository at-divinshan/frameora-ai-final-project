# Frameora authentication API

## Status and scope

Google authentication is disabled by default. The existing `/auth/register`,
`/auth/login`, `/auth/me`, Frameora JWT contract and database role checks remain.
The existing React authentication UI now integrates the Google endpoints. No additional database schema is included. The previously
approved User migration must already exist; do not rerun it.

Google requires `Authlib`, `httpx`, `redis`, and `PyJWT[crypto]` from
`backend/requirements.txt`. Dependencies have not been installed and runtime tests
have not been executed as part of this implementation.

## Backend configuration

Configure privately through backend environment variables or the untracked
`backend/.env`. OS environment variables take precedence. Never send secrets in
chat, URLs, frontend configuration, or logs.

| Variable | Purpose |
| --- | --- |
| `GOOGLE_AUTH_ENABLED` | `false` by default; explicitly set `true` to enable |
| `GOOGLE_CLIENT_ID` | Google Web application client ID |
| `GOOGLE_CLIENT_SECRET` | Backend-only Google client secret |
| `GOOGLE_REDIRECT_URI` | Exact registered API URL ending `/auth/google/callback` |
| `FRONTEND_ORIGIN` | Exact allowed browser origin, without trailing slash/path |
| `GOOGLE_COMPLETION_URL` | Fixed completion page under that frontend origin; no query/fragment |
| `REDIS_URL` | Private Redis URL, including ACL credentials where required |
| `OAUTH_TRANSACTION_KEY` | Separate Fernet encryption key shared by all workers |
| `OAUTH_COOKIE_SECURE` | `true` by default; `false` permitted only for loopback development |

Existing DB and JWT settings remain required. Keep the existing JWT secret.
Missing Google settings or dependencies fail closed on Google endpoints without
preventing existing password authentication. Redis connection is lazy and has
bounded timeouts. Google and Redis must be configured before enabling the feature.

For local development, use `localhost` consistently for frontend and API (or
`127.0.0.1` consistently), and explicitly set `OAUTH_COOKIE_SECURE=false` if using
HTTP. In production use HTTPS, Secure cookies, and a same-site frontend/API
arrangement. Cross-site frontend/API deployments are not supported by the current
SameSite=Lax cookie contract. The frontend completion page is `/auth/google/callback`. Configure the completion URL to that page.

Create the transaction key privately with `cryptography.fernet.Fernet.generate_key()`
and store it through the backend secret configuration mechanism. Do not reuse the
JWT signing secret. Rotating this key invalidates outstanding Google transactions,
not existing Frameora sessions.

## Redis requirements

Use a private shared Redis 6+ endpoint, TLS (`rediss://`) for remote endpoints,
and an ACL user restricted to `frameora:oauth:*` keys. The client requires SET,
GET, DEL, INCR, EXPIRE and EVAL permissions (and client connection/handshake
commands appropriate to the chosen Redis client/server). No FLUSH, CONFIG or
administrative permissions are required. Do not expose Redis publicly.

Authorization records expire after 300 seconds, pending registration after 600
seconds, and callback completion after 60 seconds. Linking also has an absolute
300-second reauthentication deadline. Transaction payloads are Fernet encrypted;
keys and browser bindings use SHA-256 digests. Lua atomically checks browser
binding/purpose before consuming a record. There is no in-memory fallback.

Rate limits: 30 start attempts per peer IP per minute; five link reauthentication
attempts per account per five minutes. Restrict trusted reverse proxies so peer
addresses cannot be spoofed. Shared NAT/proxy addresses can share a limit.

Use a dedicated Redis database/instance with suitable capacity and preferably
`noeviction`. A missing/evicted record forces a restart. Avoid restoring old OAuth
state from snapshots: rotate the transaction key following disaster recovery.
Use a primary with appropriate durability/failover guarantees; asynchronous Redis
failover can lose recent consumes. Never treat Redis failover as a substitute for
MySQL uniqueness and guarded linking updates.

## Browser protocol

All POST endpoints require `Origin: <FRONTEND_ORIGIN>` and
`Content-Type: application/json`, plus `credentials: "include"` in browser fetch.
Only the configured origin is accepted for OAuth POSTs. Host-only HttpOnly cookies
bind the flow; production cookie names have the `__Host-` prefix. Only one Google
flow per browser cookie jar is supported: starting another replaces its binding.

### Sign-in and registration

1. `POST /auth/google/start` with `{"remember_me": false}`.
   Returns `{"authorization_url": "..."}` and sets the binding cookie.
2. Navigate the same browser to that URL. Google redirects to the registered
   `GET /auth/google/callback` with its authorization response.
3. The API consumes state, exchanges the code with PKCE, verifies the Google ID
   token, and redirects to the fixed completion URL. No Frameora or Google token
   is included in that redirect. A one-minute completion cookie is set.
4. From the completion page, `POST /auth/google/complete` with `{}`:
   - Linked public account: existing `TokenResponse` (`access_token`, `token_type`,
     `expires_in`, `user`). Keep tokens out of logs and URLs.
   - New identity: `{"status": "registration_required"}` and a ten-minute
     registration cookie. No User has been created.
5. For a new identity, collect name, role and explicit terms acceptance, then
   `POST /auth/google/register` with
   `{"name":"Your Name","role":"owner","accept_terms":true}`.
   `role` must be `user` (Normal User) or `owner` (Studio Owner). The account is
   inserted once with that role, NULL password and the verified Google subject.
   Returns the existing `TokenResponse`. There is no role conversion step.

Email collisions never authenticate, merge, or create a duplicate account. They
return a conflict directing the user to existing-account login and explicit
linking. Linked Google login resolves by verified subject, even if Google's email
changes; it does not overwrite the stored account email or role. The general
`is_verified` field is not repurposed or silently changed.

### Explicit linking

1. Log in normally and retain the existing Frameora bearer token in the client.
2. `POST /auth/google/link/start`, including `Authorization: Bearer ...`, with
   `{"password":"<current password>","consent":true}`. Never log the body.
   This verifies the password freshly and returns an authorization URL.
3. Navigate through Google in the same browser. The callback sets a short-lived
   link-completion cookie and redirects to the fixed completion URL.
4. `POST /auth/google/link/complete` with the SAME bearer token and
   `{"consent":true}`. Returns `{"status":"linked"}`.

The link is bound to account ID, bearer session, browser and unchanged password.
The final account is reloaded under a row lock; the update requires a public role
and an empty Google identity. Existing links cannot be replaced. An identity
already owned elsewhere is rejected. Admin registration, login and linking through
Google are all forbidden. Admin password login and its exactly-one-Admin check
remain unchanged. Google-only accounts do not use the password-linking flow.

Linking and registration are single-use: if a database commit succeeds but its
response is lost, restart sign-in. Do not retry a consumed transaction. Unlinking,
Google identity replacement, and password setup/recovery are outside this phase.

## Token verification and logging

Google identity verification uses fixed Google authorization/token/JWKS endpoints,
RS256 only, signature validation, issuer, audience, expiry, issued-at, nonce,
authorized-party checks, verified email, subject bounds, and access-token hash
verification when present. Google tokens are discarded after validation. Frameora
HS256 JWT verification is separate. The JWKS is fetched for each exchange to
handle rotation without maintaining a stale key cache; provider outage fails closed.

All Google responses have no-store and no-referrer headers. The application filters
Google routes out of Uvicorn access logging and sanitizes unexpected Google-route
failures. Reverse proxies, load balancers, APM/tracing, alternate ASGI servers,
and request-body logging must ALSO exclude OAuth query strings, headers, cookies
and bodies. Configure this before enabling Google. Do not enable HTTP wire/debug
logging. The provider code necessarily reaches the callback URL; it must not be
recorded in infrastructure logs. Do not record authorization URLs or token responses.

## Manual validation (not executed)

Use a development environment and accounts you authorize for testing. Registration
and linking tests intentionally create/update records; they are not inspection-only.

From the project root, the manual dependency installation command is:

```bash
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

After privately configuring the environment, the manual local API command is:

```bash
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

Neither command has been executed. Keep Google disabled for the initial regression
checks. Use the existing frontend origin in a browser for subsequent requests.
For backend-only exploration, browser developer tools can issue the documented
POST requests without changing frontend source. For example, on the configured
local frontend origin, start a flow with:

```javascript
void (async () => {
  const response = await fetch("http://localhost:8000/auth/google/start", {
    method: "POST", credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ remember_me: false }),
  });
  if (!response.ok) throw new Error("Google start failed: " + response.status);
  const result = await response.json();
  window.location.assign(result.authorization_url);
})();
```

After returning to the frontend (its current catch-all may send you to `/login`),
issue `/auth/google/complete` with the same fetch options and body `{}`. For new
users, issue `/auth/google/register` using the documented name/role/terms body.
Inspect status codes privately; do not print successful token responses to the
console. The implemented frontend completion page handles these POSTs automatically; developer tools are optional for diagnosis.

1. Install reviewed requirements in the backend virtual environment manually.
   Provision Redis privately, generate its transaction encryption key, configure a
   Google Web OAuth client and exact callback URI, and add permitted Google test
   accounts. Do not rerun the database migration.
2. With `GOOGLE_AUTH_ENABLED=false`, manually launch the API. Verify Google start
   returns 503 while existing password login, registration and `/auth/me` work.
3. Configure the Google variables and Redis and enable Google; restart manually.
   A browser harness or developer tools on the configured origin is needed. The
   existing Login/Register buttons and completion page now provide the flow. Use a browser fetch from that origin for the
   POSTs described above; navigating to the authorization URL must use the same
   browser cookie jar. Never paste tokens/codes into shared tools or logs.
4. Complete new registration separately with `user` and `owner`. Before the final
   registration POST, confirm no User was inserted. Afterwards confirm the chosen
   role, NULL password, non-NULL subject and unchanged 16-table count.
5. Try missing/false terms, missing/invalid role and `admin`: expect 422 and no
   account. Confirm a blank/invalid name is rejected.
6. Sign in again with each linked identity. Verify the same User ID/role and the
   normal JWT response; call `/auth/me` with that token. Verify no duplicate account.
7. Try Google sign-in whose email matches an unlinked manual account: expect 409,
   no session and no database change. Use password login and the explicit linking
   sequence; verify original ID, email, role and password hash are unchanged.
8. Try wrong password, missing/false consent, different bearer token, another
   browser, expired reauthentication, existing link, or identity owned elsewhere:
   expect rejection. Verify that no link was overwritten. Admin linking must fail.
9. Confirm existing Admin password login still works under the single-Admin policy.
   Do not create another Admin or modify live Admin data to test this. A dedicated
   isolated fixture is needed later for non-single-Admin and prelinked-Admin cases.
10. Try password login against a Google-only account: expect the same generic 401
    as other invalid credentials, with no exception or invented password.
11. Cancel Google consent; omit/change state; replay the callback; replay completion
    or registration; omit browser cookies; use a wrong Origin: all must fail safely.
    Let each transaction expire and confirm a fresh start is required.
12. Stop Redis manually in development. Google start/completion must fail closed;
    password login must continue. Restarting Redis must not enable reuse of consumed
    transactions. Exercise rate limits and verify 429 responses.
13. Inspect developer tools privately: HttpOnly/Secure/SameSite cookies, credentials
    CORS, no-store responses, no tokens in redirects. Inspect infrastructure logs
    for absence of sensitive OAuth data without copying secret values into reports.
14. Concurrent signup/link completion and forged signature/audience/issuer/nonce/
    email-verification cases require a controlled integration harness or later
    automated tests. Do not attempt to alter signed real Google claims and expect
    a successful exchange. These cases remain unverified until such tests run.

Dashboard routes, artwork, themes, gradients and logos remain unchanged. Google controls reuse the existing authentication layout and theme tokens.


## Integrated frontend flow and manual checks

Configuration: `VITE_API_URL` must point to the API; `FRONTEND_ORIGIN` must equal the
browser origin exactly; `GOOGLE_COMPLETION_URL` must be that origin followed by
`/auth/google/callback`. `GOOGLE_REDIRECT_URI` remains the BACKEND callback. Google
Client Secret, Redis URL and transaction encryption key never belong in Vite.
Enable Google only after the documented backend dependencies/configuration and
Redis are ready. Start services manually; no live Google flow has been run here.

1. Open `/login`, select Remember me if desired, and click **Continue with Google**.
   Verify Google Account Chooser appears, with its callback directed to the API.
2. For an existing linked public account, finish Google authorization. Verify
   `/auth/google/callback` completes automatically and redirects to the existing
   `/user/dashboard` or `/owner/dashboard` according to the backend role.
   Reload and verify `/auth/me` restores the session. With Remember me off, use
   session storage; with it on, use local storage as for password login.
3. Open `/register` and click **Continue with Google** with a new identity. Verify
   the completion form requires a name, explicit Normal User/Studio Owner selection
   (no default selection), and unchecked terms acceptance. Submit each role in
   separate authorized development accounts. Verify direct creation with that role.
   No email/password is requested for the Google-only account.
4. Use the Login page's **Link Google to an existing account** link, or visit
   `/auth/google/link`. Sign in with the existing account's password if necessary.
   Enter its current password again, explicitly consent, and choose a Google
   account. On return, check the account shown and explicitly confirm the link.
   Verify the original ID/email/role/password remain intact and both login methods
   work. Admins are redirected to their password-authenticated dashboard.
5. Try an existing-email/unlinked Google identity. Verify the conflict message offers
   explicit linking and no account merge/login occurs. Try already linked identities
   and ensure links cannot be replaced. Wrong linking passwords must not silently
   log the user out; an actually expired session requires signing in again.
6. Cancel at Google, expire a transaction, refresh the completion page, and use the
   browser Back button. Verify safe restart messages, no repeated single-use POST
   from React StrictMode, and usable start controls after returning with Back.
   A pending registration can survive refresh within its backend lifetime.
7. Verify missing/false terms, invalid roles and attempts to use Admin registration
   are rejected. Confirm existing password login/registration/logout, protected
   routes, Admin login and role redirects still work.
8. Disable Google or stop Redis in development: Google displays an unavailable
   message while password login remains usable. Inspect light/dark desktop and
   mobile layouts, keyboard focus, checkbox labels, busy states and errors.
9. Confirm requests use credentials only for Google endpoints, JWTs stay in the
   existing session mechanism, and no OAuth code/ID token/Google access token is
   stored by frontend code or forwarded in frontend URLs. Production still needs
   the documented proxy/APM log exclusions. OAuth provider codes necessarily reach
   the registered backend callback, never the frontend callback.

The frontend stores only mode, Remember me preference, account ID for linking,
phase and local expiry in session storage. This metadata is NOT authorization;
backend cookies, Redis, bearer session, consent, password proof and uniqueness
constraints remain authoritative. Callback completion is deduplicated in memory
only to avoid React StrictMode consuming backend transactions twice; Redis remains
the actual security store. Logout clears navigation metadata.

Callback errors now redirect to the fixed frontend completion URL using only one
of three fixed fragments: `#google-cancelled`, `#google-conflict`, `#google-error`.
The frontend immediately removes these markers and shows fixed messages. It never
renders provider error descriptions or extracts tokens/codes from the URL. A
configuration failure before entering the backend callback may still return a
sanitized API error because there may be no valid frontend destination configured.

## Day 4 Stage 2: privacy settings

`GET /users/me/privacy` and `PATCH /users/me/privacy` require the existing Bearer
JWT. The target account is always loaded from the authenticated identity. PATCH
accepts one or more of these keys, each strictly `"private"` or `"public"`:

```json
{
  "profile_visibility": "private",
  "photography_plans_default": "private",
  "ai_images_default": "private"
}
```

All defaults are private. Missing/null/malformed stored values are interpreted
as private without writing during GET. PATCH rejects null values, empty objects,
unknown keys and protected fields with 422. Unspecified keys retain their
effective values. The service locks/reloads the authenticated row and replaces
the existing `User.privacy_preferences` JSON value in one transaction; no schema
change is required. Admin profile visibility is always private, regardless of
stored JSON, and attempts to set it public return 403.

`GET /users/{user_id}/public-profile` requires no JWT. Only public User/Owner
profiles return 200, with exactly `name` and `profile_image`. Private, Admin and
nonexistent profiles return the same generic 404. Responses use no-store caching.
This endpoint does not serve image bytes or implement uploads. Image references
are the existing stored profile reference, not a new public storage route.

Plan and AI-image preferences are creation defaults only: changing them neither
publishes existing content nor creates sharing links. Their content APIs do not
exist yet; future endpoints must enforce ownership and explicit content privacy.
No claim of completed plan/image access enforcement is made by this stage.

Isolated checks: from `backend`, run
`.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`.
Privacy tests use ephemeral real JWT signing and disposable SQLite accounts;
Stage 1 tests mock JWT decoding. Both block configured database connections.
These tests do not validate MySQL persistence or MySQL row-lock concurrency.

## Day 4 Stage 3: private profile pictures

All mutations derive the account exclusively from the JWT/database identity.

| Method/path | Request/access | Result |
| --- | --- | --- |
| `POST /users/me/picture` | Bearer JWT; raw JPEG/PNG bytes with `Content-Type: image/jpeg` or `image/png` | Upload/replace, `{"profile_image":"<opaque key>"}` |
| `DELETE /users/me/picture` | Bearer JWT | Remove, `{"profile_image":null}`; idempotent |
| `GET /users/me/picture` | Bearer JWT | Own image, including private/Admin images |
| `GET /users/{user_id}/picture` | Public visibility checked on every request | Public User/Owner picture only; otherwise generic 404 |

The upload contract is a raw image body, **not multipart or JSON**. Later frontend
integration should send the selected File/Blob with the correct content type,
overriding the API client's JSON default. Filenames, query account IDs, remote
URLs and client storage paths are never used. 415 rejects unsupported media
types, 413 rejects uploads exceeding 5 MiB while reading (even without a
Content-Length), and 422 rejects invalid/animated/unsupported image content or
decoded dimensions exceeding 16,000,000 pixels. Pillow verifies, decodes,
orients, resizes to fit 512×512 and re-encodes clean pixels as PNG without metadata.
Both JPEG and PNG inputs therefore return `image/png` on retrieval.

Private files default to `backend/private/profile-pictures` (gitignored). Set
`PROFILE_IMAGE_DIR` to an absolute private persistent path if needed; the service
does not change `.env`. The leaf directory is created lazily with mode 0700 and
files with mode 0600. Existing overly permissive directories are rejected.
Symlinked paths, frontend directories and paths containing public/static are
rejected. Do not mount this directory through a web server, CDN or static route.
Multiple workers/instances must share this same persistent storage. Back up files
and database references together. Pillow and python-multipart are installed in
the backend virtual environment; the raw-body endpoint does not use a multipart
parser, avoiding unbounded pre-handler multipart spooling.

Only random immutable keys are stored in `User.profile_image`. There is no
key-addressed serving endpoint. Image responses and handled errors have no-store,
nosniff and same-site resource-policy headers. Private images are fetched using
authenticated requests; later frontend code can display a temporary object URL.
Admin images are never served through the public endpoint, even if legacy JSON
claims a public profile. Legacy path/URL references are not fetched or served.

Mutations lock/reload the account row, write/fsync a new unique file, commit its
key, then delete the previous file. Retrieval holds the row lock until bytes are
read. A rollback before commit cleans up the new file; an ambiguous commit failure
retains both files to avoid breaking a potentially committed reference. Cleanup
failures and process crashes can leave private orphans, never a direct public URL.
An offline, coordinated orphan cleanup procedure is deferred; do not delete files
based on an uncoordinated database snapshot while uploads are running. MySQL lock
concurrency and crash recovery require isolated MySQL/deployment testing.

Tests use disposable SQLite accounts, real test-signed JWTs and temporary private
storage. Stage 1/2 regressions run alongside upload, replacement, removal,
visibility, validation, traversal/symlink, size-limit and failure tests. No live
MySQL records or production image files are touched.

## Day 4 Stage 4: migration-gated password management

**Prepared, not activated.** `AUTH_VERSION_ENABLED=false` and
`PASSWORD_MANAGEMENT_ENABLED=false` are the defaults. No automatic migrations or
database creation run. The model's new server-default column is deferred, and
eager default loading is disabled: legacy selects/inserts/updates do not reference
`auth_version` while the gate is off. Tests use a database genuinely missing that
column. Never enable the version gate against the current unmigrated database.

Migration `backend/migrations/002_user_auth_version.sql` adds only
`User.auth_version BIGINT UNSIGNED NOT NULL DEFAULT 0`, using `ALGORITHM=INSTANT`
to fail rather than silently rebuild. It preserves the 16-table structure.
Execution requires separate approval, a current backup and confirmation that the
actual MySQL version/table supports the algorithm. No migration has been executed.

Activation sequence (manual, separately approved):

1. Verify backup, table count, column absence and MySQL compatibility; test the
   migration in isolated MySQL first. Obtain migration execution approval.
2. Apply the additive migration, verify the non-null default and unchanged
   account counts/identities/roles and existing password hashes without printing
   them. Keep both gates false until ready for the coordinated rollout.
3. Drain existing requests and replace all workers with version-aware code;
   enable `AUTH_VERSION_ENABLED=true` consistently. Do not run mixed workers.
   All existing JWTs lacking the claim now return 401, including Remember Me.
4. Restart sign-in/OAuth transactions. Pre-activation existing-account OAuth
   authorization/login/link proofs cannot bypass version checks.
5. Verify login for all roles and Google, then separately enable
   `PASSWORD_MANAGEMENT_ENABLED=true` when Redis and API integration are ready.

New JWTs contain a strictly validated integer `auth_version` and a random `jti`
so separately issued sessions are distinct even within the same second. Every
authenticated request compares the claim with the database; neither a client role
nor an email supplies authorization. Password login locks/reloads the account
before password verification and token issuance. Google existing-account login
completion and linking check the captured version under a row lock. Sensitive
profile/privacy/picture writes recheck the authenticated version when locking.
An already-authorized in-flight read cannot be retroactively withdrawn.

| Endpoint | Payload and authorization |
| --- | --- |
| `POST /auth/password/change` | JWT; `current_password`, `new_password`, `confirm_password`; password-based User/Owner/Admin |
| `POST /auth/google/password-setup/start` | JWT, permitted Origin and JSON `{"consent":true}`; Google-only User/Owner |
| `POST /auth/google/password-setup/complete` | Same JWT session, browser cookies, JSON `new_password`, `confirm_password` |

New passwords use the existing policy: 8–128 characters, uppercase and lowercase,
matching confirmation, no trimming. Argon2 remains the hasher. Unknown fields are
rejected. Incorrect current password returns 400, invalid schemas 422, invalid or
revoked JWTs 401, and disabled features/unavailable Redis 503. Successful writes
return `{"status":"password_updated","reauthentication_required":true}` with
no replacement JWT. Hash and incremented version commit atomically; all earlier
sessions, including the initiating and remembered sessions, become invalid.

Google setup uses a new authorization-code flow with independent state, nonce,
S256 PKCE and browser binding. Separate Redis purposes bind it to account ID,
original Google subject, JWT digest, version and start time. Only the existing
verified Google `sub` can authorize setup. No email merge or Admin setup is allowed.
Authorization expires after 300 seconds; completion proof has at most 60 seconds
and remains within the original 300-second window. Redis consumes proofs atomically
once. Callback reuses `/auth/google/callback` and the fixed frontend return URL,
with the static `#google-password-setup` marker and an HttpOnly completion cookie.
This is fresh Google verification, not a promise of a Google password prompt.
The existing frontend does not handle this new marker yet; frontend integration
is intentionally deferred. No passwords, Google codes or JWTs go in frontend URLs.

Redis rate limits are five attempts per account/action per five minutes and 30
password-management requests per peer IP across actions per five minutes. Limits
run before hashing or provider exchange, return 429 with Retry-After and fail
closed. Password changes do not depend on Google credentials or its enabled flag.
Only a trusted ASGI peer is used; deployment must configure trusted proxies.
Existing password login throttling is not introduced by this stage.

Concurrent writes use row locks plus a compare-and-swap predicate on version and
password hash. Only one stale-version writer can succeed. Rollback restores both
hash and version; ambiguous commit errors must not be blindly retried. A consumed
Google proof is not restored after database failure: restart verification.
The interactive Admin reset helper increments the version whenever the column
exists (even with the feature gate off), and refuses a missing column if version
enforcement is on. It preserves the existing exactly-one-Admin and identity checks.

Safe rollback: disable `PASSWORD_MANAGEMENT_ENABLED` while keeping
`AUTH_VERSION_ENABLED=true`, retaining the column and all version checks. Never
reset versions, drop the column or deploy code ignoring it: revoked tokens can
become valid again. Database restoration can also resurrect old versions/hashes.
A destructive rollback requires a separate recovery/key-rotation decision; this
implementation does not rotate existing keys.

Testing: `.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v`.
Stage 4 uses real Argon2/JWT signatures, disposable SQLite (with and without the
column) and a spawned Redis process on a private temporary Unix socket, with TCP
and persistence disabled. No configured Redis/MySQL is contacted. Redis tests are
skipped explicitly if redis-server is unavailable. Provider exchanges are simulated;
offline ID-token tests use real RSA signatures and mocked network responses.
SQLite compare-and-swap concurrency does not establish MySQL row-lock behavior.
Live MySQL migration/persistence/locking, real Google consent and browser/frontend
integration remain untested and are required before production activation.
