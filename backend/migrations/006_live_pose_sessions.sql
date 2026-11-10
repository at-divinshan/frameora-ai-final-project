-- MANUAL APPROVAL REQUIRED. Do not run automatically. MySQL 8 / InnoDB.
-- Independent of image-generation allowances and credits. Contains no photographs.
CREATE TABLE LivePoseSession (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    request_key VARCHAR(36) NOT NULL,
    scene_hash VARCHAR(64) NOT NULL,
    plan_code VARCHAR(16) NOT NULL,
    created_at DATETIME NOT NULL,
    result JSON NOT NULL,
    CONSTRAINT fk_live_pose_user FOREIGN KEY (user_id) REFERENCES User(id),
    CONSTRAINT uq_live_pose_request UNIQUE (user_id, request_key),
    INDEX ix_live_pose_usage (user_id, created_at)
) ENGINE=InnoDB;
