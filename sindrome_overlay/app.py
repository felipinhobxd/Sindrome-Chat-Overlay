from __future__ import annotations

import logging
import sys
import traceback

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImageReader, QPixmapCache
from PySide6.QtWidgets import QApplication, QMessageBox

from .i18n import tr
from .logging_config import configure_logging
from .settings import SettingsStore
from .ui import OverlayWindow


_PIXMAP_CACHE_KB = 4 * 1024
_IMAGE_ALLOCATION_LIMIT_MB = 32


def run() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QPixmapCache.setCacheLimit(_PIXMAP_CACHE_KB)
    QImageReader.setAllocationLimit(_IMAGE_ALLOCATION_LIMIT_MB)

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
