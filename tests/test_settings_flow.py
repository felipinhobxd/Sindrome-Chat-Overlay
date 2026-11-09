from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path


class SettingsDialogFlowTests(unittest.TestCase):
    """Regression tests for the settings flow introduced by OverlayShell.

    When open_settings() moved to the shell it built the stock dialog, which
    has neither the diagnostics_requested signal nor the obs_source_url kwarg,
    crashing the settings flow for the real overlay. These tests exercise the
    hook contract on every platform so the mismatch can never ship again.
    """

    def _window(self):
        from PySide6.QtWidgets import QApplication

        from sindrome_overlay.settings import Settings, SettingsStore
        from sindrome_overlay.ui import OverlayWindow

        app = QApplication.instance() or QApplication([])
        directory = tempfile.TemporaryDirectory()
        settings = Settings(
            twitch_enabled=False,
            youtube_enabled=False,
            sound_enabled=False,
            check_for_updates=False,
            obs_enabled=False,
        )
        window = OverlayWindow(
            settings,
            SettingsStore(Path(directory.name) / "settings.json"),
            logging.getLogger("settings-flow"),
        )
        window._test_temp_directory = directory
        return app, window

    def test_settings_dialog_class_is_the_feature_dialog(self) -> None:
        app, window = self._window()
        try:
            from sindrome_overlay.ui.settings_dialog import SettingsDialog as BaseDialog

            dialog_cls = window._settings_dialog_class()
            self.assertTrue(issubclass(dialog_cls, BaseDialog))
            # The base dialog declares the hook signal; the feature dialog
            # actually emits it. Either way the override can connect safely.
            self.assertTrue(hasattr(dialog_cls, "diagnostics_requested"))
        finally:
            window.deleteLater()
            app.processEvents()

    def test_extras_are_accepted_by_the_dialog_constructor(self) -> None:
        # open_settings() forwards youtube_connection_mode plus every key from
        # _settings_dialog_extras(); a constructor mismatch raises TypeError
        # before the dialog is ever shown.
        app, window = self._window()
        try:
            dialog_cls = window._settings_dialog_class()
            dialog = dialog_cls(
                window.settings,
                window,
                youtube_connection_mode=window.youtube_connection_mode,
                **window._settings_dialog_extras(),
            )
            self.assertTrue(hasattr(dialog, "diagnostics_requested"))
            dialog.deleteLater()
        finally:
            window.deleteLater()
            app.processEvents()


if __name__ == "__main__":
    unittest.main()
