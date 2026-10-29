-- PREPARED ONLY. Back up and obtain migration approval before executing.
-- Keep AUTH_VERSION_ENABLED=false until applied and verified. No automatic DDL.
-- Keep PASSWORD_MANAGEMENT_ENABLED=false until rollout and isolated checks finish.
-- MySQL 8.0.12+ eligible InnoDB tables; fail rather than silently rebuild.
ALTER TABLE `User`
    ADD COLUMN `auth_version` BIGINT UNSIGNED NOT NULL DEFAULT 0,
    ALGORITHM=INSTANT;
