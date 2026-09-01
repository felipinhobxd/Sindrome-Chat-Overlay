from __future__ import annotations

import html
import re
from collections.abc import Mapping

from .models import ChatEmote

_EMOTE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def twitch_emote_url(emote_id: str) -> str:
    if not _EMOTE_ID.fullmatch(emote_id):
        raise ValueError("Invalid Twitch emote ID.")
    return f"https://static-cdn.jtvnw.net/emoticons/v2/{emote_id}/static/dark/3.0"


def build_message_html(
    text: str,
    emotes: tuple[ChatEmote, ...],
    sources: Mapping[str, str],
    image_size: int,
) -> str:
    if not emotes:
        return _escape_text(text)

    parts: list[str] = []
    cursor = 0
    for emote in emotes:
        if emote.start < cursor or emote.end <= emote.start or emote.end > len(text):
            continue
        parts.append(_escape_text(text[cursor : emote.start]))
        source = sources.get(emote.emote_id, "")
        if source:
            safe_source = html.escape(source, quote=True)
            safe_name = html.escape(emote.name, quote=True)
            parts.append(
                f'<img src="{safe_source}" height="{image_size}" '
                f'alt="{safe_name}" title="{safe_name}" style="vertical-align: middle;">'
            )
        else:
            parts.append(_escape_text(text[emote.start : emote.end]))
        cursor = emote.end
    parts.append(_escape_text(text[cursor:]))
    return "".join(parts)


def _escape_text(value: str) -> str:
    return html.escape(value).replace("\n", "<br>")
