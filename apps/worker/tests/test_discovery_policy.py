import unittest
from unittest.mock import patch

from app.browser_discovery import canonical_url, public_host, stable_hash


class DiscoveryPolicyTests(unittest.TestCase):
    def test_blocks_loopback_and_private_hosts(self):
        self.assertFalse(public_host("127.0.0.1"))
        self.assertFalse(public_host("localhost"))
        self.assertFalse(public_host("192.168.1.10"))

    @patch("app.browser_discovery.public_host", return_value=True)
    def test_canonical_url_rejects_cross_origin_links(self, _):
        self.assertIsNone(canonical_url("https://attacker.example/path", "https://demo.example/", "demo.example"))

    @patch("app.browser_discovery.public_host", return_value=True)
    def test_canonical_url_keeps_app_query_but_drops_tracking(self, _):
        value = canonical_url("/catalog?category=books&utm_source=mail", "https://demo.example/", "demo.example")
        self.assertEqual(value, "https://demo.example/catalog?category=books")

    def test_stable_hash_is_deterministic(self):
        self.assertEqual(stable_hash({"b": 2, "a": 1}), stable_hash({"a": 1, "b": 2}))


if __name__ == "__main__":
    unittest.main()
