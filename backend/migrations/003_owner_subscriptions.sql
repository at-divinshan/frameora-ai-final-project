-- Frameora AI Step 33 — PREPARED ONLY; never auto-run.
-- MySQL 8.0.46 / InnoDB. Read docs/003_owner_subscriptions_review.md first.
-- Execute this file ALONE, once, only after backup, rehearsal and explicit approval.
-- Stop all application/worker/admin writers for the entire maintenance window.
-- DO NOT use mysql --force. DO NOT run 002_user_auth_version.sql.
-- No Payment/User/UserProfile ALTER, account writes, seeds, or payment activation.
-- The only DML fills three verified SubscriptionPlan.code values.
-- DDL implicitly commits. Earlier ALTERs survive later failure; no automatic undo.
-- A short-lived procedure makes every preflight SIGNAL stop the remaining body,
-- even if a client ignores errors. It does not add a table.
-- The named advisory lock coordinates this migration only, NOT application writers.

DELIMITER $$
CREATE PROCEDURE `frameora_m003_owner_subscriptions`()
SQL SECURITY INVOKER
BEGIN
    DECLARE v_lock INT DEFAULT 0;
    DECLARE v_signature TEXT;
    DECLARE v_missing_privileges INT DEFAULT 0;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK; -- Only outstanding DML; never reverses completed DDL.
        IF v_lock = 1 THEN
            DO RELEASE_LOCK('frameora:m003:owner_subscriptions');
        END IF;
        RESIGNAL;
    END;

    IF DATABASE() IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: select the approved database first';
    END IF;
    IF VERSION() NOT LIKE '8.0.46%' OR VERSION() LIKE '%MariaDB%' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: reviewed for MySQL 8.0.46 only';
    END IF;
    IF @@SESSION.autocommit <> 1 OR @@SESSION.foreign_key_checks <> 1
       OR @@SESSION.unique_checks <> 1
       OR @@SESSION.group_concat_max_len < 1024
       OR FIND_IN_SET('NO_ZERO_DATE', @@SESSION.sql_mode) = 0
       OR FIND_IN_SET('NO_ZERO_IN_DATE', @@SESSION.sql_mode) = 0
       OR (FIND_IN_SET('STRICT_TRANS_TABLES', @@SESSION.sql_mode) = 0
           AND FIND_IN_SET('STRICT_ALL_TABLES', @@SESSION.sql_mode) = 0) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: unsafe session settings; see review';
    END IF;
    SELECT GET_LOCK('frameora:m003:owner_subscriptions', 0) INTO v_lock;
    IF v_lock IS NULL OR v_lock <> 1 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: another migration holds the advisory lock';
    END IF;
    -- Verify grants before trusting privilege-filtered metadata (especially TRIGGERS).
    -- Only CURRENT_USER and ENABLED_ROLES may contribute; merely granted/inactive
    -- roles never qualify. Missing/invisible evidence fails closed.
    -- Partial revokes need a separate evaluator; do not infer global rights then.
    IF @@GLOBAL.partial_revokes <> 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: partial revokes require separate privilege review';
    END IF;
    WITH principals AS (
        SELECT CONCAT(QUOTE(LEFT(CURRENT_USER(), LENGTH(CURRENT_USER())
                    - LENGTH(SUBSTRING_INDEX(CURRENT_USER(), '@', -1)) - 1)),
                    '@', QUOTE(SUBSTRING_INDEX(CURRENT_USER(), '@', -1))) AS grantee
        UNION
        SELECT CONCAT(QUOTE(ROLE_NAME), '@', QUOTE(ROLE_HOST))
        FROM information_schema.ENABLED_ROLES
    ), effective_grants AS (
        SELECT g.PRIVILEGE_TYPE AS privilege_type,
               CAST(NULL AS CHAR(64)) AS schema_name, CAST(NULL AS CHAR(64)) AS table_name
        FROM information_schema.USER_PRIVILEGES g
        JOIN principals p ON BINARY p.grantee = BINARY g.GRANTEE
        UNION
        SELECT g.PRIVILEGE_TYPE, g.TABLE_SCHEMA, NULL
        FROM information_schema.SCHEMA_PRIVILEGES g
        JOIN principals p ON BINARY p.grantee = BINARY g.GRANTEE
        WHERE BINARY g.TABLE_SCHEMA = BINARY DATABASE()
        UNION
        SELECT g.PRIVILEGE_TYPE, g.TABLE_SCHEMA, g.TABLE_NAME
        FROM information_schema.TABLE_PRIVILEGES g
        JOIN principals p ON BINARY p.grantee = BINARY g.GRANTEE
        WHERE BINARY g.TABLE_SCHEMA = BINARY DATABASE()
        UNION
        SELECT g.PRIVILEGE_TYPE, g.TABLE_SCHEMA, g.TABLE_NAME
        FROM information_schema.ROLE_TABLE_GRANTS g
        JOIN information_schema.ENABLED_ROLES r
          ON BINARY r.ROLE_NAME = BINARY g.GRANTEE AND BINARY r.ROLE_HOST = BINARY g.GRANTEE_HOST
        WHERE BINARY g.TABLE_SCHEMA = BINARY DATABASE()
    ), affected AS (
        SELECT 'SubscriptionPlan' AS table_name UNION ALL SELECT 'Subscription'
        UNION ALL SELECT 'CreditTransaction' UNION ALL SELECT 'CustomerProject'
        UNION ALL SELECT 'ShareLink'
    ), required AS (
        SELECT a.table_name, p.privilege_type FROM affected a CROSS JOIN (
            SELECT 'ALTER' AS privilege_type UNION ALL SELECT 'CREATE'
            UNION ALL SELECT 'INSERT' UNION ALL SELECT 'TRIGGER'
        ) p
        UNION ALL SELECT 'SubscriptionPlan', 'UPDATE'
        UNION ALL SELECT 'User', 'REFERENCES'
        UNION ALL SELECT 'SubscriptionPlan', 'REFERENCES'
        UNION ALL SELECT 'Subscription', 'REFERENCES'
        UNION ALL SELECT 'AIGeneration', 'REFERENCES'
        UNION ALL SELECT 'CustomerProject', 'REFERENCES'
        UNION ALL SELECT NULL, 'CREATE ROUTINE'
        UNION ALL SELECT NULL, 'ALTER ROUTINE'
        UNION ALL SELECT NULL, 'EXECUTE'
        UNION ALL SELECT t.table_name, 'SELECT' FROM (
            SELECT 'User' AS table_name UNION ALL SELECT 'UserProfile'
            UNION ALL SELECT 'SubscriptionPlan' UNION ALL SELECT 'Subscription'
            UNION ALL SELECT 'CreditTransaction' UNION ALL SELECT 'CustomerProject'
            UNION ALL SELECT 'ShareLink' UNION ALL SELECT 'AIGeneration'
            UNION ALL SELECT 'AIResult' UNION ALL SELECT 'Equipment'
            UNION ALL SELECT 'MediaAsset' UNION ALL SELECT 'Notification'
            UNION ALL SELECT 'Payment' UNION ALL SELECT 'PhotographyPlan'
            UNION ALL SELECT 'PlanEquipment' UNION ALL SELECT 'ResultRating'
        ) t
    )
    SELECT COUNT(*) INTO v_missing_privileges FROM required req
    WHERE NOT EXISTS (
        SELECT 1 FROM effective_grants g
        WHERE g.privilege_type = req.privilege_type
          AND (g.schema_name IS NULL OR BINARY g.schema_name = BINARY DATABASE())
          AND (g.table_name IS NULL OR BINARY g.table_name = BINARY req.table_name)
    );
    IF v_missing_privileges <> 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: effective migration grants unproven; review enabled roles and privileges';
    END IF;

    IF (SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE') <> 16 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: expected exactly 16 base tables';
    END IF;
    SELECT GROUP_CONCAT(TABLE_NAME ORDER BY BINARY TABLE_NAME SEPARATOR ',')
    INTO v_signature FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE';
    IF BINARY COALESCE(v_signature, '') <> BINARY
       'AIGeneration,AIResult,CreditTransaction,CustomerProject,Equipment,MediaAsset,Notification,Payment,PhotographyPlan,PlanEquipment,ResultRating,ShareLink,Subscription,SubscriptionPlan,User,UserProfile' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: unexpected table names';
    END IF;
    IF (SELECT COUNT(*) FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME IN ('User','UserProfile','SubscriptionPlan','Subscription',
                             'CreditTransaction','CustomerProject','ShareLink','AIGeneration')
          AND ENGINE = 'InnoDB' AND TABLE_COLLATION = 'utf8mb4_0900_ai_ci') <> 8 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: table engine/collation mismatch';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.TRIGGERS
               WHERE TRIGGER_SCHEMA = DATABASE()
                 AND EVENT_OBJECT_TABLE IN ('SubscriptionPlan','Subscription',
                     'CreditTransaction','CustomerProject','ShareLink')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: unreviewed trigger on affected table';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS
               WHERE CONSTRAINT_SCHEMA = DATABASE()
                 AND TABLE_NAME IN ('SubscriptionPlan','Subscription',
                     'CreditTransaction','CustomerProject','ShareLink')
                 AND CONSTRAINT_TYPE = 'CHECK') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: unexpected existing CHECK constraint';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS
               WHERE CONSTRAINT_SCHEMA = DATABASE()
                 AND LEFT(CONSTRAINT_NAME, 5) = 'm003_') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: migration constraint name already exists';
    END IF;

    -- Exact ordered column baselines: name|type|nullability|default|extra.
    -- A prior/partial migration or extra column fails before table ALTERs.
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'User';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;name|varchar(100)|NO|<NULL>|;email|varchar(255)|NO|<NULL>|;password_hash|varchar(255)|YES|<NULL>|;role|varchar(30)|NO|<NULL>|;is_verified|tinyint(1)|NO|0|;created_at|datetime|NO|CURRENT_TIMESTAMP|DEFAULT_GENERATED;phone|varchar(20)|YES|<NULL>|;profile_image|varchar(500)|YES|<NULL>|;privacy_preferences|json|YES|<NULL>|;google_sub|varbinary(255)|YES|<NULL>|' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: User column definition mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'UserProfile';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;user_id|int|NO|<NULL>|;studio_name|varchar(150)|YES|<NULL>|;studio_phone|varchar(20)|YES|<NULL>|;studio_address|varchar(255)|YES|<NULL>|;studio_city|varchar(100)|YES|<NULL>|;studio_description|text|YES|<NULL>|;onboarding_status|varchar(30)|NO|pending_studio|;onboarding_completed_at|datetime|YES|<NULL>|' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: UserProfile column definition mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'SubscriptionPlan';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;name|varchar(100)|NO|<NULL>|;user_role|varchar(30)|NO|<NULL>|;monthly_credits|int|NO|<NULL>|;price|decimal(10,2)|NO|<NULL>|;is_active|tinyint(1)|NO|<NULL>|;max_projects|int|YES|<NULL>|;max_share_links|int|YES|<NULL>|;trial_days|int|YES|<NULL>|;currency|char(3)|NO|LKR|' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: SubscriptionPlan column definition mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Subscription';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;user_id|int|NO|<NULL>|;plan_id|int|NO|<NULL>|;start_date|datetime|NO|<NULL>|;end_date|datetime|NO|<NULL>|;status|varchar(30)|NO|<NULL>|' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: Subscription column definition mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'CreditTransaction';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;user_id|int|NO|<NULL>|;generation_id|int|YES|<NULL>|;credits_change|int|NO|<NULL>|;transaction_type|varchar(30)|NO|<NULL>|;created_at|datetime|NO|CURRENT_TIMESTAMP|DEFAULT_GENERATED' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: CreditTransaction column definition mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'CustomerProject';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;studio_owner_id|int|NO|<NULL>|;customer_name|varchar(100)|NO|<NULL>|;customer_contact|varchar(100)|YES|<NULL>|;event_type|varchar(100)|YES|<NULL>|;shooting_date|date|YES|<NULL>|;requirements|text|YES|<NULL>|;created_at|datetime|NO|CURRENT_TIMESTAMP|DEFAULT_GENERATED' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: CustomerProject column definition mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ShareLink';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;project_id|int|YES|<NULL>|;generation_id|int|NO|<NULL>|;token_hash|varchar(255)|NO|<NULL>|;is_active|tinyint(1)|NO|1|;expires_at|datetime|YES|<NULL>|;created_at|datetime|NO|CURRENT_TIMESTAMP|DEFAULT_GENERATED' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: ShareLink column definition mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
               COALESCE(COLUMN_DEFAULT, '<NULL>'), EXTRA)
               ORDER BY ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'AIGeneration';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'id|int|NO|<NULL>|auto_increment;user_id|int|NO|<NULL>|;plan_id|int|NO|<NULL>|;model_name|varchar(100)|YES|<NULL>|;quality|varchar(20)|NO|<NULL>|;status|varchar(30)|NO|<NULL>|;error_message|text|YES|<NULL>|;created_at|datetime|NO|CURRENT_TIMESTAMP|DEFAULT_GENERATED;completed_at|datetime|YES|<NULL>|;guidance_text|longtext|YES|<NULL>|;is_favorite|tinyint(1)|NO|0|' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: AIGeneration column definition mismatch';
    END IF;

    -- Exact existing index definitions, including visibility and prefix lengths.
    SELECT GROUP_CONCAT(CONCAT_WS('|', INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX,
               COLUMN_NAME, INDEX_TYPE, COALESCE(SUB_PART, '<NULL>'), IS_VISIBLE, COLLATION)
               ORDER BY BINARY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ';') INTO v_signature
    FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'User';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'PRIMARY|0|1|id|BTREE|<NULL>|YES|A;email|0|1|email|BTREE|<NULL>|YES|A;uq_user_google_sub|0|1|google_sub|BTREE|<NULL>|YES|A' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: User index mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX,
               COLUMN_NAME, INDEX_TYPE, COALESCE(SUB_PART, '<NULL>'), IS_VISIBLE, COLLATION)
               ORDER BY BINARY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ';') INTO v_signature
    FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'UserProfile';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'PRIMARY|0|1|id|BTREE|<NULL>|YES|A;user_id|0|1|user_id|BTREE|<NULL>|YES|A' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: UserProfile index mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX,
               COLUMN_NAME, INDEX_TYPE, COALESCE(SUB_PART, '<NULL>'), IS_VISIBLE, COLLATION)
               ORDER BY BINARY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ';') INTO v_signature
    FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'SubscriptionPlan';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'PRIMARY|0|1|id|BTREE|<NULL>|YES|A' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: SubscriptionPlan index mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX,
               COLUMN_NAME, INDEX_TYPE, COALESCE(SUB_PART, '<NULL>'), IS_VISIBLE, COLLATION)
               ORDER BY BINARY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ';') INTO v_signature
    FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Subscription';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'PRIMARY|0|1|id|BTREE|<NULL>|YES|A;fk_sub_plan|1|1|plan_id|BTREE|<NULL>|YES|A;fk_sub_user|1|1|user_id|BTREE|<NULL>|YES|A' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: Subscription index mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX,
               COLUMN_NAME, INDEX_TYPE, COALESCE(SUB_PART, '<NULL>'), IS_VISIBLE, COLLATION)
               ORDER BY BINARY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ';') INTO v_signature
    FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'CreditTransaction';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'PRIMARY|0|1|id|BTREE|<NULL>|YES|A;fk_credit_generation|1|1|generation_id|BTREE|<NULL>|YES|A;fk_credit_user|1|1|user_id|BTREE|<NULL>|YES|A' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: CreditTransaction index mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX,
               COLUMN_NAME, INDEX_TYPE, COALESCE(SUB_PART, '<NULL>'), IS_VISIBLE, COLLATION)
               ORDER BY BINARY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ';') INTO v_signature
    FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'CustomerProject';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'PRIMARY|0|1|id|BTREE|<NULL>|YES|A;fk_project_owner|1|1|studio_owner_id|BTREE|<NULL>|YES|A' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: CustomerProject index mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX,
               COLUMN_NAME, INDEX_TYPE, COALESCE(SUB_PART, '<NULL>'), IS_VISIBLE, COLLATION)
               ORDER BY BINARY INDEX_NAME, SEQ_IN_INDEX SEPARATOR ';') INTO v_signature
    FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ShareLink';
    IF BINARY COALESCE(v_signature, '') <> BINARY 'PRIMARY|0|1|id|BTREE|<NULL>|YES|A;fk_share_generation|1|1|generation_id|BTREE|<NULL>|YES|A;fk_share_project|1|1|project_id|BTREE|<NULL>|YES|A;token_hash|0|1|token_hash|BTREE|<NULL>|YES|A' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: ShareLink index mismatch';
    END IF;

    -- Reject external schema references before DDL or any rehearsal fixture writes.
    -- Includes AIGeneration/PhotographyPlan ownership prerequisites, not just ALTER targets.
    IF EXISTS (SELECT 1 FROM information_schema.KEY_COLUMN_USAGE
               WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL
                 AND (REFERENCED_TABLE_SCHEMA IS NULL
                      OR BINARY REFERENCED_TABLE_SCHEMA <> BINARY DATABASE())) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: cross-database foreign key reference rejected';
    END IF;

    -- Existing FK targets and RESTRICT/NO ACTION behavior must be preserved.
    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'User' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: User foreign key mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'UserProfile' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY 'fk_profile_user|user_id|User|id' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: UserProfile foreign key mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'SubscriptionPlan' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: SubscriptionPlan foreign key mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Subscription' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY 'fk_sub_plan|plan_id|SubscriptionPlan|id;fk_sub_user|user_id|User|id' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: Subscription foreign key mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'CreditTransaction' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY 'fk_credit_generation|generation_id|AIGeneration|id;fk_credit_user|user_id|User|id' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: CreditTransaction foreign key mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'CustomerProject' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY 'fk_project_owner|studio_owner_id|User|id' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: CustomerProject foreign key mismatch';
    END IF;
    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ShareLink' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY 'fk_share_generation|generation_id|AIGeneration|id;fk_share_project|project_id|CustomerProject|id' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: ShareLink foreign key mismatch';
    END IF;

    SELECT GROUP_CONCAT(CONCAT_WS('|', CONSTRAINT_NAME, COLUMN_NAME,
               REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME)
               ORDER BY BINARY CONSTRAINT_NAME, ORDINAL_POSITION SEPARATOR ';') INTO v_signature
    FROM information_schema.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'AIGeneration' AND REFERENCED_TABLE_NAME IS NOT NULL;
    IF BINARY COALESCE(v_signature, '') <> BINARY 'fk_generation_plan|plan_id|PhotographyPlan|id;fk_generation_user|user_id|User|id' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: AIGeneration ownership foreign key mismatch';
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.REFERENTIAL_CONSTRAINTS
               WHERE CONSTRAINT_SCHEMA = DATABASE()
                 AND TABLE_NAME IN ('UserProfile','Subscription','CreditTransaction','CustomerProject','ShareLink','AIGeneration')
                 AND (UPDATE_RULE NOT IN ('RESTRICT','NO ACTION')
                      OR DELETE_RULE NOT IN ('RESTRICT','NO ACTION'))) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: unexpected cascading foreign key';
    END IF;
    IF (SELECT COUNT(*) FROM `User`) <> 8
       OR (SELECT COUNT(*) FROM `User` WHERE `role` = 'owner') <> 3
       OR (SELECT COUNT(*) FROM `User` WHERE `role` = 'admin') <> 1
       OR EXISTS (SELECT 1 FROM `User` WHERE BINARY `role` NOT IN ('user','owner','admin')) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: user count/role assumptions changed';
    END IF;
    -- Existing profiles are allowed: Studio Setup may already have saved pending_plan.
    -- The exact UserProfile schema, UNIQUE user_id and same-database FK were checked above.
    -- Preserve every profile field and timestamp; never require deleting profiles to migrate.
    IF EXISTS (SELECT 1 FROM `UserProfile` p LEFT JOIN `User` u ON u.id = p.user_id
               WHERE u.id IS NULL) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: orphan profile reference; separate data review required';
    END IF;
    IF EXISTS (SELECT 1 FROM `Subscription`)
       OR EXISTS (SELECT 1 FROM `CreditTransaction`)
       OR EXISTS (SELECT 1 FROM `CustomerProject`)
       OR EXISTS (SELECT 1 FROM `ShareLink`) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: business tables not empty; backfill review required';
    END IF;
    IF (SELECT COUNT(*) FROM `SubscriptionPlan`) <> 3
       OR (SELECT COUNT(*) FROM `SubscriptionPlan` WHERE
           (id=1 AND BINARY name=BINARY 'Free Basic' AND BINARY user_role=BINARY 'owner'
            AND monthly_credits=10 AND price=0.00 AND BINARY currency=BINARY 'LKR'
            AND max_projects=2 AND max_share_links=3 AND trial_days IS NULL AND is_active=1)
        OR (id=2 AND BINARY name=BINARY 'Free Trial' AND BINARY user_role=BINARY 'owner'
            AND monthly_credits=100 AND price=0.00 AND BINARY currency=BINARY 'LKR'
            AND max_projects=10 AND max_share_links=20 AND trial_days=14 AND is_active=1)
        OR (id=3 AND BINARY name=BINARY 'Paid Pro' AND BINARY user_role=BINARY 'owner'
            AND monthly_credits=500 AND price=1500.00 AND BINARY currency=BINARY 'LKR'
            AND max_projects=50 AND max_share_links=100 AND trial_days IS NULL AND is_active=1)) <> 3 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: exact plan catalogue baseline mismatch';
    END IF;

    -- ALL preflight checks have passed. DDL below is NOT a single transaction.
    ALTER TABLE `SubscriptionPlan`
        ADD COLUMN `code` VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NULL,
        ADD CONSTRAINT `m003_chk_plan_code`
            CHECK (`code` IS NULL OR `code` IN ('basic','trial','pro')),
        ADD UNIQUE KEY `m003_uq_plan_role_code` (`user_role`, `code`);

    ALTER TABLE `Subscription`
        MODIFY COLUMN `end_date` DATETIME NULL,
        ADD COLUMN `plan_kind` VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        ADD COLUMN `activation_key` VARBINARY(64) NOT NULL,
        ADD COLUMN `trial_owner_id` INT GENERATED ALWAYS AS
            (CASE WHEN `plan_kind`='trial' THEN `user_id` ELSE NULL END) STORED,
        ADD COLUMN `active_owner_id` INT GENERATED ALWAYS AS
            (CASE WHEN `status`='active' THEN `user_id` ELSE NULL END) STORED,
        ADD COLUMN `pending_owner_id` INT GENERATED ALWAYS AS
            (CASE WHEN `status`='pending_payment' THEN `user_id` ELSE NULL END) STORED,
        ADD CONSTRAINT `m003_chk_sub_kind`
            CHECK (`plan_kind` IN ('basic','trial','pro')),
        ADD CONSTRAINT `m003_chk_sub_status_dates` CHECK (
            (`plan_kind`='basic' AND `end_date` IS NULL
             AND `status` IN ('active','superseded','cancelled'))
            OR (`plan_kind`='trial' AND `end_date` IS NOT NULL
                AND `end_date`=DATE_ADD(`start_date`, INTERVAL 14 DAY)
                AND `status` IN ('active','expired','superseded','cancelled'))
            OR (`plan_kind`='pro' AND `end_date` IS NOT NULL AND `end_date`>`start_date`
                AND `status` IN ('active','expired','superseded','pending_payment','cancelled'))
        ),
        ADD CONSTRAINT `m003_chk_sub_key` CHECK (OCTET_LENGTH(`activation_key`)=32),
        ADD UNIQUE KEY `m003_uq_trial_owner` (`trial_owner_id`),
        ADD UNIQUE KEY `m003_uq_active_owner` (`active_owner_id`),
        ADD UNIQUE KEY `m003_uq_pending_owner` (`pending_owner_id`),
        ADD UNIQUE KEY `m003_uq_activation` (`user_id`,`activation_key`),
        ADD UNIQUE KEY `m003_uq_sub_user_id` (`user_id`,`id`),
        ADD KEY `m003_ix_sub_user_status_end` (`user_id`,`status`,`end_date`);

    ALTER TABLE `CreditTransaction`
        ADD COLUMN `subscription_id` INT NOT NULL,
        ADD COLUMN `period_start` DATETIME NOT NULL,
        ADD COLUMN `period_end` DATETIME NOT NULL,
        ADD COLUMN `operation_key` VARBINARY(128) NOT NULL,
        ADD COLUMN `request_hash` BINARY(32) NOT NULL,
        ADD COLUMN `grant_period_start` DATETIME GENERATED ALWAYS AS
            (CASE WHEN `transaction_type`='grant' THEN `period_start` ELSE NULL END) STORED,
        ADD CONSTRAINT `m003_chk_credit_period` CHECK (`period_end`>`period_start`),
        ADD CONSTRAINT `m003_chk_credit_signed` CHECK (
            (`transaction_type` IN ('grant','refund') AND `credits_change`>0)
            OR (`transaction_type`='spend' AND `credits_change`<0)
        ),
        ADD CONSTRAINT `m003_chk_credit_key` CHECK (OCTET_LENGTH(`operation_key`)=32),
        ADD UNIQUE KEY `m003_uq_credit_operation` (`user_id`,`operation_key`),
        ADD UNIQUE KEY `m003_uq_credit_grant` (`user_id`,`subscription_id`,`grant_period_start`),
        ADD KEY `m003_ix_credit_balance` (`user_id`,`subscription_id`,`period_start`,`period_end`),
        ADD CONSTRAINT `m003_fk_credit_subscription_owner`
            FOREIGN KEY (`user_id`,`subscription_id`) REFERENCES `Subscription` (`user_id`,`id`);

    ALTER TABLE `CustomerProject`
        ADD COLUMN `deleted_at` DATETIME NULL,
        ADD KEY `m003_ix_project_owner_live_order` (`studio_owner_id`,`deleted_at`,`created_at`,`id`);

    ALTER TABLE `ShareLink`
        ADD KEY `m003_ix_share_generation_active` (`generation_id`,`is_active`,`expires_at`,`created_at`,`id`),
        ADD KEY `m003_ix_share_generation_order` (`generation_id`,`is_active`,`created_at`,`id`);

    -- The only DML. Do not generalize this to all owner plans or use display names alone.
    START TRANSACTION;
    UPDATE `SubscriptionPlan`
    SET `code`=CASE `id` WHEN 1 THEN 'basic' WHEN 2 THEN 'trial' WHEN 3 THEN 'pro' END
    WHERE `code` IS NULL AND BINARY `user_role`=BINARY 'owner'
      AND ((`id`=1 AND BINARY `name`=BINARY 'Free Basic')
        OR (`id`=2 AND BINARY `name`=BINARY 'Free Trial')
        OR (`id`=3 AND BINARY `name`=BINARY 'Paid Pro'));
    IF ROW_COUNT() <> 3 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: plan backfill did not affect exactly three rows';
    END IF;
    COMMIT;
    DO RELEASE_LOCK('frameora:m003:owner_subscriptions');
    SET v_lock = 0;
END$$
DELIMITER ;

CALL `frameora_m003_owner_subscriptions`();
-- In batch mode without --force an error stops before this statement. If a
-- client nevertheless continues, dropping this helper cannot apply more DDL.
DROP PROCEDURE `frameora_m003_owner_subscriptions`;
