-- PROPOSAL ONLY. Do not execute automatically or against a live database.
-- Requires a separately approved backup, isolated MySQL 8 rehearsal and rollout.
-- Apply only after confirming the exact User and AIGeneration definitions/FKs.
-- No existing accounts or generations are modified; new accounts start implicitly
-- available (the allowance row is created on the first reserved free request).
-- Failed requests return the per-account row to 'available'; successful requests
-- link exactly one completed AIGeneration row and remain permanently consumed.
-- The backend must lock User first, then this table row, for every reservation and
-- completion. Keep all image-provider work outside the database transaction.
-- An interrupted 'reserved' row needs explicit reconciliation; do not auto-expire
-- it until generation timeouts and cancellation semantics are implemented.
-- DDL is additive but MySQL implicitly commits it. Rollback after rollout must
-- first disable new reservations and preserve/resolve allowance records; dropping
-- this table would erase consumed entitlements and is not an automatic rollback.

CREATE TABLE `FreeGenerationAllowance` (
    `user_id` INT NOT NULL,
    `state` VARCHAR(16) NOT NULL DEFAULT 'available',
    `reservation_key` BINARY(32) NULL,
    `generation_id` INT NULL,
    `reserved_at` DATETIME NULL,
    `consumed_at` DATETIME NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`user_id`),
    UNIQUE KEY `m005_uq_free_generation_id` (`generation_id`),
    KEY `m005_ix_free_generation_state_reserved` (`state`, `reserved_at`),
    CONSTRAINT `m005_fk_free_generation_user`
        FOREIGN KEY (`user_id`) REFERENCES `User` (`id`),
    CONSTRAINT `m005_fk_free_generation_generation`
        FOREIGN KEY (`generation_id`) REFERENCES `AIGeneration` (`id`),
    CONSTRAINT `m005_ck_free_generation_state` CHECK (
        (`state` = 'available' AND `reservation_key` IS NULL
            AND `generation_id` IS NULL AND `reserved_at` IS NULL
            AND `consumed_at` IS NULL)
        OR
        (`state` = 'reserved' AND `reservation_key` IS NOT NULL
            AND `generation_id` IS NOT NULL AND `reserved_at` IS NOT NULL
            AND `consumed_at` IS NULL)
        OR
        (`state` = 'consumed' AND `reservation_key` IS NULL
            AND `generation_id` IS NOT NULL AND `reserved_at` IS NOT NULL
            AND `consumed_at` IS NOT NULL)
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET=utf8mb4
  COLLATE=utf8mb4_0900_ai_ci;
