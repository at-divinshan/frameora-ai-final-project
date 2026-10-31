-- PROPOSAL ONLY. Requires separate review, isolated rehearsal and approval.
-- Never automatically run this file at application startup.
-- Confirm SELECT DATABASE() names the explicitly approved target, MySQL 8,
-- UserProfile is InnoDB, and SHOW CREATE TABLE matches the reviewed definition.
-- Confirm studio_photo is absent and take a verified backup before execution.
-- MySQL ALTER TABLE implicitly commits; this is not transactionally reversible.
ALTER TABLE `UserProfile`
    ADD COLUMN `studio_photo` VARCHAR(68) CHARACTER SET ascii COLLATE ascii_bin NULL DEFAULT NULL,
    ADD CONSTRAINT `m004_ck_studio_photo_key`
      CHECK (`studio_photo` IS NULL OR REGEXP_LIKE(`studio_photo`, '^[0-9a-f]{64}[.]png$', 'c'));
