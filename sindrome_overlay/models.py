from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(slots=True, frozen=True)
class ChatMessage:
    platform: str
    author: str
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    author_colour: str = ""
    badges: tuple[str, ...] = ()
    amount: str = ""
    message_id: str = ""
    kind: str = "message"

    @property
    def safe_author_colour(self) -> str:
        if _HEX_COLOUR.fullmatch(self.author_colour):
            return self.author_colour
        return "#B7C2D8"


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
