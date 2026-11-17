"""Provider contract tests; all delivery is mocked."""
import unittest
from unittest.mock import patch, MagicMock
from dataclasses import replace
from fastapi import HTTPException
from app.services import auth_email_delivery as delivery
from app.services.verification_email_content import content, SUBJECT

class BrevoTests(unittest.TestCase):
    def config(self):
        return delivery.BrevoSettings('synthetic-key', 'sender@example.com', 'https://frontend.example')

    def test_success_payload(self):
        with patch.object(delivery.httpx, 'Client') as factory:
            client = factory.return_value.__enter__.return_value
            client.post.return_value.status_code = 201
            link = 'https://frontend.example/verify-email#token=synthetic'
            delivery.BrevoAuthEmailDelivery(self.config()).send(recipient='recipient@example.com', purpose='verify-email', link=link)
            args, kwargs = client.post.call_args
            self.assertEqual(args[0], 'https://api.brevo.com/v3/smtp/email')
            self.assertEqual(kwargs['headers']['api-key'], 'synthetic-key')
            self.assertEqual(kwargs['json']['subject'], SUBJECT)
            self.assertEqual((kwargs['json']['textContent'], kwargs['json']['htmlContent']), content(link))
            self.assertEqual(kwargs['json']['sender']['name'], 'Frameora AI')
            self.assertFalse(factory.call_args.kwargs['follow_redirects'])
            self.assertFalse(factory.call_args.kwargs['trust_env'])

    def test_invalid_configuration(self):
        for changes in ({'api_key':''}, {'sender_email':'invalid'}, {'frontend_origin':'http://unsafe.example'}, {'sender_name':'bad\nname'}):
            with self.subTest(changes=changes), self.assertRaises(HTTPException):
                delivery.BrevoAuthEmailDelivery(replace(self.config(), **changes))

    def test_errors_sanitized_no_fallback(self):
        with patch.object(delivery.httpx, 'Client') as factory, patch.object(delivery, 'GmailAuthEmailDelivery') as smtp:
            client = factory.return_value.__enter__.return_value
            for code in (400,401,429,500,302):
                client.post.return_value.status_code = code
                with self.assertRaises(HTTPException) as caught:
                    delivery.BrevoAuthEmailDelivery(self.config()).send(recipient='recipient@example.com', purpose='verify-email', link='https://frontend.example/verify-email#token=synthetic')
                self.assertEqual(caught.exception.status_code, 503)
                self.assertNotIn('synthetic', caught.exception.detail)
            client.post.side_effect = RuntimeError('private provider information')
            with self.assertRaises(HTTPException) as caught:
                delivery.BrevoAuthEmailDelivery(self.config()).send(recipient='recipient@example.com', purpose='verify-email', link='https://frontend.example/verify-email#token=synthetic')
            self.assertNotIn('private', caught.exception.detail)
            smtp.assert_not_called()

    def test_selection_default_explicit_and_unknown(self):
        with patch.object(delivery, 'configuration_values', return_value={}), patch.object(delivery, 'GmailAuthEmailDelivery') as smtp:
            delivery.email_delivery(); smtp.assert_called_once()
        values = {'EMAIL_DELIVERY_PROVIDER':'brevo','BREVO_API_KEY':'synthetic-key','BREVO_SENDER_EMAIL':'sender@example.com','EMAIL_VERIFICATION_FRONTEND_ORIGIN':'https://frontend.example'}
        with patch.object(delivery, 'configuration_values', return_value=values), patch.object(delivery, 'GmailAuthEmailDelivery') as smtp:
            self.assertIsInstance(delivery.email_delivery(), delivery.BrevoAuthEmailDelivery)
            smtp.assert_not_called()
        with patch.object(delivery, 'configuration_values', return_value={'EMAIL_DELIVERY_PROVIDER':'unknown'}):
            with self.assertRaises(HTTPException): delivery.email_delivery()

    def test_readiness_uses_selected_delivery_without_sending(self):
        from app.routers import email_verification as route
        from fastapi import Response
        from types import SimpleNamespace
        with patch.object(route, 'limit_verification_peer'), patch.object(route.service, 'prerequisites'), patch.object(delivery, 'email_delivery') as factory:
            result = route.readiness(Response(), SimpleNamespace(client=SimpleNamespace(host='mock')), db=MagicMock())
            self.assertTrue(result['delivery_available'])
            factory.assert_called_once()
            factory.return_value.send.assert_not_called()
            factory.side_effect = HTTPException(503, 'unavailable')
            self.assertFalse(route.readiness(Response(), SimpleNamespace(client=None), db=MagicMock())['delivery_available'])

    def test_failure_invalidates_token_and_leaves_account_pending(self):
        from app.services import email_verification as service
        from types import SimpleNamespace
        account = SimpleNamespace(id=1, email='recipient@example.com', auth_version=0,
                                  email_verification_required=True, is_verified=False)
        with patch.object(service.tokens, 'issue', return_value='synthetic'), patch.object(service.tokens, 'consume') as consume, patch.object(delivery.httpx, 'Client', side_effect=RuntimeError('private')):
            with self.assertRaises(HTTPException):
                service.send_verification(account, delivery.BrevoAuthEmailDelivery(self.config()))
            consume.assert_called_once_with('verify-email', 'synthetic')
            self.assertFalse(account.is_verified)
            self.assertTrue(account.email_verification_required)
