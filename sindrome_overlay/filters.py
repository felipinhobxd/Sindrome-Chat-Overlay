"""Central message display filters shared by both desktop overlays."""

from __future__ import annotations

import re

from .models import ChatMessage
from .settings import Settings

_SEPARATOR = re.compile(r"[,\n]")


def _items(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in _SEPARATOR.split(raw or "") if item.strip())


def hidden_user_names(settings: Settings) -> frozenset[str]:
    return frozenset(item.lower() for item in _items(settings.hidden_users))


def hidden_word_list(settings: Settings) -> tuple[str, ...]:
    return tuple(item.lower() for item in _items(settings.hidden_words))


def should_display(message: ChatMessage, settings: Settings) -> bool:
    """Single source of truth for whether a message is rendered.

    Used by the live add path and by history rebuilds so both overlays can
    never drift apart again.
    """
    if settings.hide_commands and message.text.lstrip().startswith("!"):
        return False
    users = hidden_user_names(settings)
    if users:
        if message.author.lower() in users:
            return False
        if message.author_id and message.author_id in users:
            return False
    words = hidden_word_list(settings)
    if words:
        text = message.text.lower()
        if any(word in text for word in words):
            return False
    return True
