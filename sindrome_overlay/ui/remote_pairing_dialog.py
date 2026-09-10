from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from ..feature_i18n import feature_tr
from ..remote_pairing import RemotePairing


class RemotePairingDialog(QDialog):
    """Local pairing UI; expose it only once the protected transport is ready.

    The owning controller must share the pairing instance with its transport,
    keep at most one dialog open, and revoke access when the overlay shuts down.
    This dialog neither opens a listener nor persists credentials.
    """

    def __init__(
        self,
        pairing: RemotePairing,
        language: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pairing = pairing
        self._language = language
        self.setWindowTitle(feature_tr(language, "remote_title"))
        self.resize(380, 350)

        layout = QVBoxLayout(self)
        help_label = QLabel(feature_tr(language, "remote_help"))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.code_label = QLabel()
        self.code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_label.setTextFormat(Qt.TextFormat.PlainText)
        self.code_label.setAccessibleName(feature_tr(language, "remote_code"))
        code_font = self.code_label.font()
        code_font.setPointSize(28)
        code_font.setBold(True)
        self.code_label.setFont(code_font)
        layout.addWidget(self.code_label)

        self.expiry_label = QLabel()
        self.expiry_label.setWordWrap(True)
        layout.addWidget(self.expiry_label)
        layout.addStretch()

        self.generate_button = QPushButton(feature_tr(language, "remote_generate"))
        self.generate_button.clicked.connect(self._generate_code)
        self.revoke_button = QPushButton(feature_tr(language, "remote_revoke"))
        self.revoke_button.clicked.connect(self._revoke_access)
        self.close_button = QPushButton(feature_tr(language, "remote_close"))
        self.close_button.clicked.connect(self.reject)
        for button in (self.generate_button, self.revoke_button, self.close_button):
            button.setAutoDefault(False)
            layout.addWidget(button)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh_status)
        self._refresh_status()

    def _generate_code(self) -> None:
        self.code_label.setText(self._pairing.begin_pairing())
        self._refresh_status()

    def _revoke_access(self) -> None:
        self._pairing.revoke()
        self._refresh_status()

    def _refresh_status(self) -> None:
        status = self._pairing.status()
        self.status_label.setText(feature_tr(
            self._language, "remote_authorized" if status.session_active else "remote_no_access",
        ))
        if not status.code_seconds:
            self.code_label.clear()
        self.expiry_label.setText(feature_tr(
            self._language, "remote_expires" if status.code_seconds else "remote_no_code",
            seconds=status.code_seconds,
        ))
        self.revoke_button.setEnabled(status.session_active or status.code_seconds > 0)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._refresh_status()
        self._timer.start()

    def hideEvent(self, event: QHideEvent) -> None:
        self._timer.stop()
        self._pairing.cancel_pairing()
        self.code_label.clear()
        super().hideEvent(event)
