from __future__ import annotations

import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from sindrome_overlay.remote_pairing import RemotePairing
from sindrome_overlay.ui.remote_pairing_dialog import RemotePairingDialog


class RemotePairingUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.now = 100.0
        self.pairing = RemotePairing(clock=lambda: self.now)
        self.dialog = RemotePairingDialog(self.pairing, "pt-BR")
        self.dialog.show()
        QTest.qWait(5)

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def generate_code(self):
        QTest.mouseClick(self.dialog.generate_button, Qt.MouseButton.LeftButton)
        return self.dialog.code_label.text()

    def refresh(self):
        self.dialog._timer.timeout.emit()

    def test_code_requires_a_click_and_expires_on_screen(self):
        self.assertEqual(self.dialog.code_label.text(), "")
        self.assertFalse(self.dialog.revoke_button.isEnabled())
        self.assertTrue(self.dialog._timer.isActive())
        QTest.keyClick(self.dialog, Qt.Key.Key_Return)
        self.assertEqual(self.dialog.code_label.text(), "")
        with patch("sindrome_overlay.remote_pairing.secrets.randbelow", return_value=7):
            code = self.generate_code()
        self.assertEqual(code, "000007")
        self.assertIn("120", self.dialog.expiry_label.text())
        self.now += 119.5
        self.refresh()
        self.assertIn("1 s.", self.dialog.expiry_label.text())
        self.now += 0.5
        self.refresh()
        self.assertEqual(self.dialog.code_label.text(), "")
        self.assertFalse(self.dialog.revoke_button.isEnabled())
        self.assertIsNone(self.pairing.exchange_code(code))

    def test_consumed_code_disappears_and_close_keeps_phone_authorized(self):
        token = self.pairing.exchange_code(self.generate_code())
        self.refresh()
        self.assertEqual(self.dialog.code_label.text(), "")
        self.assertEqual(self.dialog.status_label.text(), "Um celular tem acesso ao overlay.")
        self.assertTrue(self.dialog.revoke_button.isEnabled())
        QTest.mouseClick(self.dialog.close_button, Qt.MouseButton.LeftButton)
        self.assertFalse(self.dialog._timer.isActive())
        self.assertTrue(self.pairing.authorized(token))
        self.dialog.show()
        self.now += self.pairing.SESSION_LIFETIME
        self.refresh()
        self.assertEqual(self.dialog.status_label.text(), "Nenhum celular tem acesso.")
        self.assertFalse(self.dialog.revoke_button.isEnabled())

    def test_revoke_cancels_both_access_and_pending_code(self):
        token = self.pairing.exchange_code(self.generate_code())
        code = self.generate_code()
        QTest.mouseClick(self.dialog.revoke_button, Qt.MouseButton.LeftButton)
        self.assertFalse(self.pairing.authorized(token))
        self.assertIsNone(self.pairing.exchange_code(code))
        self.assertEqual(self.dialog.code_label.text(), "")
        self.assertFalse(self.dialog.revoke_button.isEnabled())

    def test_close_escape_and_hide_cancel_pending_codes(self):
        for dismiss in (
            self.dialog.close,
            lambda: QTest.keyClick(self.dialog, Qt.Key.Key_Escape),
            self.dialog.hide,
        ):
            self.dialog.show()
            code = self.generate_code()
            dismiss()
            self.assertFalse(self.dialog._timer.isActive())
            self.assertEqual(self.dialog.code_label.text(), "")
            self.assertIsNone(self.pairing.exchange_code(code))

    def test_exhausted_attempts_clear_code_and_allow_local_retry(self):
        self.generate_code()
        for _ in range(self.pairing.MAX_ATTEMPTS):
            self.pairing.exchange_code(None)
        self.refresh()
        self.assertEqual(self.dialog.code_label.text(), "")
        self.assertFalse(self.dialog.revoke_button.isEnabled())
        self.assertIsNotNone(self.pairing.exchange_code(self.generate_code()))

    def test_narrow_dialog_keeps_code_and_buttons_inside_window(self):
        self.dialog.resize(280, 350)
        code = self.generate_code()
        QTest.qWait(5)
        self.assertEqual(len(code), 6)
        self.assertLessEqual(
            self.dialog.code_label.fontMetrics().horizontalAdvance(code),
            self.dialog.code_label.width(),
        )
        for widget in (
            self.dialog.code_label, self.dialog.expiry_label, self.dialog.generate_button,
            self.dialog.revoke_button, self.dialog.close_button,
        ):
            self.assertTrue(self.dialog.rect().contains(widget.geometry()))
