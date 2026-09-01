from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .i18n import tr
from .logging_config import configure_logging
from .settings import SettingsStore
from .ui import OverlayWindow


def run() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Sindrome Chat Overlay")
    app.setApplicationDisplayName("Sindrome Chat Overlay")
    app.setOrganizationName("Sindrome Games")
    app.setQuitOnLastWindowClosed(False)

    logger = configure_logging()
    store = SettingsStore()
    settings = store.load()

    def handle_exception(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("Unhandled exception:\n%s", details)
        QMessageBox.critical(
            None,
            "Sindrome Chat Overlay",
            tr(settings.language, "unexpected_error"),
        )

    sys.excepthook = handle_exception
    logging.captureWarnings(True)

    window = OverlayWindow(settings, store, logger)
    window.show()
    return app.exec()
