# Studio photo migration proposal — NOT APPLIED

Migration 003 does not add studio_photo; the current ORM maps it as deferred for
legacy-schema compatibility. The live database
was not accessed in this sprint. Confirm its actual definition before approving this proposal.
Migration 004 adds one nullable opaque key to existing UserProfile, no table or data backfill.
Do not reuse personal User.profile_image or privacy JSON for studio photos.

Before execution: obtain approval, backup and restore into an isolated MySQL 8 database;
inspect SHOW CREATE TABLE UserProfile, table engine, existing columns/check names,
row counts and target database. Confirm VARCHAR(68) is suitable for the generated
64 lowercase hex characters plus .png. Rehearse the ALTER there. No SQL has been executed.
The operator needs ALTER/CREATE/INSERT and applicable metadata privileges.
The file intentionally fails if the column/check already exists; do not blindly rerun.
DDL implicitly commits. Recover failed/ambiguous deployment by inspecting the actual
schema and restoring a verified backup if necessary; never drop populated keys casually.

Post-approval verification: SHOW CREATE TABLE UserProfile; compare original row counts
and original field values to backup. Confirm existing studio_photo values are NULL.
Test uploads with disposable accounts/storage first. The new mapping defers this column
and omits it on ordinary profile inserts, preserving onboarding before migration.
Photo status reports available:false and mutations return 503 when the column is absent.

Files use the existing configured private profile-image storage directory, opaque
exclusive-created PNG filenames, mode 0600, directory mode 0700, outside static mounts.
JPEG/PNG/WebP decode and re-encode to metadata-free PNG <=512x512; 5 MiB streamed
limit and 16 megapixels; animations rejected. Owner JWT self routes and authorized read-only Admin routes serve images.
No public studio-photo endpoint exists. Normal studio updates leave the reference alone.
Replace/remove serialize on User; uncertain commit retains both private files. Crash or
cleanup failure can leave private orphan files; future audited garbage collection is deferred.
Neither migration 003 nor auth_version/password feature flags are changed.


Step 42 review: SQL 004 remains byte-for-byte unchanged. Apply only after successful
003 verification; applying 004 first makes the exact UserProfile preflight in 003 fail.
Existing profiles receive NULL for the new column while every prior field remains intact.
Manual metadata/target/privilege checks in this document are mandatory: 004 itself does
not implement the comprehensive automated preflight used by 003. MySQL regex/CHECK and
actual persistence remain unverified until an approved isolated MySQL rehearsal.
