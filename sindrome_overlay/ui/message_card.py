from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..models import ChatMessage
from ..settings import Settings


class MessageCard(QFrame):
    def __init__(
        self, message: ChatMessage, settings: Settings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.message = message
        self.created_monotonic = time.monotonic()
        self.setObjectName("ChatCard")
        accent = "#9146FF" if message.platform == "twitch" else "#FF4057"
        if message.kind in {"paid", "bits"}:
            accent = "#F6B73C"
        elif message.kind in {"membership", "event"}:
            accent = "#48D597"
        self.setStyleSheet(f"QFrame#ChatCard {{ border-left: 4px solid {accent}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 9)
        outer.setSpacing(4)

        meta = QHBoxLayout()
        meta.setSpacing(6)
        if settings.show_platform_labels:
            platform = QLabel("TWITCH" if message.platform == "twitch" else "YOUTUBE")
            platform.setObjectName("MetaText")
            platform.setStyleSheet(f"color: {accent}; font-weight: 800; letter-spacing: 0.4px;")
            meta.addWidget(platform)

        author = QLabel(message.author)
        author.setStyleSheet(
            f"color: {message.safe_author_colour}; font-weight: 700; background: transparent;"
        )
        author.setTextInteractionFlags(Qt.TextSelectableByMouse)
        meta.addWidget(author)

        for badge_text in message.badges[:3]:
            badge = QLabel(_short_badge(badge_text))
            badge.setObjectName("MetaText")
            badge.setStyleSheet(
                "background: rgba(255,255,255,26); border-radius: 4px; "
                "padding: 1px 4px; font-weight: 700;"
            )
            badge.setToolTip(badge_text)
            meta.addWidget(badge)

        if message.amount:
            amount = QLabel(message.amount)
            amount.setStyleSheet(
                "color: #17120A; background: #F6B73C; border-radius: 5px; "
                "padding: 2px 6px; font-weight: 800;"
            )
            meta.addWidget(amount)

        meta.addStretch(1)
        if settings.show_timestamps:
            timestamp = QLabel(message.timestamp.astimezone().strftime("%H:%M"))
            timestamp.setObjectName("MetaText")
            meta.addWidget(timestamp)
        outer.addLayout(meta)

        text = QLabel(message.text)
        text.setObjectName("MessageText")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        outer.addWidget(text)


def _short_badge(value: str) -> str:
    normalized = value.upper()
    aliases = {
        "MODERATOR": "MOD",
        "CHAT MODERATOR": "MOD",
        "VERIFIED": "✓",
        "SUBSCRIBER": "SUB",
        "MEMBER": "MEMBRO",
        "CHANNEL OWNER": "DONO",
    }
    if normalized in aliases:
        return aliases[normalized]
    return normalized[:9]
