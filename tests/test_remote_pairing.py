from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from sindrome_overlay.remote_pairing import RemotePairing


class RemotePairingTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.pairing = RemotePairing(clock=lambda: self.now)

    def test_pairing_requires_a_pc_code_and_consumes_it_once(self):
        self.assertIsNone(self.pairing.exchange_code("123456"))
        with patch("sindrome_overlay.remote_pairing.secrets.randbelow", return_value=7):
            code = self.pairing.begin_pairing()
        self.assertEqual(code, "000007")
        token = self.pairing.exchange_code(code)
        self.assertTrue(self.pairing.authorized(token))
        self.assertIsNone(self.pairing.exchange_code(code))
        self.assertFalse(self.pairing.authorized(code))
        self.assertFalse(RemotePairing().authorized(token))

    def test_expired_code_and_session_are_rejected_at_the_deadline(self):
        code = self.pairing.begin_pairing()
        self.now += self.pairing.CODE_LIFETIME
        self.assertIsNone(self.pairing.exchange_code(code))
        token = self.pairing.exchange_code(self.pairing.begin_pairing())
        self.now += self.pairing.SESSION_LIFETIME
        self.assertFalse(self.pairing.authorized(token))

    def test_five_invalid_attempts_require_a_new_code_from_the_pc(self):
        code = self.pairing.begin_pairing()
        wrong_code = "000000" if code != "000000" else "000001"
        for invalid in (None, {}, 123456, "１２３４５６", wrong_code):
            self.assertIsNone(self.pairing.exchange_code(invalid))
        self.assertIsNone(self.pairing.exchange_code(code))
        self.assertIsNotNone(self.pairing.exchange_code(self.pairing.begin_pairing()))

    def test_new_pairing_and_revocation_invalidate_old_tokens(self):
        first = self.pairing.exchange_code(self.pairing.begin_pairing())
        second = self.pairing.exchange_code(self.pairing.begin_pairing())
        self.assertFalse(self.pairing.authorized(first))
        self.assertTrue(self.pairing.authorized(second))
        code = self.pairing.begin_pairing()
        self.pairing.revoke()
        self.assertFalse(self.pairing.authorized(second))
        self.assertIsNone(self.pairing.exchange_code(code))

    def test_simultaneous_exchanges_can_create_only_one_session(self):
        code = self.pairing.begin_pairing()
        with ThreadPoolExecutor(max_workers=2) as workers:
            tokens = list(workers.map(self.pairing.exchange_code, [code, code]))
        self.assertEqual(sum(token is not None for token in tokens), 1)

    def test_malformed_tokens_do_not_raise_or_revoke_a_valid_session(self):
        token = self.pairing.exchange_code(self.pairing.begin_pairing())
        for invalid in (None, {}, "x" * 10000, "é" * 43, "x" * 43):
            self.assertFalse(self.pairing.authorized(invalid))
        self.assertTrue(self.pairing.authorized(token))
