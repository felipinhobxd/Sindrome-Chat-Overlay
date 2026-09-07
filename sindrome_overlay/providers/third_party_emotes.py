"""Third-party Twitch emote resolution (BetterTTV, 7TV, FrankerFaceZ).

The resolver fetches the global and channel emote catalogs once per
connection and lets providers augment parsed messages with image emotes for
matching tokens. Native Twitch emotes always take priority: tokens inside a
native emote's range are never replaced.

All network calls are best-effort with short timeouts; failures leave the map
empty and the overlay keeps rendering text fallbacks.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
from typing import Any

import requests

from ..models import ChatEmote, ChatMessage

_FETCH_TIMEOUT = (3.0, 6.0)
_MAX_CODE_LENGTH = 40
_MAX_MATCHES_PER_MESSAGE = 30

_BTTV_GLOBAL_URL = "https://api.betterttv.net/3/cached/emotes/global"
_BTTV_CHANNEL_URL = "https://api.betterttv.net/3/cached/users/twitch/{channel_id}"
_SEVENTV_GLOBAL_URL = "https://7tv.io/v3/emote-sets/global"
_SEVENTV_CHANNEL_URL = "https://7tv.io/v3/users/twitch/{channel_id}"
_FFZ_GLOBAL_URL = "https://api.frankerfacez.com/v1/set/global"
_FFZ_ROOM_URL = "https://api.frankerfacez.com/v1/room/id/{channel_id}"


def _bttv_emote_url(emote_id: str) -> str:
    return f"https://cdn.betterttv.net/emote/{emote_id}/2x"


def _seventv_emote_url(emote_id: str) -> str:
    return f"https://cdn.7tv.app/emote/{emote_id}/2x.webp"


def _ffz_url(value: Any) -> str:
    url = str(value or "").strip()
    if url.startswith("//"):
        url = f"https:{url}"
    return url if url.startswith("https://") else ""


def parse_bttv_payload(payload: Any) -> dict[str, str]:
    """Parses a BTTV global emote list or channel/shared emote payload."""
    codes: dict[str, str] = {}
    items: list[Any] = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for section in ("channelEmotes", "sharedEmotes"):
            section_value = payload.get(section)
            if isinstance(section_value, list):
                items.extend(section_value)
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or "").strip()
        emote_id = str(item.get("id") or "").strip()
        if code and emote_id:
            codes[code] = _bttv_emote_url(emote_id)
    return codes


def parse_seventv_payload(payload: Any) -> dict[str, str]:
    """Parses a 7TV emote set object or a user payload with an emote_set."""
    codes: dict[str, str] = {}
    emotes: list[Any] = []
    if isinstance(payload, dict):
        emote_set = payload.get("emote_set") if "emote_set" in payload else payload
        raw = emote_set.get("emotes") if isinstance(emote_set, dict) else None
        if isinstance(raw, list):
            emotes = raw
    for item in emotes:
        if not isinstance(item, dict):
            continue
        code = str(item.get("name") or "").strip()
        emote_id = str(item.get("id") or "").strip()
        if code and emote_id:
            codes[code] = _seventv_emote_url(emote_id)
    return codes


def parse_ffz_payload(payload: Any) -> dict[str, str]:
    """Parses an FFZ global or room payload, honouring the room's active set."""
    codes: dict[str, str] = {}
    if not isinstance(payload, dict):
        return codes
    sets = payload.get("sets")
    if not isinstance(sets, dict):
        return codes
    selected: list[Any] = []
    if "default_sets" in payload:
        for set_id in payload.get("default_sets") or []:
            chosen = sets.get(str(set_id))
            if isinstance(chosen, dict):
                selected.append(chosen)
    else:
        room = payload.get("room")
        active_set = room.get("set") if isinstance(room, dict) else None
        chosen = sets.get(str(active_set)) if active_set is not None else None
        if isinstance(chosen, dict):
            selected.append(chosen)
    for set_payload in selected:
        emoticons = set_payload.get("emoticons")
        if not isinstance(emoticons, list):
            continue
        for item in emoticons:
            if not isinstance(item, dict):
                continue
            code = str(item.get("name") or "").strip()
            urls = item.get("urls")
            url = ""
            if isinstance(urls, dict):
                url = _ffz_url(urls.get("2") or urls.get("1") or urls.get("4"))
            if code and url:
                codes[code] = url
    return codes


