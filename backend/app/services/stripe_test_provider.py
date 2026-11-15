"""Bounded Stripe HTTP adapter and raw-body signature verification; no implicit calls."""
import hashlib
import hmac
import json
import re
import time
from datetime import timezone
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException
from app.core.stripe_test import API_VERSION
from app.core.stripe_prices import purchase_plan, checkout_metadata

MAX_WEBHOOK_BYTES = 262144
SUPPORTED_EVENTS = frozenset(('checkout.session.completed', 'checkout.session.async_payment_succeeded',
    'refund.created', 'refund.updated', 'charge.dispute.created', 'charge.dispute.closed'))

def verify_event(raw, signature, secret, *, now=None):
    if not secret.startswith('whsec_'):
        raise HTTPException(503, 'Webhook configuration is unavailable.')
    if len(raw) > MAX_WEBHOOK_BYTES:
        raise HTTPException(413, 'Webhook is too large.')
    try:
        parts = [part.split('=', 1) for part in signature.split(',')]
        stamps = [v for k, v in parts if k == 't']
        signatures = [v for k, v in parts if k == 'v1']
        if len(stamps) != 1 or not stamps[0].isdigit(): raise ValueError()
        stamp = int(stamps[0])
        if abs((time.time() if now is None else now) - stamp) > 300: raise ValueError()
        expected = hmac.new(secret.encode(), stamps[0].encode() + b'.' + raw, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, value) for value in signatures): raise ValueError()
        def unique_object(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj: raise ValueError()
                obj[key] = value
            return obj
        event = json.loads(raw, object_pairs_hook=unique_object)
        if (not isinstance(event, dict) or event.get('livemode') is not False
                or not re.fullmatch(r'evt_[A-Za-z0-9]+', event.get('id', ''))
                or not isinstance(event.get('type'), str)
                or not isinstance(event.get('data', {}).get('object'), dict)):
            raise ValueError()
        return event
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise HTTPException(400, 'Invalid webhook signature or payload.') from None

class StripeTestProvider:
    def __init__(self, config, transport=None):
        config.validate()
        self.config, self.transport = config, transport

    def request(self, method, path, *, data=None, key=None):
        headers = {'Authorization': 'Bearer ' + self.config.secret_key, 'Stripe-Version': API_VERSION}
        if key: headers['Idempotency-Key'] = key
        try:
            with httpx.Client(base_url='https://api.stripe.com/v1/', timeout=15,
                              follow_redirects=False, trust_env=False, transport=self.transport) as client:
                response = client.request(method, path, data=data, headers=headers)
                response.raise_for_status()
                obj = response.json()
            if not isinstance(obj, dict) or obj.get('livemode') is True:
                raise ValueError()
            return obj
        except httpx.HTTPStatusError as error:
            # Never return provider bodies: they can contain request data or secrets.
            status = error.response.status_code
            if status in (401, 403):
                detail = 'Stripe rejected the test credentials or permissions. Contact the administrator.'
            elif status == 404:
                detail = 'The Stripe test resource was not found. Verify the configured sandbox and Price IDs.'
            elif status == 429:
                detail = 'Stripe is rate limiting requests. Wait before retrying.'
            elif 400 <= status < 500:
                detail = 'Stripe rejected the payment request. An administrator must inspect the Stripe request log before retrying.'
            else:
                detail = 'Stripe Test Mode is temporarily unavailable. Retry later with the same purchase.'
            raise HTTPException(502, detail) from None
        except httpx.RequestError:
            raise HTTPException(502, 'Unable to reach Stripe Test Mode. Check backend connectivity and retry with the same purchase.') from None
        except ValueError:
            raise HTTPException(502, 'Stripe returned an invalid test-mode response. Payment verification was stopped.') from None

    def retrieve(self, kind, identifier):
        prefixes = {'checkout/sessions':'cs_test_', 'payment_intents':'pi_', 'charges':'ch_',
                    'refunds':'re_', 'disputes':'dp_', 'prices':'price_'}
        if kind not in prefixes or not isinstance(identifier, str) or not re.fullmatch(re.escape(prefixes[kind]) + r'[A-Za-z0-9]+', identifier):
            raise HTTPException(400, 'Invalid payment reference.')
        result = self.request('GET', f'{kind}/{identifier}')
        if result.get('id') != identifier:
            raise HTTPException(409, 'Payment reference mismatch.')
        return result

    def validate_price(self, price, purchase, *, active=False):
        plan=purchase_plan(purchase)
        if (price.get('id')!=plan.price_id or price.get('livemode') is not False
                or price.get('currency')!=plan.currency or price.get('unit_amount')!=plan.amount_minor
                or price.get('type')!='one_time' or price.get('recurring') is not None
                or price.get('billing_scheme')!='per_unit' or price.get('custom_unit_amount') is not None
                or price.get('transform_quantity') is not None or (active and price.get('active') is not True)):
            raise HTTPException(409,'Configured test Price must match the approved one-time plan.')

    def verify_line_items(self, session_id, purchase):
        if not re.fullmatch(r'cs_test_[A-Za-z0-9]+', session_id):
            raise HTTPException(400,'Invalid checkout reference.')
        items=self.request('GET',f'checkout/sessions/{session_id}/line_items')
        rows=items.get('data')
        if items.get('has_more') is not False or not isinstance(rows,list) or len(rows)!=1:
            raise HTTPException(409,'Unexpected checkout line items.')
        item=rows[0]
        if (item.get('quantity')!=1 or item.get('currency')!=purchase.currency
                or item.get('amount_total')!=purchase.amount_minor or item.get('amount_subtotal')!=purchase.amount_minor
                or item.get('amount_discount',0)!=0 or item.get('amount_tax',0)!=0):
            raise HTTPException(409,'Checkout line amount mismatch.')
        self.validate_price(item.get('price',{}),purchase)

    def create_checkout(self, purchase):
        origin = self.config.frontend_origin.rstrip('/')
        plan=purchase_plan(purchase)
        self.validate_price(self.retrieve('prices',plan.price_id),purchase,active=True)
        metadata = checkout_metadata(purchase)
        # Payment methods are managed by the Stripe Sandbox Dashboard.
        data = {'mode':'payment',
            'client_reference_id':str(purchase.id), 'success_url':origin+'/'+plan.role+'/subscription?payment=return',
            'cancel_url':origin+'/'+plan.role+'/subscription?payment=cancelled',
            'line_items[0][quantity]':'1', 'line_items[0][price]':plan.price_id,
            'expires_at':str(int(purchase.expires_at.replace(tzinfo=timezone.utc).timestamp()))}
        for key, value in metadata.items():
            data[f'metadata[{key}]'] = value
            data[f'payment_intent_data[metadata][{key}]'] = value
        obj = self.request('POST', 'checkout/sessions', data=data, key='frameora:'+purchase.request_key.hex())
        url = urlparse(obj.get('url', ''))
        if (obj.get('livemode') is not False or not str(obj.get('id','')).startswith('cs_test_') or url.scheme != 'https'
                or url.hostname != 'checkout.stripe.com' or url.username or url.password
                or obj.get('mode') != 'payment' or obj.get('metadata') != metadata):
            raise HTTPException(502, 'Invalid test checkout response.')
        return obj
