from __future__ import annotations

import random
import socket
import ssl
from datetime import UTC, datetime
from queue import Queue

from ..events import ProviderEvent
from ..i18n import normalize_language, tr
from ..models import ChatMessage
from ..url_utils import normalize_twitch_channel
from .base import BaseProvider


def decode_irc_tag(value: str) -> str:
    replacements = {
        r"\s": " ",
        r"\:": ";",
        r"\r": "\r",
        r"\n": "\n",
        r"\\": "\\",
    }
    result = value
    for encoded, decoded in replacements.items():
        result = result.replace(encoded, decoded)
    return result


def parse_irc_tags(raw: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in raw.split(";"):
        key, _, value = item.partition("=")
        tags[key] = decode_irc_tag(value)
    return tags


def parse_twitch_line(line: str, language: str = "en") -> tuple[str, ChatMessage | str | None]:
    tags: dict[str, str] = {}
    rest = line
    if rest.startswith("@"):
        raw_tags, _, rest = rest[1:].partition(" ")
        tags = parse_irc_tags(raw_tags)

    if " PRIVMSG " in rest and " :" in rest:
        prefix, message_text = rest.split(" :", 1)
        fallback_author = prefix.split("!", 1)[0].lstrip(":")
        author = tags.get("display-name") or fallback_author or "Twitch"
        badge_names = tuple(
            badge.split("/", 1)[0].upper() for badge in tags.get("badges", "").split(",") if badge
        )
        amount = f"{tags['bits']} Bits" if tags.get("bits") else ""
        timestamp = datetime.now(UTC)
        if tags.get("tmi-sent-ts", "").isdigit():
            timestamp = datetime.fromtimestamp(
                int(tags["tmi-sent-ts"]) / 1000,
                UTC,
            )
        return (
            "message",
            ChatMessage(
                platform="twitch",
                author=author,
                text=message_text.strip(),
                timestamp=timestamp,
                author_colour=tags.get("color", ""),
                badges=badge_names,
                amount=amount,
                message_id=tags.get("id", ""),
                kind="bits" if amount else "message",
            ),
        )

    command = rest.split(" ", 2)[1] if rest.startswith(":") and " " in rest else ""
    if command == "USERNOTICE" or " USERNOTICE " in rest:
        text = tags.get("system-msg", tr(language, "twitch_event"))
        author = tags.get("display-name") or tags.get("login") or "Twitch"
        return (
            "message",
            ChatMessage(
                platform="twitch",
                author=author,
                text=text,
                author_colour=tags.get("color", ""),
                message_id=tags.get("id", ""),
                kind="event",
            ),
        )
    if " CLEARMSG " in rest:
        return "delete", tags.get("target-msg-id", "")
    if " CLEARCHAT " in rest:
        clear_target = rest.split(" CLEARCHAT ", 1)[1]
        # A trailing user means only that user's history was removed. Without
        # author IDs on older cards, leaving those cards alone is safer than
        # erasing the entire overlay.
        return ("other", None) if " :" in clear_target else ("clear", None)
    if " NOTICE " in rest:
        return "notice", rest.rsplit(" :", 1)[-1]
    if rest.startswith("PING"):
        return "ping", rest.removeprefix("PING").strip()
    if " RECONNECT" in rest:
        return "reconnect", None
    if " 001 " in rest or " ROOMSTATE " in rest:
        return "ready", None
    return "other", None


class TwitchProvider(BaseProvider):
    platform = "twitch"

    def __init__(self, events: Queue[ProviderEvent], channel: str, language: str = "en") -> None:
        super().__init__(events)
        self.language = normalize_language(language)
        self.channel = normalize_twitch_channel(channel, self.language)
        self._socket: ssl.SSLSocket | None = None

    def stop(self) -> None:
        super().stop()
        sock = self._socket
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def run(self) -> None:
        delay = 2.0
        while not self.stop_event.is_set():
            try:
                self._listen()
                delay = 2.0
            except Exception as exc:  # noqa: BLE001 - remote network boundary
                if self.stop_event.is_set():
                    break
                self.log.warning("Twitch reconnect: %s", exc)
                self.emit_status(
                    "waiting",
                    tr(self.language, "reconnecting", seconds=int(delay)),
                )
                if self.wait(delay):
                    break
                delay = min(delay * 2, 30.0)
        self.emit_status("stopped", tr(self.language, "disconnected"))

    def _listen(self) -> None:
        self.emit_status("connecting", tr(self.language, "connecting"))
        raw_socket = socket.create_connection(
            ("irc.chat.twitch.tv", 6697),
            timeout=15,
        )
        context = ssl.create_default_context()
        sock = context.wrap_socket(raw_socket, server_hostname="irc.chat.twitch.tv")
        sock.settimeout(1.0)
        self._socket = sock

        nick = f"justinfan{random.randint(10000, 99999)}"
        self._send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        self._send("PASS SCHMOOPIIE")
        self._send(f"NICK {nick}")
        self._send(f"JOIN #{self.channel}")

        buffer = ""
        announced = False
        try:
            while not self.stop_event.is_set():
                try:
                    chunk = sock.recv(8192)
                except TimeoutError:
                    continue
                if not chunk:
                    raise ConnectionError("Twitch closed the connection.")
                buffer += chunk.decode("utf-8", "replace")
                lines = buffer.split("\r\n")
                buffer = lines.pop()
                for line in lines:
                    kind, payload = parse_twitch_line(line, self.language)
                    if kind == "ping":
                        self._send(f"PONG {payload}")
                    elif kind == "message" and isinstance(payload, ChatMessage):
                        if not announced:
                            self.emit_status("connected", tr(self.language, "live"))
                            announced = True
                        self.emit_message(payload)
                    elif kind == "delete" and isinstance(payload, str):
                        self.emit_delete(payload)
                    elif kind == "clear":
                        self.emit_clear()
                    elif kind == "ready" and not announced:
                        self.emit_status("connected", tr(self.language, "connected"))
                        announced = True
                    elif kind == "notice" and isinstance(payload, str):
                        if "authentication failed" in payload.lower():
                            raise PermissionError(payload)
                        self.log.info("Twitch notice: %s", payload)
                    elif kind == "reconnect":
                        raise ConnectionError("Twitch requested a reconnect.")
        finally:
            self._socket = None
            try:
                sock.close()
            except OSError:
                pass

    def _send(self, line: str) -> None:
        if self._socket is None:
            return
        self._socket.sendall((line + "\r\n").encode("utf-8"))
