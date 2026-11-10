-- Prepared only. Requires explicit approval before execution on any real database.
-- Independent of pending Live Pose migration 006. Existing tables/data unchanged.
CREATE TABLE ImageFeedback (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 project_id INT NOT NULL,
 asset_id INT NOT NULL,
 share_link_id INT NOT NULL,
 author_id INT NOT NULL,
 request_key VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 comment TEXT NOT NULL,
 status VARCHAR(16) NOT NULL DEFAULT 'pending',
 revised_asset_id INT NULL,
 created_at DATETIME NOT NULL,
 updated_at DATETIME NOT NULL,
 CONSTRAINT fk_feedback_project FOREIGN KEY (project_id) REFERENCES CustomerProject(id),
 CONSTRAINT fk_feedback_asset FOREIGN KEY (asset_id) REFERENCES MediaAsset(id),
 CONSTRAINT fk_feedback_share FOREIGN KEY (share_link_id) REFERENCES ShareLink(id),
 CONSTRAINT fk_feedback_author FOREIGN KEY (author_id) REFERENCES User(id),
 CONSTRAINT fk_feedback_revision FOREIGN KEY (revised_asset_id) REFERENCES MediaAsset(id),
 CONSTRAINT uq_feedback_request UNIQUE (author_id, request_key),
 CONSTRAINT chk_feedback_status CHECK (status IN ('pending','in_progress','resolved')),
 INDEX ix_feedback_project_image (project_id, asset_id, id)
) ENGINE=InnoDB;
