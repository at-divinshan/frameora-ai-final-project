-- Additive, manual approval only. No existing User rows or credentials are changed.
-- Absence of an AccountStatus row means active, version 0 for legacy accounts.
CREATE TABLE IF NOT EXISTS AccountStatus (
 user_id INT NOT NULL PRIMARY KEY,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 version INT NOT NULL DEFAULT 0,
 changed_at DATETIME NOT NULL,
 CONSTRAINT fk_account_status_user FOREIGN KEY (user_id) REFERENCES User(id),
 CONSTRAINT ck_account_status_version CHECK (version >= 0),
 CONSTRAINT ck_account_status_active CHECK (is_active IN (0,1))
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS AccountStatusAudit (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 user_id INT NOT NULL,
 actor_id INT NOT NULL,
 old_active BOOLEAN NOT NULL,
 new_active BOOLEAN NOT NULL,
 version INT NOT NULL,
 changed_at DATETIME NOT NULL,
 CONSTRAINT fk_account_audit_user FOREIGN KEY (user_id) REFERENCES User(id),
 CONSTRAINT fk_account_audit_actor FOREIGN KEY (actor_id) REFERENCES User(id),
 CONSTRAINT uq_account_status_audit_version UNIQUE (user_id, version),
 CONSTRAINT ck_account_audit_transition CHECK (old_active <> new_active),
 INDEX ix_account_status_audit_user_time (user_id,changed_at)
) ENGINE=InnoDB;
