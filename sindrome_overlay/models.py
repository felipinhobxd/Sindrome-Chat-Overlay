from __future__ import annotations

import colorsys
import hashlib
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

_HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
_OVERLAY_BACKGROUND = "#0B101B"
_MINIMUM_NAME_CONTRAST = 4.5


@dataclass(slots=True, frozen=True)
class ChatEmote:
    emote_id: str
    start: int
    end: int
    name: str
    image_url: str = ""


@dataclass(slots=True, frozen=True)
class ChatBadge:
    set_id: str
    version: str
    room_id: str = ""

    @property
    def key(self) -> str:
        room = self.room_id or "global"
        return f"{room}:{self.set_id}/{self.version}"


@dataclass(slots=True, frozen=True)
class ChatMessage:
    platform: str
    author: str
    text: str
    author_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    author_colour: str = ""
    badges: tuple[str, ...] = ()
    amount: str = ""
    message_id: str = ""
    kind: str = "message"
    emotes: tuple[ChatEmote, ...] = ()
    badge_refs: tuple[ChatBadge, ...] = ()

    @property
    def safe_author_colour(self) -> str:
        identity = stable_user_identity(self.author_id, self.author)
        return resolve_author_colour(self.platform, identity, self.author_colour)


def stable_user_identity(author_id: str, author: str) -> str:
    """Return a stable cache/hash key, preferring the platform's unique user ID."""
    normalized_id = unicodedata.normalize("NFKC", author_id.strip())
    if normalized_id:
        return f"id:{normalized_id}"
    normalized_name = unicodedata.normalize("NFKC", author.strip()).casefold()
    return f"name:{normalized_name or 'unknown'}"


@lru_cache(maxsize=2_048)
def resolve_author_colour(platform: str, identity: str, supplied_colour: str = "") -> str:
    """Resolve an official Twitch colour or a deterministic, readable fallback."""
    normalized_platform = platform.strip().casefold()
    if normalized_platform == "twitch" and _HEX_COLOUR.fullmatch(supplied_colour):
        return ensure_readable_colour(supplied_colour)

    digest = hashlib.blake2s(
        f"{normalized_platform}:{identity}".encode("utf-8"),
        digest_size=8,
    ).digest()
    hue = int.from_bytes(digest[:2], "big") / 65_536
    saturation = 0.70 + (digest[2] / 255) * 0.12
    lightness = 0.62 + (digest[3] / 255) * 0.10
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    generated = _rgb_to_hex(red, green, blue)
    return ensure_readable_colour(generated)


def ensure_readable_colour(
    colour: str,
    background: str = _OVERLAY_BACKGROUND,
    minimum_contrast: float = _MINIMUM_NAME_CONTRAST,
) -> str:
    """Lighten a valid colour only as much as needed for the dark overlay."""
    if not _HEX_COLOUR.fullmatch(colour) or not _HEX_COLOUR.fullmatch(background):
        return "#B7C2D8"
    if colour_contrast_ratio(colour, background) >= minimum_contrast:
        return colour

    red, green, blue = _hex_to_rgb(colour)
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    lower = lightness
    upper = 1.0
    candidate = "#FFFFFF"
    for _ in range(12):
        midpoint = (lower + upper) / 2
        adjusted = _rgb_to_hex(*colorsys.hls_to_rgb(hue, midpoint, saturation))
        if colour_contrast_ratio(adjusted, background) >= minimum_contrast:
            candidate = adjusted
            upper = midpoint
        else:
            lower = midpoint
    return candidate


def colour_contrast_ratio(foreground: str, background: str = _OVERLAY_BACKGROUND) -> float:
    """Return the WCAG contrast ratio between two validated RGB hex colours."""
    if not _HEX_COLOUR.fullmatch(foreground) or not _HEX_COLOUR.fullmatch(background):
        return 1.0
    foreground_luminance = _relative_luminance(*_hex_to_rgb(foreground))
    background_luminance = _relative_luminance(*_hex_to_rgb(background))
    lighter = max(foreground_luminance, background_luminance)
    darker = min(foreground_luminance, background_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _hex_to_rgb(colour: str) -> tuple[float, float, float]:
    return tuple(int(colour[index : index + 2], 16) / 255 for index in (1, 3, 5))


def _rgb_to_hex(red: float, green: float, blue: float) -> str:
    channels = (round(max(0.0, min(1.0, channel)) * 255) for channel in (red, green, blue))
    return "#{:02X}{:02X}{:02X}".format(*channels)


def _relative_luminance(red: float, green: float, blue: float) -> float:
    def linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.replace("\x00", "").split())
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        if "simpleText" in value:
            return clean_text(value["simpleText"])
        if "runs" in value:
            return text_from_runs(value["runs"])
        if "text" in value:
            return clean_text(value["text"])
    if isinstance(value, (list, tuple)):
        return text_from_runs(value)
    return clean_text(str(value))


def text_from_runs(runs: Iterable[Any]) -> str:
    parts: list[str] = []
    for run in runs:
        if isinstance(run, str):
            parts.append(run)
            continue
        if not isinstance(run, dict):
            continue
        if "text" in run:
            parts.append(str(run["text"]))
            continue
        emoji = run.get("emoji")
        if isinstance(emoji, dict):
            shortcuts = emoji.get("shortcuts") or emoji.get("searchTerms") or []
            if shortcuts:
                parts.append(str(shortcuts[0]))
            elif emoji.get("emojiId"):
                parts.append(str(emoji["emojiId"]))
    return clean_text("".join(parts))


def parse_timestamp_usec(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(value) / 1_000_000, UTC)
    except (TypeError, ValueError, OSError):
        return datetime.now(UTC)
