-- PREPARED ONLY: apply manually after backup/review. No historical backfill.
CREATE TABLE IF NOT EXISTS ProjectGenerationPhase (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 project_id INT NOT NULL,
 generation_id INT NOT NULL,
 phase_number INT NOT NULL,
 created_at DATETIME NOT NULL,
 CONSTRAINT uq_phase_project_number UNIQUE (project_id, phase_number),
 CONSTRAINT uq_phase_generation UNIQUE (generation_id),
 CONSTRAINT fk_phase_project FOREIGN KEY (project_id) REFERENCES CustomerProject(id),
 CONSTRAINT fk_phase_generation FOREIGN KEY (generation_id) REFERENCES AIGeneration(id),
 CONSTRAINT chk_phase_positive CHECK (phase_number > 0)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS ShareLinkPhase (
 id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 share_link_id INT NOT NULL,
 phase_id INT NOT NULL,
 published_by INT NOT NULL,
 created_at DATETIME NOT NULL,
 CONSTRAINT uq_link_phase UNIQUE (share_link_id, phase_id),
 CONSTRAINT fk_phase_link FOREIGN KEY (share_link_id) REFERENCES ShareLink(id),
 CONSTRAINT fk_publication_phase FOREIGN KEY (phase_id) REFERENCES ProjectGenerationPhase(id),
 CONSTRAINT fk_phase_publisher FOREIGN KEY (published_by) REFERENCES User(id)
) ENGINE=InnoDB;
