"""Fresh-process startup regression: no database or provider access permitted."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

BACKEND = Path(__file__).resolve().parents[1]

class PaymentRegistrationTests(unittest.TestCase):
    def check_order(self, imports):
        script = '''
from unittest.mock import patch
from sqlalchemy.engine import Engine
from sqlalchemy.orm import configure_mappers
with patch.object(Engine, 'connect', side_effect=AssertionError('Startup must not connect')):
    IMPORTS
    from app.database.base import Base
    required = {'User', 'SubscriptionPlan', 'Subscription', 'CreditTransaction',
                'Payment', 'PaymentCheckout', 'PaymentWebhookEvent', 'PaidCreditAllocation'}
    assert required <= set(Base.metadata.tables), required - set(Base.metadata.tables)
    for name in required:
        for foreign_key in Base.metadata.tables[name].foreign_keys:
            assert foreign_key.column.table is Base.metadata.tables[foreign_key.column.table.name]
    configure_mappers()
    from app.core import stripe_test
    from app.services.payment_service import readiness
    from types import SimpleNamespace
    with patch.object(stripe_test, 'RELEASE_VERIFIED', False), patch.object(stripe_test, 'STRIPE_TEST_ENABLED', False):
        assert readiness(SimpleNamespace(role='owner'))['paid_activation_available'] is False
'''.replace('IMPORTS', imports)
        result = subprocess.run([sys.executable, '-c', script], cwd=BACKEND,
            env={**os.environ, 'PYTHONPATH': str(BACKEND)}, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_main_registers_all_payment_foreign_keys(self):
        self.check_order('import app.main')

    def test_payment_service_before_main_keeps_registration_complete(self):
        self.check_order('import app.services.payment_service\n    import app.main')

if __name__ == '__main__':
    unittest.main()
