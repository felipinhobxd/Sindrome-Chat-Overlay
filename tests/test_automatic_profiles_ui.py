from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from sindrome_overlay.profiles import capture_overlay_profile
from sindrome_overlay.settings import Settings, SettingsStore
from sindrome_overlay.ui.feature_settings_dialog import SettingsDialog
from sindrome_overlay.ui.virtualized_overlay import OverlayWindow


class AutomaticProfilesUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.detector = Mock(available=True)
        self.detector.profile.return_value = "builtin:compact_fps"
        self.settings = Settings(
            twitch_enabled=False, youtube_enabled=False, sound_enabled=False,
            check_for_updates=False, font_size=19, window_width=540, window_height=620,
            automatic_profiles_enabled=True,
            game_profiles={r"c:\game.exe": "builtin:compact_fps"},
        )
        self.store = SettingsStore(Path(self.directory.name) / "settings.json")
        with patch("sindrome_overlay.ui.virtualized_overlay.WindowsGameDetector",
                   return_value=self.detector):
            self.window = OverlayWindow(self.settings, self.store, logging.getLogger("auto-test"))
        self.window.show()
        # Let the shell's delayed native/lock initialization finish before
        # exercising profile transitions or destroying its widgets.
        QTest.qWait(180)
        self.addCleanup(self._close_window)
        self.window._remember_geometry()
        self.baseline = capture_overlay_profile(self.window.settings)

    def _close_window(self):
        self.window.close()
        QTest.qWait(10)
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_game_switches_restore_original_without_restarting_chats_or_saving_temporary_layout(self):
        with patch.object(self.window, "_restart_providers") as restart:
            self.window._poll_game_profile()
            self.assertEqual(self.window.settings.font_size, 13)
            self.assertEqual(self.window.width(), 360)
            with patch.object(self.window, "_rebuild_cards") as rebuild:
                self.window._poll_game_profile()
                rebuild.assert_not_called()
            self.window.set_click_through(True)
            saved = self.store.load()
            self.assertEqual(capture_overlay_profile(saved), self.baseline)
            self.assertTrue(saved.click_through)
            self.detector.profile.return_value = "builtin:chat_focus"
            self.window._poll_game_profile()
            self.assertEqual(self.window.settings.font_size, 15)
            self.detector.profile.return_value = ""
            self.window._poll_game_profile()
            self.assertEqual(capture_overlay_profile(self.window.settings), self.baseline)
            self.assertEqual(self.window.width(), self.baseline["window_width"])
            restart.assert_not_called()

    def test_pause_and_manual_selection_win_and_shutdown_saves_baseline(self):
        self.window._poll_game_profile()
        self.window._set_automatic_profiles_enabled(False)
        self.assertFalse(self.window._automatic_timer.isActive())
        self.assertEqual(capture_overlay_profile(self.window.settings), self.baseline)
        self.window._set_automatic_profiles_enabled(True)
        self.window._poll_game_profile()
        self.window._apply_overlay_profile_ref("builtin:clean_stream")
        self.assertFalse(self.window.settings.automatic_profiles_enabled)
        self.assertEqual(self.window.settings.font_size, 17)
        self.window._set_automatic_profiles_enabled(True)
        self.window._poll_game_profile()
        self.window.close()
        self.assertEqual(self.store.load().font_size, 17)
        self.assertTrue(self.store.load().automatic_profiles_enabled)

    def test_settings_dialog_pauses_automation_and_cancel_resumes_it(self):
        self.window._poll_game_profile()
        observed = []

        def reject(dialog):
            observed.append(dialog.settings().font_size)
            self.assertFalse(self.window._automatic_timer.isActive())
            return QDialog.DialogCode.Rejected

        with patch.object(SettingsDialog, "exec", reject):
            self.window.open_settings()
        self.assertEqual(observed, [19])
        self.assertTrue(self.window._automatic_timer.isActive())
        self.window._poll_game_profile()
        self.assertEqual(self.window.settings.font_size, 13)

    def test_dialog_add_remove_and_deleted_custom_profile_cleanup(self):
        dialog = SettingsDialog(self.settings)
        self.app.processEvents()
        self.addCleanup(dialog.close)
        self.assertTrue(dialog._save_profile_named("My game"))
        with patch("sindrome_overlay.ui.feature_settings_dialog.QFileDialog.getOpenFileName",
                   return_value=("C:/New/Game.EXE", "")):
            dialog._choose_game_profile()
        self.assertEqual(dialog.settings().game_profiles[r"c:\new\game.exe"], "custom:My game")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dialog._delete_selected_profile()
        self.assertNotIn(r"c:\new\game.exe", dialog.settings().game_profiles)
        dialog.game_profile_list.setCurrentRow(0)
        dialog._remove_game_profile()
        self.assertEqual(dialog.settings().game_profiles, {})
        # Editing/cancelling the dialog never mutates the original settings.
        self.assertEqual(self.settings.game_profiles, {r"c:\game.exe": "builtin:compact_fps"})

    def test_partial_profiles_do_not_inherit_previous_game_geometry(self):
        self.window.settings.overlay_profiles = {
            "First": {"window_x": 220, "font_size": 12},
            "Second": {"font_size": 21},
        }
        self.detector.profile.return_value = "custom:First"
        self.window._poll_game_profile()
        self.assertEqual(self.window.settings.window_x, 220)
        self.detector.profile.return_value = "custom:Second"
        self.window._poll_game_profile()
        self.assertEqual(self.window.settings.window_x, self.baseline["window_x"])
        self.assertEqual(self.window.settings.font_size, 21)

    def test_accepting_settings_preserves_changes_and_disables_automation(self):
        self.window._poll_game_profile()

        def accept(dialog):
            dialog.automatic_profiles_enabled.setChecked(False)
            dialog.font_size.setValue(23)
            return QDialog.DialogCode.Accepted

        with patch.object(SettingsDialog, "exec", accept):
            self.window.open_settings()
        self.assertFalse(self.window._automatic_timer.isActive())
        self.assertEqual(self.store.load().font_size, 23)
        self.assertFalse(self.store.load().automatic_profiles_enabled)
