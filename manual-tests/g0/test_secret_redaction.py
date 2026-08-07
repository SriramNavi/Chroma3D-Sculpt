from __future__ import annotations

import json
import unittest

import _support

assert _support.GENERATIVE_ROOT.is_dir()
from backends.base import redact_sensitive


class SecretRedactionTests(unittest.TestCase):
    def test_sensitive_keys_and_values_are_removed_recursively(self) -> None:
        secret = "cgb-owner-secret-123"
        value = {
            "Authorization": f"Bearer {secret}",
            "nested": {"subscription_key": secret, "message": f"failure {secret}"},
            "api_token": secret,
        }
        encoded = json.dumps(redact_sensitive(value, (secret,)))
        self.assertNotIn(secret, encoded)
        self.assertIn("[REDACTED]", encoded)

    def test_bearer_token_is_redacted_without_known_secret_list(self) -> None:
        self.assertEqual(redact_sensitive("Bearer abc.def-123"), "Bearer [REDACTED]")


if __name__ == "__main__":
    unittest.main()
