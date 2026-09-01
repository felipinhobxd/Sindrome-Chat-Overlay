from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import ChatMessage

EventKind = Literal["message", "status", "delete", "clear"]


@dataclass(slots=True, frozen=True)
class ProviderEvent:
    kind: EventKind
    platform: str
    message: ChatMessage | None = None
    text: str = ""
    message_id: str = ""
    state: str = ""
