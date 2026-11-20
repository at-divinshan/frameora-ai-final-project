"""Mock/SQL compilation only. No database or provider access."""
import unittest
from datetime import datetime
from unittest.mock import Mock, patch
from types import SimpleNamespace
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, Response
from app.services import admin_analytics_service as service
from app.routers.admin import router
from app.core.dependencies import get_current_user
from app.database.connection import get_db

class AnalyticsTests(unittest.TestCase):
    def test_payment_query_is_verified_deduplicated_and_not_webhook_based(self):
        query = service.queries(datetime(2026, 1, 1))['payments'].compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True})
        sql = str(query)
        for condition in ["'succeeded'", "'fulfilled'", 'livemode IS false', 'verified_at IS NOT NULL', 'revoked_at IS NULL', 'EXISTS', 'amount_minor', 'subscription_id']:
            self.assertIn(condition, sql)
        self.assertNotIn('PaymentWebhookEvent', sql)
        self.assertEqual(sql.count('FROM `Payment`'), 1)

    def test_expired_periods_and_failed_images_excluded(self):
        queries = service.queries(datetime(2026, 1, 1))
        sql = str(queries['subscriptions'].compile(compile_kwargs={'literal_binds': True}))
        for text in ["'active'", 'end_date >', 'start_date <=', 'end_date IS NULL']:
            self.assertIn(text, sql)
        self.assertIn("'completed'", str(queries['images'].compile(compile_kwargs={'literal_binds': True})))
        self.assertIn('project_id IS NULL', str(queries['projects']))

    def test_empty_values_and_unavailable_are_distinct(self):
        db = Mock(); db.scalar.return_value = 0
        db.execute.return_value.mappings.return_value.all.return_value = []
        result = service.analytics(db)
        self.assertEqual(result['payments'], 0)
        self.assertEqual(result['payment_trend'], [])
        db.commit.assert_not_called(); db.add.assert_not_called()
        db.scalar.side_effect = SQLAlchemyError('unavailable')
        self.assertIsNone(service.analytics(db)['payments'])

    def test_chart_results_and_decimal_total_preserved(self):
        from decimal import Decimal
        db = Mock(); db.scalar.return_value = Decimal('1990.00')
        db.execute.return_value.mappings.return_value.all.return_value = [{'month':'2026-02','value':Decimal('1500')}, {'month':'2026-01','value':Decimal('490')}]
        result = service.analytics(db)
        self.assertEqual(result['revenue'], Decimal('1990.00'))
        self.assertEqual(result['payment_trend'][0]['month'], '2026-01')

    def test_admin_only_and_no_store(self):
        route = next(route for route in router.routes if route.path == '/admin/analytics')
        authorize = route.dependant.dependencies[0].call
        for role in ('user', 'owner'):
            with self.assertRaises(HTTPException) as error:
                authorize(SimpleNamespace(role=role))
            self.assertEqual(error.exception.status_code, 403)
        admin = SimpleNamespace(role='admin')
        self.assertIs(authorize(admin), admin)
        response = Response()
        route.dependant.dependencies[1].call(response)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        with patch.object(service, 'analytics', return_value={'users': 0}) as read:
            db = Mock()
            self.assertEqual(route.endpoint(db), {'users': 0})
            read.assert_called_once_with(db)

    def test_image_trend_uses_completed_records_and_completion_timestamp(self):
        sql = str(service.queries(datetime(2026, 1, 1))['image_trend'].compile(dialect=mysql.dialect(), compile_kwargs={'literal_binds': True}))
        for text in ["'completed'", "'ai_generated'", 'completed_at IS NOT NULL', 'GROUP BY', 'LIMIT 12', '`MediaAsset`.user_id = `AIGeneration`.user_id']:
            self.assertIn(text, sql)
        self.assertNotIn('CreditTransaction', sql)
        db = Mock(); db.scalar.return_value = 0
        db.execute.return_value.mappings.return_value.all.return_value = [{'month': '2026-02', 'value': 8}, {'month': '2026-01', 'value': 4}]
        self.assertEqual(service.analytics(db)['image_trend'], [{'month': '2026-01', 'value': 4}, {'month': '2026-02', 'value': 8}])
        db.execute.side_effect = SQLAlchemyError('missing source')
        self.assertIsNone(service.analytics(db)['image_trend'])
        db.commit.assert_not_called()
