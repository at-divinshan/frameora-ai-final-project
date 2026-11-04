"""SQLite-only tests for the free-generation reservation foundation."""

from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import event, inspect, select
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

import test_privacy
from app.models.ai_generation import AIGeneration
from app.models.free_generation_allowance import FreeGenerationAllowance
from app.models.photography_plan import PhotographyPlan
from app.models.user import User
from app.services import free_generation_service


class FreeGenerationTests(TestCase):
    auth = test_privacy.PrivacyTests.auth

    def setUp(self):
        test_privacy.PrivacyTests.setUp(self)
        PhotographyPlan.__table__.create(self.engine)
        AIGeneration.__table__.create(self.engine)
        FreeGenerationAllowance.__table__.create(self.engine)
        with Session(self.engine) as db:
            db.add(
                PhotographyPlan(
                    id=1,
                    user_id=1,
                    photography_type="Portrait",
                    people_count=1,
                    environment="Outdoor",
                )
            )
            db.commit()
        self.headers = self.auth(1)

    def tearDown(self):
        test_privacy.PrivacyTests.tearDown(self)

    def test_eligibility_is_read_only_and_missing_allowance_is_available(self):
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            statements.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            response = self.client.get(
                "/ai/free-generation/eligibility", headers=self.headers
            )
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(
            response.json(),
            {"free_request_status": "available", "free_request_available": True},
        )
        self.assertFalse(
            any(
                statement.lstrip().split()[0].upper() in ("INSERT", "UPDATE", "DELETE")
                for statement in statements
            )
        )

    def test_failed_attempt_releases_reservation_and_does_not_consume_allowance(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)
            reservation = free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard"
            )
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "in_progress",
            )
            free_generation_service.release_failed_request(
                db, user, reservation=reservation
            )
            generation = db.get(AIGeneration, reservation.generation_id)
            self.assertEqual(generation.status, "failed")
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "available",
            )
            retry = free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard"
            )
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "in_progress",
            )
            free_generation_service.release_failed_request(
                db, user, reservation=retry
            )

    def test_second_reservation_is_rejected_while_first_is_in_progress(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)
            first = free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard"
            )
            with self.assertRaises(HTTPException) as raised:
                free_generation_service.reserve_free_request(
                    db, user, plan_id=1, quality="standard"
                )
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "in_progress",
            )
            free_generation_service.release_failed_request(
                db, user, reservation=first
            )

    def test_only_successful_generation_consumes_allowance_permanently(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)
            reservation = free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard", guidance_text="test-only"
            )
            generation = db.get(AIGeneration, reservation.generation_id)
            generation.status = "completed"
            generation.completed_at = datetime(2026, 11, 4, 12)
            db.commit()

            free_generation_service.complete_free_request(
                db, user, reservation=reservation
            )
            free_generation_service.complete_free_request(
                db, user, reservation=reservation
            )
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "used",
            )
            with self.assertRaises(HTTPException) as raised:
                free_generation_service.reserve_free_request(
                    db, user, plan_id=1, quality="standard"
                )
            self.assertEqual(raised.exception.status_code, 409)

    def test_interrupted_terminal_requests_reconcile_without_releasing_active_work(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)

            failed = free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard"
            )
            failed_generation = db.get(AIGeneration, failed.generation_id)
            failed_generation.status = "failed"
            db.commit()
            self.assertEqual(
                free_generation_service.reconcile_interrupted_request(
                    db, user_id=user.id
                ),
                "available",
            )

            completed = free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard"
            )
            completed_generation = db.get(AIGeneration, completed.generation_id)
            completed_generation.status = "completed"
            completed_generation.completed_at = datetime(2026, 11, 4, 12)
            db.commit()
            self.assertEqual(
                free_generation_service.reconcile_interrupted_request(
                    db, user_id=user.id
                ),
                "used",
            )
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "used",
            )

    def test_interrupted_nonterminal_request_remains_reserved(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)
            free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard"
            )
            self.assertEqual(
                free_generation_service.reconcile_interrupted_request(
                    db, user_id=user.id
                ),
                "in_progress",
            )
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "in_progress",
            )

    def test_unsuccessful_generation_cannot_complete_reservation(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)
            reservation = free_generation_service.reserve_free_request(
                db, user, plan_id=1, quality="standard"
            )
            generation = db.get(AIGeneration, reservation.generation_id)
            generation.status = "failed"
            generation.completed_at = None
            db.commit()
            with self.assertRaises(HTTPException) as raised:
                free_generation_service.complete_free_request(
                    db, user, reservation=reservation
                )
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(
                free_generation_service.eligibility(db, user)["free_request_status"],
                "in_progress",
            )

    def test_cross_account_plan_and_roles_are_rejected(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)
            with self.assertRaises(HTTPException) as raised:
                free_generation_service.reserve_free_request(
                    db, user, plan_id=999, quality="standard"
                )
            self.assertEqual(raised.exception.status_code, 404)
            owner = db.get(User, 2)
            with self.assertRaises(HTTPException) as raised:
                free_generation_service.eligibility(db, owner)
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(
                self.client.get(
                    "/ai/free-generation/eligibility", headers=self.auth(2)
                ).status_code,
                403,
            )

    def test_missing_proposal_table_fails_closed_without_creating_it(self):
        FreeGenerationAllowance.__table__.drop(self.engine)
        response = self.client.get(
            "/ai/free-generation/eligibility", headers=self.headers
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("migration", response.json()["detail"])
        self.assertFalse(inspect(self.engine).has_table("FreeGenerationAllowance"))

    def test_reservation_serializes_on_account_row(self):
        with Session(self.engine) as db:
            user = db.get(User, 1)
            calls = []
            original_lock_profile = free_generation_service.lock_profile
            original_allowance = free_generation_service._allowance
            with patch.object(
                free_generation_service,
                "lock_profile",
            ) as locked:
                locked.side_effect = lambda *args: (
                    calls.append("user"),
                    original_lock_profile(*args),
                )[1]
                with patch.object(
                    free_generation_service,
                    "_allowance",
                ) as allowance:
                    allowance.side_effect = lambda *args, **kwargs: (
                        calls.append("allowance"),
                        original_allowance(*args, **kwargs),
                    )[1]
                    free_generation_service.reserve_free_request(
                        db, user, plan_id=1, quality="standard"
                    )
            locked.assert_called_once_with(db, user.id)
            self.assertEqual(calls, ["user", "allowance"])

    def test_mysql_allowance_query_uses_row_lock(self):
        db = MagicMock()
        free_generation_service._allowance(db, 1, lock=True)
        statement = db.scalar.call_args.args[0]
        self.assertIn("FOR UPDATE", str(statement.compile(dialect=mysql.dialect())))

    def test_historical_successful_generations_do_not_consume_free_allowance(self):
        with Session(self.engine) as db:
            db.add(
                AIGeneration(
                    user_id=1,
                    plan_id=1,
                    quality="standard",
                    status="completed",
                    completed_at=datetime(2026, 1, 1),
                )
            )
            db.commit()
            self.assertEqual(
                free_generation_service.eligibility(db, db.get(User, 1))[
                    "free_request_status"
                ],
                "available",
            )
