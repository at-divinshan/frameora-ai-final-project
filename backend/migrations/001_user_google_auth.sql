-- MySQL 8 / InnoDB: prepare the existing User table for Google authentication.
-- Apply manually to the intended database only after approval and backup.
-- Run once, before starting the backend with the updated User model.
-- Existing password hashes, account identifiers, roles, and relationships are preserved.
-- DDL may rebuild/lock the table and cannot be undone with transaction ROLLBACK.
ALTER TABLE `User`
    MODIFY COLUMN `password_hash` VARCHAR(255) NULL DEFAULT NULL,
    ADD COLUMN `google_sub` VARBINARY(255) NULL DEFAULT NULL,
    ADD UNIQUE INDEX `uq_user_google_sub` (`google_sub`);
