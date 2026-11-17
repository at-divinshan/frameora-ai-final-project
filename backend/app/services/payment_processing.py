"""Provider verification outside transactions; atomic persistence inside repository.

This orchestration has no global provider and no access to payment credentials.
Production entry points must pass release/configuration/schema checks first.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from fastapi import HTTPException
from app.services.stripe_test_provider import SUPPORTED_EVENTS
from app.core.stripe_prices import checkout_metadata

@dataclass(frozen=True)
class VerifiedPayment:
    checkout_id: int
    session_id: str | None
    payment_intent_id: str
    amount_minor: int
    currency: str
    paid_at: datetime
    reversal: bool = False
    reversal_reason: str | None = None
    reversal_amount: int | None = None


def reject():
    raise HTTPException(409, 'Payment verification did not match the saved purchase.')


def checkout_reference(obj):
    metadata = obj.get('metadata')
    if not isinstance(metadata, dict): reject()
    value = metadata.get('checkout_id')
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or len(value) > 20:
        reject()
    identifier = int(value)
    if not 0 < identifier < 2**64: reject()
    return identifier


def verify_metadata(obj, purchase):
    expected = checkout_metadata(purchase)
    if obj.get('metadata') != expected: reject()


def verify_paid(provider, purchase, session_id):
    session=provider.retrieve('checkout/sessions',session_id)
    verify_metadata(session,purchase)
    if (session.get('livemode') is not False or session.get('mode')!='payment'
            or session.get('status')!='complete' or session.get('payment_status')!='paid'
            or session.get('client_reference_id')!=str(purchase.id)
            or session.get('amount_total')!=purchase.amount_minor or session.get('currency')!=purchase.currency
            or (purchase.provider_session_id and purchase.provider_session_id != session_id)):
        reject()
    provider.verify_line_items(session_id,purchase)
    intent=provider.retrieve('payment_intents',session.get('payment_intent'))
    verify_metadata(intent,purchase)
    if (intent.get('livemode') is not False or intent.get('status')!='succeeded'
            or intent.get('amount')!=purchase.amount_minor or intent.get('amount_received')!=purchase.amount_minor
            or intent.get('currency')!=purchase.currency): reject()
    charge=provider.retrieve('charges',intent.get('latest_charge'))
    if (charge.get('livemode') is not False or charge.get('payment_intent')!=intent['id']
            or charge.get('paid') is not True or charge.get('captured') is not True
            or charge.get('amount')!=purchase.amount_minor or charge.get('currency')!=purchase.currency): reject()
    try:
        paid_at=datetime.fromtimestamp(charge['created'],timezone.utc).replace(tzinfo=None)
        if paid_at < purchase.created_at or paid_at > purchase.expires_at: reject()
    except (KeyError,ValueError,TypeError,OverflowError): reject()
    # Missing reversal fields are unknown, not evidence that funds are intact.
    refunded = charge.get('amount_refunded')
    disputed = charge.get('disputed')
    if type(refunded) is not int or not 0 <= refunded <= purchase.amount_minor or type(disputed) is not bool:
        reject()
    reversed_payment = disputed or refunded > 0
    return VerifiedPayment(purchase.id,session_id,intent['id'],purchase.amount_minor,purchase.currency,
        paid_at,reversed_payment,'dispute' if charge.get('disputed') else 'partial_refund' if 0 < charge.get('amount_refunded',0) < purchase.amount_minor else 'refund' if reversed_payment else None, charge.get('amount_refunded',0) if reversed_payment else None)


def process_event(event, raw, repository, provider):
    kind=event['type']
    if kind not in SUPPORTED_EVENTS:
        return {'received':True,'outcome':'ignored'}
    obj=event['data']['object']
    if kind.startswith('checkout.session.'):
        # Event metadata is a lookup hint only; authoritative objects are fetched next.
        checkout_id=checkout_reference(obj)
        purchase=repository.get_purchase(checkout_id)
        verified=verify_paid(provider,purchase,obj.get('id'))
    else:
        reversal=provider.retrieve('refunds' if kind.startswith('refund.') else 'disputes',obj.get('id'))
        charge=provider.retrieve('charges',reversal.get('charge'))
        if charge.get('livemode') is not False: reject()
        intent=provider.retrieve('payment_intents',charge.get('payment_intent'))
        if intent.get('livemode') is not False: reject()
        checkout_id=checkout_reference(intent)
        purchase=repository.get_purchase(checkout_id)
        verify_metadata(intent,purchase)
        if (charge.get('amount')!=purchase.amount_minor or charge.get('currency')!=purchase.currency
                or intent.get('amount')!=purchase.amount_minor or intent.get('currency')!=purchase.currency
                or reversal.get('currency')!=purchase.currency): reject()
        if kind.startswith('refund.'):
            if reversal.get('status')!='succeeded': return {'received':True,'outcome':'not_succeeded'}
            if not 0 < reversal.get('amount',0) <= purchase.amount_minor: reject()
        elif reversal.get('status') == 'won':
            # Never regrant automatically on dispute closure. Existing revocation stays.
            return {'received':True,'outcome':'manual_review'}
        verified=VerifiedPayment(purchase.id,purchase.provider_session_id,intent['id'],purchase.amount_minor,
            purchase.currency,purchase.verified_at or purchase.created_at,True,
            ('partial_refund' if reversal['amount'] < purchase.amount_minor else 'refund') if kind.startswith('refund.') else 'dispute',
            reversal.get('amount'))
    return repository.apply_event(event,sha256(raw).digest(),verified)


def start_checkout(repository, provider, user, request):
    purchase=repository.reserve_purchase(user,request)
    if purchase.state not in ('pending','open'):
        raise HTTPException(409,'This purchase is already finalized. Refresh your subscription.')
    if purchase.provider_session_id:
        session=provider.retrieve('checkout/sessions',purchase.provider_session_id)
    else:
        session=provider.create_checkout(purchase)
    if (session.get('livemode') is not False or session.get('status')!='open'
            or session.get('mode') != 'payment'
            or session.get('client_reference_id') != str(purchase.id)
            or session.get('amount_total') != purchase.amount_minor
            or session.get('currency') != purchase.currency):
        raise HTTPException(409,'Checkout has ended. Refresh your subscription before retrying.')
    verify_metadata(session,purchase)
    provider.verify_line_items(session['id'],purchase)
    from urllib.parse import urlparse
    url=urlparse(session.get('url',''))
    if url.scheme!='https' or url.hostname!='checkout.stripe.com' or url.username or url.password: reject()
    repository.bind_session(purchase,session['id'])
    return {'checkout_url':session['url'],'checkout_id':purchase.id,'mode':'test'}
