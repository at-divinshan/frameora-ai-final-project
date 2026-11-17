"""Stripe Test Mode orchestration, hard-disabled pending user-managed v4 rollout.

Database deployment alone must NOT enable payments. The prepared implementation
requires schema, configuration and deployment-test verification before release.
"""
from dataclasses import dataclass
from fastapi import HTTPException
from app.core.stripe_prices import paid_plan

@dataclass(frozen=True)
class CheckoutIntent:
    user_id: int
    plan_code: str
    currency: str
    amount_minor: int
    credits: int
    idempotency_key: str
    mode: str = 'payment'  # Explicit monthly purchase; never auto-renewing billing.
    test_mode: bool = True


def prepare_intent(user, request):
    plan = paid_plan(user.role, request.plan_code)
    return CheckoutIntent(user.id, plan.code, plan.currency.lower(), plan.amount_minor,
                          plan.credits, request.idempotency_key)


def readiness(user):
    if user.role not in ('owner', 'user'):
        raise HTTPException(403, 'Payments are unavailable for this role.')
    from app.core import stripe_test
    config = stripe_test.configuration()
    blockers = []
    configuration_valid = True
    try:
        config.validate()
    except HTTPException:
        configuration_valid = False
        blockers.append('test_configuration_invalid_or_missing')
    if not stripe_test.STRIPE_TEST_ENABLED:
        blockers.append('stripe_test_mode_disabled')
    if not stripe_test.RELEASE_VERIFIED:
        blockers.append('deployment_verification_not_approved')
    # RELEASE_VERIFIED attests to schema and deployment tests, not merely credentials.
    # This read-only endpoint does not inspect live schema or verify Stripe objects.
    available = (configuration_valid and stripe_test.RELEASE_VERIFIED
                 and stripe_test.STRIPE_TEST_ENABLED and config.enabled)
    return {'provider': 'stripe', 'mode': 'test', 'checkout_available': available,
            'paid_activation_available': available, 'blockers': blockers,
            'configuration_valid': configuration_valid,
            'release_verified': stripe_test.RELEASE_VERIFIED,
            'schema_checked': False,
            'verification_required': [
                'Verify the required payment schema and role-specific plan catalogue.',
                'Verify test prices, signed webhooks, fulfillment, refunds and idempotency.',
                'Approve deployment verification before enabling either payment gate.',
            ] if not stripe_test.RELEASE_VERIFIED else []}


def runtime(db):
    from app.core.stripe_test import require_release
    from app.services.payment_schema import require_payment_schema
    from app.services.stripe_test_provider import StripeTestProvider
    from app.repositories.payment_repository import PaymentRepository
    config = require_release()
    if db is None: raise HTTPException(503, 'Payment database is unavailable.')
    require_payment_schema(db)
    return PaymentRepository(db), StripeTestProvider(config), config


def checkout(user, request, db=None):
    prepare_intent(user, request)
    repository, provider, _ = runtime(db)
    from app.services.payment_processing import start_checkout
    return start_checkout(repository, provider, user, request)


def receive_webhook(raw=b'', signature='', db=None):
    from app.core.stripe_test import require_release
    from app.services.stripe_test_provider import verify_event
    from app.services.payment_processing import process_event
    config = require_release()
    event = verify_event(raw, signature, config.webhook_secret)

    def apply(session):
        repository, provider, _ = runtime(session)
        return process_event(event, raw, repository, provider)

    if db is not None:
        return apply(db)
    # Even session creation waits until the bounded payload has a valid signature.
    from app.database.connection import SessionLocal
    with SessionLocal() as session:
        return apply(session)
