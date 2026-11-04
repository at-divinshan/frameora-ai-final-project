"""Static checks for proposal-only migration 005; never execute its SQL."""

from pathlib import Path
import re
import unittest


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "005_free_generation_allowance.sql"
)


class FreeGenerationMigrationTests(unittest.TestCase):
    def setUp(self):
        self.raw_sql = MIGRATION.read_text()
        self.sql = re.sub(r"(?m)^\s*--.*$", "", self.raw_sql)

    def test_migration_only_adds_one_new_allowance_table(self):
        statements = [
            statement.strip()
            for statement in self.sql.split(";")
            if statement.strip() and not statement.strip().startswith("--")
        ]
        executable = [
            statement
            for statement in statements
            if re.search(r"\b(?:CREATE|ALTER|DROP|INSERT|UPDATE|DELETE)\b", statement, re.I)
        ]
        self.assertEqual(len(executable), 1)
        self.assertRegex(
            executable[0],
            r"(?is)^CREATE\s+TABLE\s+`FreeGenerationAllowance`\s*\(",
        )
        self.assertNotRegex(
            executable[0],
            r"(?i)\b(?:IF\s+NOT\s+EXISTS|ALTER|DROP|INSERT|UPDATE|DELETE)\b",
        )

    def test_account_identity_and_one_generation_are_constrained(self):
        self.assertRegex(self.sql, r"(?i)PRIMARY\s+KEY\s*\(`user_id`\)")
        self.assertRegex(
            self.sql,
            r"(?is)UNIQUE\s+KEY\s+`m005_uq_free_generation_id`\s*\(`generation_id`\)",
        )
        self.assertRegex(
            self.sql,
            r"(?is)FOREIGN\s+KEY\s*\(`user_id`\)\s*REFERENCES\s+`User`\s*\(`id`\)",
        )
        self.assertRegex(
            self.sql,
            r"(?is)FOREIGN\s+KEY\s*\(`generation_id`\)\s*REFERENCES\s+`AIGeneration`\s*\(`id`\)",
        )
        self.assertRegex(
            self.sql,
            r"(?is)KEY\s+`m005_ix_free_generation_state_reserved`\s*\(`state`,\s*`reserved_at`\)",
        )

    def test_state_check_covers_available_reserved_and_consumed(self):
        for state in ("available", "reserved", "consumed"):
            self.assertIn(f"`state` = '{state}'", self.sql)
        self.assertRegex(
            self.sql,
            r"(?is)CHECK\s*\(.*`state`\s*=\s*'available'.*`state`\s*=\s*'reserved'.*`state`\s*=\s*'consumed'.*\)",
        )

    def test_migration_is_explicitly_proposal_only_and_additive(self):
        self.assertIn("PROPOSAL ONLY", self.raw_sql)
        self.assertIn("Do not execute automatically", self.raw_sql)
        self.assertIn("No existing accounts or generations are modified", self.raw_sql)
        self.assertIn("ENGINE=InnoDB", self.sql)


if __name__ == "__main__":
    unittest.main()
