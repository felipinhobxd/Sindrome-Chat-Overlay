from __future__ import annotations

import base64
import math
import time

from PySide6.QtCore import QEvent, QRect, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QPixmap, QResizeEvent, QTextOption
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QTextEdit, QWidget

from ..emotes import build_message_html
from ..i18n import tr
from ..models import ChatBadge, ChatMessage
from ..settings import Settings
from .twitch_assets import TwitchAssetCache


class _ElidedLabel(QLabel):
    """A single-line label whose original text never imposes a minimum width."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setTextFormat(Qt.PlainText)
        self.setMinimumWidth(0)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full_text = " ".join(text.split())
        self.setToolTip(text)
        self.setText(self._full_text)
        self.updateGeometry()

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        hint = super().sizeHint()
        if self.pixmap().isNull():
            metrics = self.fontMetrics()
            padding = max(0, hint.width() - metrics.horizontalAdvance(self.text()))
            hint.setWidth(metrics.horizontalAdvance(self._full_text) + padding)
        return hint

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, self.sizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.pixmap().isNull():
            self.setText(self.fontMetrics().elidedText(
                self._full_text, Qt.ElideRight, max(0, self.contentsRect().width())
            ))


class EmoteMessageLabel(QTextEdit):
    """Read-only rich text measured and painted by the same wrapping document."""

    layout_changed = Signal()

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
        self._rendered_text = ""
        self._render_pending = False
        self.setObjectName("MessageText")
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDocumentMargin(0)
        self.setStyleSheet("background: transparent; color: #F5F7FB; border: none; padding: 0;")
        self.viewport().setAutoFillBackground(False)
        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        if self.asset_cache is not None and self.emote_ids:
            self.asset_cache.emote_ready.connect(self._emote_ready)
        self._render()

    def text(self) -> str:
        return self._rendered_text

    def natural_width(self) -> int:
        self.document().setDefaultFont(self.font())
        self.document().setTextWidth(-1)
        return max(1, math.ceil(self.document().idealWidth()))

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        self.document().setDefaultFont(self.font())
        self.document().setTextWidth(max(1, width))
        return max(1, math.ceil(self.document().size().height()))

    def sizeHint(self) -> QSize:  # noqa: N802
        width = min(320, self.natural_width())
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, 0)

    def _render(self) -> None:
        if self.asset_cache is None or not self.message.emotes:
            self._rendered_text = self.message.text
            self.setPlainText(self._rendered_text)
        else:
            sources: dict[str, str] = {}
            for emote in self.message.emotes:
                source = (
                    self.asset_cache.emote_source(emote.emote_id, emote.image_url)
                    if emote.image_url
                    else self.asset_cache.emote_source(emote.emote_id)
                )
                if source:
                    sources[emote.emote_id] = source
            self._rendered_text = build_message_html(
                self.message.text, self.message.emotes, sources, self.image_size,
            )
            self.setHtml(self._rendered_text)
        self.updateGeometry()
        self.layout_changed.emit()

    def _emote_ready(self, emote_id: str) -> None:
        # A burst of emote downloads (a message with several distinct emotes,
        # plus other messages) must trigger ONE re-render per event-loop
        # iteration, not one full HTML rebuild per image.
        if emote_id not in self.emote_ids or self._render_pending:
            return
        self._render_pending = True
        QTimer.singleShot(0, self._flush_pending_render)

    def _flush_pending_render(self) -> None:
        self._render_pending = False
        self._render()


class TwitchBadgeLabel(_ElidedLabel):
    layout_changed = Signal()

    def __init__(
        self,
        badge: ChatBadge,
        fallback_text: str,
        settings: Settings,
        asset_cache: TwitchAssetCache,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self.badge = badge
        self.fallback_text = fallback_text
        self.language = settings.language
        self.image_height = max(18, min(32, round(settings.font_size * 1.25)))
        self.asset_cache = asset_cache
        self._has_image: bool | None = None  # None: first render must always apply
        self._render_pending = False
        self.setAlignment(Qt.AlignCenter)
        self.asset_cache.badge_ready.connect(self._badge_ready)
        self._render()

    def _badge_ready(self, *_args) -> None:
        # Every badge label in the overlay receives every badge_ready signal;
        # coalesce the re-render and skip it entirely when the visible state
        # would not change.
        if self._render_pending:
            return
        self._render_pending = True
        QTimer.singleShot(0, self._flush_pending_render)

    def _flush_pending_render(self) -> None:
        self._render_pending = False
        self._render()

    def _render(self) -> None:
        source = self.asset_cache.badge_source(self.badge)
        pixmap = _pixmap_from_source(source)
        has_image = not pixmap.isNull()
        if has_image == self._has_image:
            return
        self._has_image = has_image
        if has_image:
            scaled = pixmap.scaled(
                self.image_height, self.image_height, Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            self.setObjectName("TwitchBadgeImage")
            self.setStyleSheet("background: transparent;")
            self.setText("")
            self.setPixmap(scaled)
        else:
            self.setPixmap(QPixmap())
            self.setObjectName("MetaText")
            self.set_full_text(_short_badge(self.fallback_text, self.language))
            self.setStyleSheet(
                "background: rgba(255,255,255,26); border-radius: 4px; "
                "padding: 1px 4px; font-weight: 700;"
            )
        self.setToolTip(self.fallback_text)
        self.updateGeometry()
        self.layout_changed.emit()


class MessageCard(QFrame):
    layout_changed = Signal()

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
        policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self._meta_labels: list[QLabel] = []
        accent = "#9146FF" if message.platform == "twitch" else "#FF4057"
        if message.kind in {"paid", "bits"}:
            accent = "#F6B73C"
        elif message.kind in {"membership", "event"}:
            accent = "#48D597"

        if settings.show_platform_labels:
            platform = _ElidedLabel("TWITCH" if message.platform == "twitch" else "YOUTUBE", self)
            platform.setObjectName("MetaText")
            platform.setStyleSheet(f"color: {accent}; font-weight: 800; letter-spacing: 0.4px;")
            self._meta_labels.append(platform)

        if message.badge_refs and asset_cache is not None:
            for index, badge_ref in enumerate(message.badge_refs[:3]):
                fallback = (
                    message.badges[index] if index < len(message.badges) else badge_ref.set_id.upper()
                )
                badge = TwitchBadgeLabel(badge_ref, fallback, settings, asset_cache, self)
                badge.layout_changed.connect(self._content_changed)
                self._meta_labels.append(badge)
        else:
            for badge_text in message.badges[:3]:
                badge = _ElidedLabel(_short_badge(badge_text, settings.language), self)
                badge.setObjectName("MetaText")
                badge.setStyleSheet(
                    "background: rgba(255,255,255,26); border-radius: 4px; "
                    "padding: 1px 4px; font-weight: 700;"
                )
                badge.setToolTip(badge_text)
                self._meta_labels.append(badge)

        self.author_label = _ElidedLabel(message.author, self)
        self.author_label.setObjectName("AuthorName")
        self.author_label.setStyleSheet(
            f"color: {message.safe_author_colour}; font-weight: 700; background: transparent;"
        )
        self.author_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._meta_labels.append(self.author_label)

        if message.amount:
            amount = _ElidedLabel(message.amount, self)
            amount.setObjectName("MessageAmount")
            amount.setStyleSheet(
                "color: #17120A; background: #F6B73C; border-radius: 5px; "
                "padding: 2px 6px; font-weight: 800;"
            )
            self._meta_labels.append(amount)
        if settings.show_timestamps:
            timestamp = _ElidedLabel(message.timestamp.astimezone().strftime("%H:%M"), self)
            timestamp.setObjectName("MetaText")
            self._meta_labels.append(timestamp)

        self.message_bubble = QFrame(self)
        self.message_bubble.setObjectName("MessageBubble")
        self.message_label = EmoteMessageLabel(message, settings, asset_cache, self.message_bubble)
        self.message_label.layout_changed.connect(self._content_changed)

    def _arrange(self, width: int, *, apply: bool = False) -> int:
        """One width-based calculation for row measurement and child placement.

        No previous geometry, minimumHeight or sizeHint from a wrapped parent can
        feed back into this calculation. Metadata flows before the body, and only
        the author may use a shortened width to share the remaining line.
        """
        available = max(1, width - 6)
        x, y, line_height = 0, 2, 0
        for label in self._meta_labels:
            label.ensurePolished()
            hint = label.sizeHint()
            item_width = min(available, max(1, hint.width()))
            if label is self.author_label:
                # Keep room for useful identifying characters when sharing a row.
                readable = min(item_width, label.fontMetrics().horizontalAdvance("MMMM"))
                if available - x >= readable:
                    item_width = min(item_width, available - x)
            if x and x + item_width > available:
                x, y, line_height = 0, y + line_height + 2, 0
            if apply:
                label.setGeometry(3 + x, y, item_width, hint.height())
            x += item_width + 6
            line_height = max(line_height, hint.height())
        body_y = y + line_height + 2
        self.message_label.ensurePolished()
        text_width = min(max(1, available - 14), self.message_label.natural_width())
        text_height = self.message_label.heightForWidth(text_width)
        if apply:
            self.message_bubble.setGeometry(3, body_y, text_width + 14, text_height + 7)
            self.message_label.setGeometry(7, 3, text_width, text_height)
            # QTextEdit's viewport resize can relayout its document; keep it at the
            # exact width used above, including when only the row height changed.
            self.message_label.document().setTextWidth(text_width)
        return body_y + text_height + 7 + 3

    def required_height_for_width(self, width: int) -> int:
        return self._arrange(width)

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self.required_height_for_width(width)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(320, self.required_height_for_width(320))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, 0)

    def _content_changed(self) -> None:
        self._arrange(self.width(), apply=True)
        self.updateGeometry()
        self.layout_changed.emit()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.FontChange, QEvent.StyleChange) and hasattr(self, "message_label"):
            self._content_changed()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._arrange(event.size().width(), apply=True)


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
