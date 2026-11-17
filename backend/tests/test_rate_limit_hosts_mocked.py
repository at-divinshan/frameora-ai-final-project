"""Offline URL-policy tests: no application settings, .env or service connections."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class RedisHostTests(unittest.TestCase):
    def setUp(self):
        config = ModuleType('app.core.config')
        config.settings = SimpleNamespace(redis_url='')
        store = ModuleType('app.services.oauth_transaction_store')
        store.LIMIT = 'mocked-rate-limit-script'
        spec = importlib.util.spec_from_file_location('isolated_rate_limits',
            Path(__file__).resolve().parents[1] / 'app/services/rate_limit_service.py')
        self.service = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'app.core.config': config,
                                     'app.services.oauth_transaction_store': store}):
            spec.loader.exec_module(self.service)
        self.redis = Mock()
        self.patch = patch.object(self.service, 'Redis', self.redis)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.service.client.cache_clear)

    def test_allowed_urls_preserve_credentials_and_options(self):
        for host in ('localhost', '127.0.0.1', '[::1]', 'redis.railway.internal'):
            with self.subTest(host=host):
                self.service.client.cache_clear()
                url = f'redis://test-user:synthetic-password@{host}:6379/2'
                self.service.settings.redis_url = url
                self.assertIs(self.service.client(), self.redis.from_url.return_value)
                self.redis.from_url.assert_called_with(url, decode_responses=True,
                    socket_connect_timeout=3, socket_timeout=3, retry_on_timeout=False)

    def test_tls_hosts_remain_allowed(self):
        for host in ('remote.example', 'redis.railway.internal', 'localhost'):
            with self.subTest(host=host):
                self.service.client.cache_clear()
                self.service.settings.redis_url = f'rediss://{host}:6380'
                self.service.client()
                self.redis.from_url.assert_called()

    def test_non_tls_hosts_and_spoofed_suffixes_rejected(self):
        for host in ('remote.example', '10.0.0.1', 'other.railway.internal',
                     'redis.railway.internal.evil.example', 'evilredis.railway.internal',
                     'redis.railway.internal.', 'redis.railway.internal@evil.example'):
            with self.subTest(host=host):
                self.service.client.cache_clear()
                self.redis.reset_mock()
                self.service.settings.redis_url = f'redis://{host}:6379'
                with self.assertRaises(ValueError): self.service.client()
                self.redis.from_url.assert_not_called()

    def test_missing_host_and_invalid_scheme_rejected(self):
        for url in ('', 'redis://', 'http://redis.railway.internal:6379', 'unix:///tmp/redis.sock'):
            with self.subTest(url=url):
                self.service.client.cache_clear()
                self.redis.reset_mock()
                self.service.settings.redis_url = url
                with self.assertRaises(ValueError): self.service.client()
                self.redis.from_url.assert_not_called()

    def test_auth_limit_remains_fail_closed(self):
        self.service.settings.redis_url = 'redis://unapproved.example:6379'
        with self.assertRaises(self.service.HTTPException) as caught:
            self.service.limit_public_auth('login', 'test@example.invalid', '127.0.0.1')
        self.assertEqual(caught.exception.status_code, 503)
        self.redis.from_url.assert_not_called()

    def test_railway_rate_limit_still_returns_429(self):
        self.service.settings.redis_url = 'redis://redis.railway.internal:6379'
        self.redis.from_url.return_value.eval.return_value = 6
        with self.assertRaises(self.service.HTTPException) as caught:
            self.service.limit_public_auth('login', 'test@example.invalid', '127.0.0.1')
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.headers, {'Retry-After': '300'})
