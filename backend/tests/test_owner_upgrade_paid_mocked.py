"""Conversion policy tests: mocked persistence only."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from fastapi import HTTPException
from app.services import owner_upgrade_service as service


class PaidUpgradeTests(TestCase):
    def run_conversion(self, role="user", paid=None, proof_error=None):
        db = Mock()
        db.scalar.return_value = paid
        user = SimpleNamespace(id=9, role=role)
        with patch.object(service, "require_jwt_configuration"), patch.object(
            service, "lock_profile", return_value=user
        ), patch.object(service, "proof", side_effect=proof_error) as proof, patch.object(
            service, "find_owner_profile", return_value=SimpleNamespace()
        ), patch.object(service, "auth_versions_enabled", return_value=False), patch.object(
            service, "issue_session", return_value="session"
        ):
            try:
                result = service.convert_to_owner(db, user, False)
            except HTTPException as exc:
                result = exc
        return db, user, proof, result

    def test_active_paid_plans_block_before_mutation(self):
        for plan in ("starter", "pro"):
            with self.subTest(plan=plan):
                paid = SimpleNamespace(plan_kind=plan, end_date=datetime.utcnow()+timedelta(days=1))
                db, user, proof, result = self.run_conversion(paid=paid)
                self.assertEqual(result.status_code, 409)
                self.assertEqual(user.role, "user")
                proof.assert_called_once()
                db.commit.assert_not_called()
                db.flush.assert_not_called()
                db.add.assert_not_called()

    def test_expired_and_free_allow_conversion_query_excludes_expired(self):
        db, user, proof, result = self.run_conversion()
        self.assertEqual(result, "session")
        self.assertEqual(user.role, "owner")
        query = db.scalar.call_args.args[0]
        sql = str(query.whereclause)
        self.assertIn('"Subscription".end_date >', sql)
        self.assertIsNotNone(query._for_update_arg)
        self.assertIn('active', query.whereclause.compile().params.values())
        proof.assert_not_called()
        db.commit.assert_called_once()

    def test_unverifiable_allocation_fails_closed(self):
        db, user, _, result = self.run_conversion(
            paid=SimpleNamespace(), proof_error=HTTPException(503, "Unavailable"))
        self.assertEqual(result.status_code, 503)
        self.assertEqual(user.role, "user")
        db.commit.assert_not_called()

    def test_admin_rejected_existing_owner_preserved(self):
        db, _, _, result = self.run_conversion(role="admin")
        self.assertEqual(result.status_code, 403)
        db.scalar.assert_not_called()
        db, user, _, result = self.run_conversion(role="owner")
        self.assertEqual(user.role, "owner")
        self.assertEqual(result, "session")
        db.scalar.assert_not_called()
