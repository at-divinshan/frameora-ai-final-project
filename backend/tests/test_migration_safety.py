"""Static migration checks plus portable SELECT predicate tests on in-memory SQLite.
These tests NEVER execute either migration and do not prove MySQL DDL compatibility.
"""
import hashlib
from pathlib import Path
import re
import sqlite3
import unittest

MIGRATIONS = Path(__file__).resolve().parents[1] / 'migrations'

class MigrationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.sql = (MIGRATIONS / '003_owner_subscriptions.sql').read_text()
        self.query = re.search(r'IF EXISTS \((SELECT 1 FROM `UserProfile` p LEFT JOIN `User` u ON u.id = p.user_id\s+WHERE u.id IS NULL)\) THEN', self.sql).group(1)
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('CREATE TABLE User(id INTEGER PRIMARY KEY, role TEXT); CREATE TABLE UserProfile(id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, studio_name TEXT, onboarding_status TEXT, onboarding_completed_at TEXT);')
        self.db.executemany('INSERT INTO User VALUES (?,?)', [(i, 'user' if i <= 4 else 'owner' if i <= 7 else 'admin') for i in range(1,9)])
    def tearDown(self):
        self.db.close()
    def test_zero_one_and_three_existing_profiles_accepted_without_writes(self):
        for count in range(4):
            if count:
                self.db.execute('INSERT INTO UserProfile VALUES (?,?,?,?,?)', (count,count+4,'Synthetic Studio '+str(count),'pending_plan',None))
            before=list(self.db.iterdump())
            self.assertEqual(self.db.execute(self.query).fetchall(), [])
            self.assertEqual(list(self.db.iterdump()),before)
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM User').fetchone()[0],8)
    def test_orphan_profile_stops_without_repairing_data(self):
        # Intentionally invalid disposable fixture; checks the new SELECT only.
        self.db.execute("INSERT INTO UserProfile VALUES (1,99,'Synthetic orphan','pending_studio',NULL)")
        before=list(self.db.iterdump())
        self.assertTrue(self.db.execute(self.query).fetchall())
        self.assertEqual(list(self.db.iterdump()),before)
    def test_only_profile_preflight_changed(self):
        new="""    -- Existing profiles are allowed: Studio Setup may already have saved pending_plan.
    -- The exact UserProfile schema, UNIQUE user_id and same-database FK were checked above.
    -- Preserve every profile field and timestamp; never require deleting profiles to migrate.
    IF EXISTS (SELECT 1 FROM `UserProfile` p LEFT JOIN `User` u ON u.id = p.user_id
               WHERE u.id IS NULL) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: orphan profile reference; separate data review required';
    END IF;"""
        old="""    IF (SELECT COUNT(*) FROM `User` u LEFT JOIN `UserProfile` p ON p.user_id = u.id
        WHERE u.role = 'owner' AND p.id IS NULL) <> 3 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '003: owner profile baseline changed';
    END IF;"""
        self.assertEqual(self.sql.count(new),1)
        # Recorded pre-edit digest: every other role/FK/index/credit/plan guard and DDL
        # statement is byte-for-byte unchanged by this targeted safety correction.
        self.assertEqual(hashlib.sha256(self.sql.replace(new,old).encode()).hexdigest(),
                         '791d8c48e42b2991404f90ea00691c76f72d3b0e6a258000f97e5f9fcfb50e97')
    def test_photo_migration_unchanged_and_order_dependency_explicit(self):
        photo=(MIGRATIONS/'004_studio_photo.sql').read_bytes()
        self.assertEqual(hashlib.sha256(photo).hexdigest(),'d05ee738c72c5b969099d32c8dc0b770be924551f735d44a579c2e83b6e9b3e7')
        self.assertIn('003: UserProfile column definition mismatch',self.sql)
        self.assertNotIn('studio_photo',self.sql)
        self.assertIn(b'ADD COLUMN `studio_photo`',photo)
