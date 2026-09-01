from __future__ import annotations

import base64
import time

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..emotes import build_message_html
from ..i18n import tr
from ..models import ChatBadge, ChatMessage
from ..settings import Settings
from .twitch_assets import TwitchAssetCache


class EmoteMessageLabel(QLabel):
    def __init__(
        self,
        message: ChatMessage,
        settings: Settings,
        asset_cache: TwitchAssetCache | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.message = message
        self.asset_cache = asset_cache
        self.image_size = max(24, min(48, round(settings.font_size * 1.8)))
        self.emote_ids = {emote.emote_id for emote in message.emotes}
        self.setObjectName("MessageText")
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        if self.asset_cache is not None and self.emote_ids:
            self.asset_cache.emote_ready.connect(self._emote_ready)
        self._render()

    def _render(self) -> None:
        if self.asset_cache is None or not self.message.emotes:
            self.setTextFormat(Qt.PlainText)
            self.setText(self.message.text)
            return
        sources = {
            emote_id: source
            for emote_id in self.emote_ids
            if (source := self.asset_cache.emote_source(emote_id))
        }
        self.setTextFormat(Qt.RichText)
        self.setText(
            build_message_html(
                self.message.text,
                self.message.emotes,
                sources,
                self.image_size,
            )
        )
        self.updateGeometry()

    def _emote_ready(self, emote_id: str) -> None:
        if emote_id in self.emote_ids:
            self._render()


class TwitchBadgeLabel(QLabel):
    def __init__(
        self,
        badge: ChatBadge,
        fallback_text: str,
        settings: Settings,
        asset_cache: TwitchAssetCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.badge = badge
        self.fallback_text = fallback_text
        self.language = settings.language
        self.image_height = max(18, min(32, round(settings.font_size * 1.25)))
        self.asset_cache = asset_cache
        self.setToolTip(fallback_text)
        self.setAlignment(Qt.AlignCenter)
        self.asset_cache.badge_ready.connect(self._render)
        self._render()

    def _render(self) -> None:
        source = self.asset_cache.badge_source(self.badge)
        pixmap = _pixmap_from_source(source)
        if not pixmap.isNull():
            scaled = pixmap.scaledToHeight(self.image_height, Qt.SmoothTransformation)
            self.setObjectName("TwitchBadgeImage")
            self.setStyleSheet("background: transparent;")
            self.setText("")
            self.setPixmap(scaled)
            self.setFixedSize(scaled.size())
            return

        self.setPixmap(QPixmap())
        self.setObjectName("MetaText")
        self.setText(_short_badge(self.fallback_text, self.language))
        self.setStyleSheet(
            "background: rgba(255,255,255,26); border-radius: 4px; "
            "padding: 1px 4px; font-weight: 700;"
        )
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16_777_215, 16_777_215)


class MessageCard(QFrame):
    def __init__(
        self,
        message: ChatMessage,
        settings: Settings,
        asset_cache: TwitchAssetCache | None = None,
        parent: QWidget | None = None,
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

        if message.badge_refs and asset_cache is not None:
            for index, badge_ref in enumerate(message.badge_refs[:3]):
                fallback = (
                    message.badges[index]
                    if index < len(message.badges)
                    else badge_ref.set_id.upper()
                )
                meta.addWidget(TwitchBadgeLabel(badge_ref, fallback, settings, asset_cache, self))

        author = QLabel(message.author)
        author.setStyleSheet(
            f"color: {message.safe_author_colour}; font-weight: 700; "
            "background: rgba(4, 7, 12, 170); border-radius: 3px; padding: 0 2px;"
        )
        author.setTextInteractionFlags(Qt.TextSelectableByMouse)
        meta.addWidget(author)

        if not message.badge_refs or asset_cache is None:
            for badge_text in message.badges[:3]:
                badge = QLabel(_short_badge(badge_text, settings.language))
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

        text = EmoteMessageLabel(message, settings, asset_cache, self)
        outer.addWidget(text)


def _pixmap_from_source(source: str) -> QPixmap:
    pixmap = QPixmap()
    if not source:
        return pixmap
    if source.startswith("data:image/") and "," in source:
        try:
            pixmap.loadFromData(base64.b64decode(source.split(",", 1)[1], validate=True))
        except (ValueError, TypeError):
            return QPixmap()
        return pixmap
    local_path = QUrl(source).toLocalFile()
    if local_path:
        pixmap.load(local_path)
    return pixmap


def _short_badge(value: str, language: str = "en") -> str:
    normalized = value.upper()
    aliases = {
        "MODERATOR": "MOD",
        "CHAT MODERATOR": "MOD",
        "MODERADOR": "MOD",
        "VERIFIED": "✓",
        "VERIFICADO": "✓",
        "SUBSCRIBER": "SUB",
        "INSCRITO": "SUB",
        "MEMBER": tr(language, "badge_member"),
        "MEMBRO": tr(language, "badge_member"),
        "CHANNEL OWNER": tr(language, "badge_owner"),
        "OWNER": tr(language, "badge_owner"),
        "DONO": tr(language, "badge_owner"),
    }
    if normalized in aliases:
        return aliases[normalized]
    return normalized[:9]
