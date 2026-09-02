from __future__ import annotations

import unittest

from sindrome_overlay.authenticode import authenticode_result_from_payload


class AuthenticodeResultTests(unittest.TestCase):
    def test_valid_signature_is_accepted(self) -> None:
        result = authenticode_result_from_payload(
            {"status": "Valid", "subject": "CN=Sindrome Games, O=Sindrome Games"}
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.signer_subject, "CN=Sindrome Games, O=Sindrome Games")

    def test_unsigned_or_malformed_result_is_rejected(self) -> None:
        self.assertFalse(
            authenticode_result_from_payload(
                {"status": "NotSigned", "subject": ""}
            ).valid
        )
        self.assertFalse(authenticode_result_from_payload("unexpected").valid)

    def test_signer_continuity_is_case_and_whitespace_tolerant(self) -> None:
        expected = "CN=Sindrome Games, O=Sindrome Games"
        matching = authenticode_result_from_payload(
            {"status": "Valid", "subject": "  cn=sindrome games,   o=sindrome games "},
            expected,
        )
        different = authenticode_result_from_payload(
            {"status": "Valid", "subject": "CN=Different Publisher"},
            expected,
        )
        self.assertTrue(matching.valid)
        self.assertFalse(different.valid)
        self.assertEqual(different.error_code, "signer_mismatch")


if __name__ == "__main__":
    unittest.main()
