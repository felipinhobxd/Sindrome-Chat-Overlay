from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == "win32", "Desktop feature UI tests run on Windows CI")
class DesktopProfilesAndDiagnosticsUiTests(unittest.TestCase):
    def test_settings_dialog_profiles_and_diagnostics_are_wired(self) -> None:
        from PySide6.QtWidgets import QApplication, QTabWidget

        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.feature_settings_dialog import SettingsDialog

        app = QApplication.instance() or QApplication([])
        dialog = SettingsDialog(
            Settings(language="pt-BR", font_size=15, background_opacity=72),
            youtube_connection_mode="compatibility",
        )
        dialog.show()
        app.processEvents()

        tabs = dialog.findChild(QTabWidget)
        self.assertIsNotNone(tabs)
        titles = [tabs.tabText(index) for index in range(tabs.count())]
        self.assertIn("Perfis de Overlay", titles)
        self.assertIn("Diagnóstico", titles)

        dialog.font_size.setValue(19)
        dialog.background_opacity.setValue(41)
        dialog.max_messages.setValue(222)
        self.assertTrue(dialog._save_profile_named("Minha Live"))
        saved = dialog.settings()
        self.assertIn("Minha Live", saved.overlay_profiles)
        self.assertEqual(saved.overlay_profiles["Minha Live"]["font_size"], 19)
        self.assertEqual(saved.overlay_profiles["Minha Live"]["background_opacity"], 41)
        self.assertEqual(saved.overlay_profiles["Minha Live"]["max_messages"], 222)
        self.assertEqual(saved.active_overlay_profile, "custom:Minha Live")

        compact_index = dialog.profile_combo.findData("builtin:compact_fps")
        self.assertGreaterEqual(compact_index, 0)
        dialog.profile_combo.setCurrentIndex(compact_index)
        dialog._apply_selected_profile()
        self.assertEqual(dialog.font_size.value(), 13)
        self.assertEqual(dialog.max_messages.value(), 80)
        self.assertEqual(dialog.background_opacity.value(), 32)
        self.assertEqual(dialog.settings().active_overlay_profile, "builtin:compact_fps")

        requested = []
        dialog.diagnostics_requested.connect(lambda: requested.append(True))
        dialog.export_diagnostics_button.click()
        app.processEvents()
        self.assertEqual(requested, [True])
        dialog.close()

    def test_overlay_applies_profile_without_touching_connections_or_creating_release(self) -> None:
        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui.virtualized_overlay import OverlayWindow

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                twitch_enabled=False,
                youtube_enabled=False,
                twitch_channel="sindromegames",
                youtube_input="https://www.youtube.com/@SindromeGames/live",
                youtube_api_key="",
                sound_enabled=False,
                check_for_updates=False,
                window_width=440,
                window_height=720,
            )
            store = SettingsStore(Path(directory) / "settings.json")
            window = OverlayWindow(settings, store, logging.getLogger("feature-ui"))
            window.show()
            app.processEvents()

            original_twitch = window.settings.twitch_channel
            original_youtube = window.settings.youtube_input
            window._apply_overlay_profile_ref("builtin:compact_fps")
            app.processEvents()

            self.assertEqual(window.settings.active_overlay_profile, "builtin:compact_fps")
            self.assertEqual(window.settings.font_size, 13)
            self.assertEqual(window.settings.max_messages, 80)
            self.assertEqual(window.width(), 360)
            self.assertEqual(window.height(), 520)
            self.assertEqual(window.settings.twitch_channel, original_twitch)
            self.assertEqual(window.settings.youtube_input, original_youtube)
            self.assertEqual(store.load().active_overlay_profile, "builtin:compact_fps")

            runtime = window._diagnostic_runtime()
            self.assertIn("global_hotkey_registered", runtime)
            self.assertEqual(runtime["message_count"], 0)
            self.assertIn("active_message_cards", runtime)
            window.close()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