def _fetch_json(url: str) -> Any:
    response = requests.get(url, timeout=_FETCH_TIMEOUT)
    if response.status_code >= 400:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def _overlaps(occupied: list[tuple[int, int]], start: int, end: int) -> bool:
    for occupied_start, occupied_end in occupied:
        if start < occupied_end and occupied_start < end:
            return True
        if occupied_start >= end:
            break
    return False


def find_code_matches(
    text: str,
    codes: dict[str, str],
    occupied: Iterable[tuple[int, int]] = (),
) -> list[ChatEmote]:
    """Returns image emotes for tokens matching third-party codes.

    Tokens overlapping a native Twitch emote range are skipped so native
    rendering always wins.
    """
    if not text or not codes:
        return []
    occupied_sorted = sorted(occupied)
    matches: list[ChatEmote] = []
    cursor = 0
    for token in text.split():
        start = text.find(token, cursor)
        if start < 0:
            continue
        end = start + len(token)
        cursor = end
        if len(matches) >= _MAX_MATCHES_PER_MESSAGE:
            break
        url = codes.get(token)
        if not url or _overlaps(occupied_sorted, start, end):
            continue
        matches.append(
            ChatEmote(emote_id=token, start=start, end=end, name=token, image_url=url)
        )
    return matches


class ThirdPartyEmoteResolver:
    """Thread-safe code-to-URL map refreshed once per provider connection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._codes: dict[str, str] = {}
        self._stopped = threading.Event()
        self.log = logging.getLogger("sindrome_overlay.third-party-emotes")

    def stop(self) -> None:
        self._stopped.set()

    def clear(self) -> None:
        with self._lock:
            self._codes.clear()

    def load(self, channel_id: str) -> None:
        if self._stopped.is_set():
            return
        codes: dict[str, str] = {}
        try:
            payload = _fetch_json(_BTTV_GLOBAL_URL)
            if payload is not None:
                codes.update(parse_bttv_payload(payload))
            payload = _fetch_json(_SEVENTV_GLOBAL_URL)
            if payload is not None:
                codes.update(parse_seventv_payload(payload))
            payload = _fetch_json(_FFZ_GLOBAL_URL)
            if payload is not None:
                codes.update(parse_ffz_payload(payload))
            if channel_id.isdigit():
                payload = _fetch_json(_BTTV_CHANNEL_URL.format(channel_id=channel_id))
                if payload is not None:
                    codes.update(parse_bttv_payload(payload))
                payload = _fetch_json(_SEVENTV_CHANNEL_URL.format(channel_id=channel_id))
                if payload is not None:
                    codes.update(parse_seventv_payload(payload))
                payload = _fetch_json(_FFZ_ROOM_URL.format(channel_id=channel_id))
                if payload is not None:
                    codes.update(parse_ffz_payload(payload))
        except requests.RequestException as exc:
            self.log.debug("Third-party emote fetch failed: %s", exc)
            return
        codes = {
            code: url
            for code, url in codes.items()
            if code and len(code) <= _MAX_CODE_LENGTH and url.startswith("https://")
        }
        with self._lock:
            self._codes = codes
        if codes:
            self.log.info("Loaded %d third-party emotes.", len(codes))

    def augment(self, message: ChatMessage) -> ChatMessage:
        with self._lock:
            codes = dict(self._codes)
        if not codes or not message.text:
            return message
        native = [(emote.start, emote.end) for emote in message.emotes]
        extra = find_code_matches(message.text, codes, native)
        if not extra:
            return message
        return ChatMessage(
            platform=message.platform,
            author=message.author,
            text=message.text,
            author_id=message.author_id,
            timestamp=message.timestamp,
            author_colour=message.author_colour,
            badges=message.badges,
            amount=message.amount,
            message_id=message.message_id,
            kind=message.kind,
            emotes=message.emotes + tuple(extra),
            badge_refs=message.badge_refs,
        )
