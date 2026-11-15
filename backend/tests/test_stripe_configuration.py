"""Configuration/readiness checks: synthetic credentials, no DB or network."""
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from app.core import config, stripe_test
from app.services import payment_service

VALUES = {
    'STRIPE_TEST_SECRET_KEY': 'sk_test_fixture_only',
    'STRIPE_TEST_WEBHOOK_SECRET': 'whsec_fixture_only',
    'STRIPE_TEST_FRONTEND_ORIGIN': 'http://localhost:5173',
}

class StripeConfigurationTests(unittest.TestCase):
    def setUp(self):
        # Test gate behavior independently of deployment approval.
        for name in ('RELEASE_VERIFIED', 'STRIPE_TEST_ENABLED'):
            gate=patch.object(stripe_test,name,False);gate.start();self.addCleanup(gate.stop)
        env=patch.dict(os.environ,{},clear=True);env.start();self.addCleanup(env.stop)
        file=patch.object(config,'dotenv_values',return_value=VALUES.copy())
        self.file=file.start();self.addCleanup(file.stop)

    def test_backend_dotenv_is_loaded_without_interpolation(self):
        value=stripe_test.configuration()
        value.validate()
        self.assertEqual(value.secret_key,VALUES['STRIPE_TEST_SECRET_KEY'])
        self.file.assert_called_once_with(Path(config.__file__).resolve().parents[2]/'.env',interpolate=False)
        self.assertNotIn(value.secret_key,repr(value))
        self.assertNotIn(value.webhook_secret,repr(value))

    def test_environment_wins_including_empty_values(self):
        with patch.dict(os.environ,{'STRIPE_TEST_SECRET_KEY':'sk_test_environment_only'}):
            self.assertEqual(stripe_test.configuration().secret_key,'sk_test_environment_only')
        with patch.dict(os.environ,{'STRIPE_TEST_SECRET_KEY':''}):
            with self.assertRaises(HTTPException): stripe_test.configuration().validate()

    def test_env_cannot_enable_gates(self):
        with patch.dict(os.environ,{'STRIPE_TEST_ENABLED':'true','RELEASE_VERIFIED':'true'}):
            self.assertFalse(stripe_test.configuration().enabled)
            self.assertFalse(stripe_test.RELEASE_VERIFIED)
            with self.assertRaises(HTTPException): stripe_test.require_release()

    def test_live_missing_and_malformed_config_fail_safely(self):
        for name,value in [('STRIPE_TEST_SECRET_KEY','sk_live_fixture'),
                           ('STRIPE_TEST_WEBHOOK_SECRET',''),
                           ('STRIPE_TEST_FRONTEND_ORIGIN','https://[broken'),
                           ('STRIPE_TEST_FRONTEND_ORIGIN','https://example.invalid:bad')]:
            with self.subTest(name=name,value=value),patch.dict(os.environ,{name:value}):
                with self.assertRaises(HTTPException) as error: stripe_test.configuration().validate()
                self.assertNotIn(value or 'whsec_fixture_only',error.exception.detail)

    def test_readiness_both_roles_all_gate_combinations(self):
        # Patch gates only inside tests; source defaults remain false.
        for role in ('user','owner'):
            for release,enabled in ((False,False),(False,True),(True,False),(True,True)):
                with patch.object(stripe_test,'RELEASE_VERIFIED',release),patch.object(stripe_test,'STRIPE_TEST_ENABLED',enabled):
                    result=payment_service.readiness(SimpleNamespace(role=role))
                    self.assertEqual(result['checkout_available'],release and enabled)
                    self.assertEqual(result['paid_activation_available'],release and enabled)
                    self.assertTrue(result['configuration_valid'])
                    self.assertFalse(result['schema_checked'])
                    self.assertEqual('deployment_verification_not_approved' in result['blockers'],not release)
                    self.assertEqual('stripe_test_mode_disabled' in result['blockers'],not enabled)
                    self.assertNotIn('fixture',str(result))

    def test_invalid_configuration_blocks_even_with_mock_approved_gates(self):
        self.file.return_value={}
        with patch.object(stripe_test,'RELEASE_VERIFIED',True),patch.object(stripe_test,'STRIPE_TEST_ENABLED',True):
            for role in ('user','owner'):
                result=payment_service.readiness(SimpleNamespace(role=role))
                self.assertFalse(result['checkout_available'])
                self.assertFalse(result['paid_activation_available'])
                self.assertEqual(result['blockers'],['test_configuration_invalid_or_missing'])

    def test_unauthorized_roles_rejected_before_configuration(self):
        for role in ('admin','guest',''):
            with self.assertRaises(HTTPException) as error:
                payment_service.readiness(SimpleNamespace(role=role))
            self.assertEqual(error.exception.status_code,403)
        self.file.assert_not_called()

    def test_readiness_never_initializes_payment_runtime(self):
        with patch.object(payment_service,'runtime',side_effect=AssertionError('No DB/provider')):
            for role in ('user','owner'):
                result=payment_service.readiness(SimpleNamespace(role=role))
                self.assertFalse(result['checkout_available'])
                self.assertEqual(result['blockers'],['stripe_test_mode_disabled','deployment_verification_not_approved'])
