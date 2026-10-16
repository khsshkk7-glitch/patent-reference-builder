import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from scripts.browser_session import navigate, CollectionError, HumanRequired


class NavigationFailures(unittest.TestCase):
    def test_local_network_denial_is_not_http_and_is_not_retried(self):
        page = Mock()
        page.goto.side_effect = RuntimeError('Page.goto: net::ERR_NETWORK_ACCESS_DENIED at https://example.test')
        with self.assertRaisesRegex(CollectionError, 'net::ERR_NETWORK_ACCESS_DENIED'):
            navigate(page, 'https://example.test', attempts=3)
        self.assertEqual(page.goto.call_count, 1)

    def test_http_access_denial_requires_human_without_retries(self):
        for status in (401, 403, 429):
            page = Mock()
            page.goto.return_value = SimpleNamespace(status=status)
            with self.assertRaisesRegex(HumanRequired, f'HTTP {status}'):
                navigate(page, 'https://example.test', attempts=3)
            self.assertEqual(page.goto.call_count, 1)

    def test_transient_failure_retries_and_preserves_network_code(self):
        page = Mock()
        page.goto.side_effect = RuntimeError('net::ERR_CONNECTION_RESET')
        with patch('scripts.browser_session.time.sleep'):
            with self.assertRaisesRegex(CollectionError, 'ERR_CONNECTION_RESET'):
                navigate(page, 'https://example.test', attempts=2)
        self.assertEqual(page.goto.call_count, 2)
