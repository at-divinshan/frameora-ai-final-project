-- Manual approval only. Additive; leaves legacy Notification and migrations 006/007 untouched.
CREATE TABLE IF NOT EXISTS AppNotification (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 user_id INT NOT NULL,
 event_key VARCHAR(190) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 message VARCHAR(500) NOT NULL,
 href VARCHAR(200) NOT NULL,
 is_read BOOLEAN NOT NULL DEFAULT FALSE,
 created_at DATETIME NOT NULL,
 CONSTRAINT fk_app_notification_user FOREIGN KEY (user_id) REFERENCES User(id),
 CONSTRAINT uq_app_notification_event UNIQUE (user_id, event_key),
 INDEX ix_app_notification_unread (user_id, is_read, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
