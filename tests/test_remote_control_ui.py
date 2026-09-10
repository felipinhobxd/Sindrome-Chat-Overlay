from __future__ import annotations

import logging
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from sindrome_overlay.models import ChatMessage
from sindrome_overlay.settings import Settings, SettingsStore
from sindrome_overlay.ui.message_list import MessageListModel, VirtualMessageListView
from sindrome_overlay.ui.virtualized_overlay import OverlayWindow


class RemoteControlUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = SettingsStore(Path(directory.name) / "settings.json")
        self.detector = Mock(available=True)
        self.detector.profile.return_value = "builtin:compact_fps"
        settings = Settings(
            twitch_enabled=False, youtube_enabled=False, sound_enabled=False,
            check_for_updates=False, window_width=540, window_height=620,
            overlay_profiles={"Game": {"font_size": 20, "window_width": 600}},
            game_profiles={r"c:\game.exe": "builtin:compact_fps"},
        )
        with patch("sindrome_overlay.ui.virtualized_overlay.WindowsGameDetector",
                   return_value=self.detector):
            self.window = OverlayWindow(settings, self.store, logging.getLogger("remote-ui"))
        self.window.show()
        QTest.qWait(180)
        self.addCleanup(self._close_window)
        restart = patch.object(self.window, "_restart_providers")
        self.restart = restart.start()
        self.addCleanup(restart.stop)

    def tearDown(self):
        self.restart.assert_not_called()

    def _close_window(self):
        self.window.close()
        QTest.qWait(10)
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_appearance_updates_rendering_and_persists_without_reconnecting(self):
        message = ChatMessage("youtube", "Viewer", "Hello", message_id="one")
        self.window.add_message(message)
        state = self.window.apply_remote_command({
            "action": "set_appearance", "value": {"font_size": 24, "background_opacity": 0},
        })
        self.assertEqual(state["appearance"]["font_size"], 24)
        self.assertEqual(self.store.load().font_size, 24)
        self.assertEqual(self.store.load().background_opacity, 0)
        self.assertIn("font-size: 24px", self.window.styleSheet())
        self.assertEqual(self.window.messages, [message])
        self.assertEqual(self.window.message_model.rowCount(), 1)
        with patch.object(self.store, "save") as save:
            self.window.apply_remote_command({"action": "set_appearance", "value": {"font_size": 24}})
            save.assert_not_called()

    def test_invalid_command_cannot_partially_apply_or_save(self):
        with patch.object(self.store, "save") as save, self.assertRaises(ValueError):
            self.window.apply_remote_command({
                "action": "set_appearance", "value": {"font_size": 24, "youtube_api_key": "private"},
            })
        save.assert_not_called()
        self.assertEqual(self.window.settings.font_size, 15)

    def test_pause_keeps_receiving_messages_and_resume_scrolls_to_latest(self):
        self.window.apply_remote_command({"action": "set_auto_scroll", "value": False})
        for index in range(24):
            self.window.add_message(ChatMessage("youtube", "Viewer", "Hello", message_id=str(index)))
        QTest.qWait(20)
        bar = self.window.message_view.verticalScrollBar()
        self.assertEqual(len(self.window.messages), 24)
        self.assertEqual(bar.value(), 0)
        self.assertGreater(bar.maximum(), 0)
        self.window.apply_remote_command({"action": "set_auto_scroll", "value": True})
        QTest.qWait(20)
        self.assertEqual(bar.value(), bar.maximum())
        self.assertTrue(self.store.load().auto_scroll)

    def test_manual_edit_keeps_game_geometry_and_pauses_automatic_profiles(self):
        self.window._set_automatic_profiles_enabled(True)
        self.window._poll_game_profile()
        geometry = self.window.geometry()
        self.window.apply_remote_command({"action": "set_appearance", "value": {"font_size": 24}})
        self.assertEqual(self.window.geometry(), geometry)
        self.assertFalse(self.window.settings.automatic_profiles_enabled)
        self.assertFalse(self.window._automatic_timer.isActive())
        self.assertIsNone(self.window._automatic_baseline)
        self.assertEqual(self.window.settings.active_overlay_profile, "")
        self.assertEqual(self.store.load().font_size, 24)
        self.assertEqual(self.store.load().window_width, geometry.width())

    def test_profile_uses_existing_layout_application(self):
        state = self.window.apply_remote_command({"action": "apply_profile", "value": "custom:Game"})
        self.assertEqual(state["active_profile"], "custom:Game")
        self.assertEqual(self.window.width(), 600)
        self.assertEqual(self.store.load().font_size, 20)

    def test_click_through_and_clear_use_existing_controls(self):
        state = self.window.apply_remote_command({"action": "set_click_through", "value": True})
        self.assertTrue(state["click_through"])
        self.assertTrue(self.window.header.isHidden())
        self.assertTrue(self.store.load().click_through)
        self.window.apply_remote_command({"action": "set_click_through", "value": False})
        self.assertFalse(self.window.header.isHidden())
        message = ChatMessage("youtube", "Viewer", "Hello", message_id="one")
        self.window.add_message(message)
        self.window.obs_source.publish_message(message)
        self.window.apply_remote_command({"action": "clear_messages"})
        self.assertEqual(self.window.messages, [])
        self.assertEqual(self.window.message_model.rowCount(), 0)
        self.assertEqual(self.window.obs_source.snapshot()["messages"], [])

    def test_wrong_thread_is_rejected_before_any_ui_mutation(self):
        failures = []

        def worker():
            try:
                self.window.apply_remote_command({"action": "set_auto_scroll", "value": False})
            except RuntimeError as error:
                failures.append(str(error))

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, ["Remote commands require the overlay thread"])
        self.assertTrue(self.window.settings.auto_scroll)

    def test_modal_dialog_or_shutdown_prevents_remote_changes(self):
        dialog = QDialog(self.window)
        with patch.object(QApplication, "activeModalWidget", return_value=dialog), \
                self.assertRaises(RuntimeError):
            self.window.apply_remote_command({"action": "set_auto_scroll", "value": False})
        with patch.object(self.window, "_shutting_down", True), self.assertRaises(RuntimeError):
            self.window.apply_remote_command({"action": "set_auto_scroll", "value": False})
        self.assertTrue(self.window.settings.auto_scroll)

    def test_destroyed_chat_view_cancels_pending_layout_callbacks(self):
        model = MessageListModel()
        view = VirtualMessageListView(model)
        view.schedule_editor_refresh()
        view.relayout_visible_items()
        with patch("sys.excepthook") as errors:
            view.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            QTest.qWait(10)
        errors.assert_not_called()
