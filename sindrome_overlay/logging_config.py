from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .settings import app_data_dir


def configure_logging() -> logging.Logger:
    log_dir = app_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "overlay.log"

    logger = logging.getLogger("sindrome_overlay")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    return logger
