from __future__ import annotations

import json
import logging
import threading
from collections import deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .emotes import twitch_emote_url
from .models import ChatEmote, ChatMessage

_HOST = "127.0.0.1"
_POLL_INTERVAL_MS = 300


@dataclass(frozen=True, slots=True)
class ObsSourceConfig:
    port: int = 8765
    max_messages: int = 100
    font_size: int = 20
    show_platform_labels: bool = False
    show_badges: bool = True
    show_timestamps: bool = False
    message_background_opacity: int = 72

    def normalized(self) -> "ObsSourceConfig":
        return ObsSourceConfig(
            port=max(0, min(65535, int(self.port))),
            max_messages=max(20, min(500, int(self.max_messages))),
            font_size=max(11, min(40, int(self.font_size))),
            show_platform_labels=bool(self.show_platform_labels),
            show_badges=bool(self.show_badges),
            show_timestamps=bool(self.show_timestamps),
            message_background_opacity=max(
                0,
                min(100, int(self.message_background_opacity)),
            ),
        )


class _LocalObsHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class ObsChatSourceServer:
    """Local-only HTTP source consumed by OBS Browser Source.

    The server intentionally uses polling instead of a third-party websocket stack. It is
    bound to 127.0.0.1 only, never exposes chat on the LAN, and keeps an OBS-specific bounded
    history that is independent from the desktop overlay's message expiry timer.
    """

    def __init__(self, logger: logging.Logger, config: ObsSourceConfig | None = None) -> None:
        self.log = logger
        self._config = (config or ObsSourceConfig()).normalized()
        self._messages: deque[dict[str, Any]] = deque(maxlen=self._config.max_messages)
        self._revision = 0
        self._lock = threading.RLock()
        self._httpd: _LocalObsHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._last_error = ""

    @property
    def running(self) -> bool:
        return self._httpd is not None and self._thread is not None and self._thread.is_alive()

    @property
    def requested_port(self) -> int:
        return self._config.port

    @property
    def bound_port(self) -> int:
        server = self._httpd
        if server is None:
            return 0
        return int(server.server_address[1])

    @property
    def url(self) -> str:
        port = self.bound_port or self._config.port
        return f"http://{_HOST}:{port}/obs-chat"

    @property
    def last_error(self) -> str:
        return self._last_error

    def start(self) -> bool:
        if self.running:
            return True
        self.stop()
        try:
            server = _LocalObsHTTPServer((_HOST, self._config.port), _ObsRequestHandler)
        except OSError as exc:
            self._last_error = str(exc)
            self.log.warning("Unable to start the OBS browser source: %s", exc)
            return False

        server.obs_source = self  # type: ignore[attr-defined]
        self._httpd = server
        self._last_error = ""
        thread = threading.Thread(
            target=server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="SindromeObsBrowserSource",
            daemon=True,
        )
        self._thread = thread
        thread.start()
        self.log.info("OBS browser source listening on %s", self.url)
        return True

    def stop(self) -> None:
        server = self._httpd
        thread = self._thread
        self._httpd = None
        self._thread = None
        if server is not None:
            try:
                server.shutdown()
            except OSError:
                pass
            try:
                server.server_close()
            except OSError:
                pass
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def configure(self, config: ObsSourceConfig) -> None:
        normalized = config.normalized()
        with self._lock:
            old = list(self._messages)
            self._config = normalized
            self._messages = deque(old[-normalized.max_messages :], maxlen=normalized.max_messages)
            self._revision += 1

    def replace_messages(self, messages: list[ChatMessage]) -> None:
        payloads = [message_payload(message) for message in messages[-self._config.max_messages :]]
        with self._lock:
            self._messages = deque(payloads, maxlen=self._config.max_messages)
            self._revision += 1

    def publish_message(self, message: ChatMessage) -> None:
        payload = message_payload(message)
        with self._lock:
            message_id = str(payload.get("message_id") or "")
            if message_id and any(item.get("message_id") == message_id for item in self._messages):
                return
            self._messages.append(payload)
            self._revision += 1

    def remove_message(self, message_id: str) -> None:
        if not message_id:
            return
        with self._lock:
            retained = [item for item in self._messages if item.get("message_id") != message_id]
            if len(retained) == len(self._messages):
                return
            self._messages = deque(retained, maxlen=self._config.max_messages)
            self._revision += 1

    def clear_messages(self, platform: str = "") -> None:
        with self._lock:
            if platform:
                retained = [item for item in self._messages if item.get("platform") != platform]
            else:
                retained = []
            if len(retained) == len(self._messages):
                return
            self._messages = deque(retained, maxlen=self._config.max_messages)
            self._revision += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            config = self._config
            return {
                "revision": self._revision,
                "poll_interval_ms": _POLL_INTERVAL_MS,
                "config": {
                    "font_size": config.font_size,
                    "show_platform_labels": config.show_platform_labels,
                    "show_badges": config.show_badges,
                    "show_timestamps": config.show_timestamps,
                    "message_background_opacity": config.message_background_opacity,
                },
                "messages": list(self._messages),
            }


def message_payload(message: ChatMessage) -> dict[str, Any]:
    return {
        "platform": message.platform,
        "author": message.author,
        "author_colour": message.safe_author_colour,
        "badges": list(message.badges[:3]),
        "amount": message.amount,
        "message_id": message.message_id,
        "kind": message.kind,
        "timestamp": message.timestamp.astimezone().strftime("%H:%M"),
        "segments": _message_segments(message),
    }


def _message_segments(message: ChatMessage) -> list[dict[str, str]]:
    if not message.emotes:
        return [{"type": "text", "text": message.text}]

    segments: list[dict[str, str]] = []
    cursor = 0
    for emote in sorted(message.emotes, key=lambda item: (item.start, item.end)):
        if emote.start < cursor or emote.end <= emote.start or emote.end > len(message.text):
            continue
        if emote.start > cursor:
            segments.append({"type": "text", "text": message.text[cursor : emote.start]})
        url = _emote_url(message.platform, emote)
        if url:
            segments.append(
                {
                    "type": "emote",
                    "url": url,
                    "name": emote.name or message.text[emote.start : emote.end],
                }
            )
        else:
            segments.append({"type": "text", "text": message.text[emote.start : emote.end]})
        cursor = emote.end
    if cursor < len(message.text):
        segments.append({"type": "text", "text": message.text[cursor:]})
    return segments or [{"type": "text", "text": message.text}]


def _emote_url(platform: str, emote: ChatEmote) -> str:
    if platform.casefold() == "twitch":
        try:
            return twitch_emote_url(emote.emote_id)
        except ValueError:
            return ""
    if platform.casefold() != "youtube" or not emote.image_url:
        return ""
    parsed = urlsplit(emote.image_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return ""
    if host == "yt3.ggpht.com" or host.endswith(".ggpht.com"):
        return emote.image_url
    if host == "googleusercontent.com" or host.endswith(".googleusercontent.com"):
        return emote.image_url
    return ""


class _ObsRequestHandler(BaseHTTPRequestHandler):
    server_version = "SindromeOBS/1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP API
        source: ObsChatSourceServer = self.server.obs_source  # type: ignore[attr-defined]
        parsed = urlsplit(self.path)
        if parsed.path in {"/", "/obs-chat"}:
            self._send_html(_OBS_HTML)
            return
        if parsed.path == "/api/state":
            query = parse_qs(parsed.query)
            try:
                known_revision = int((query.get("revision") or ["-1"])[0])
            except ValueError:
                known_revision = -1
            snapshot = source.snapshot()
            if known_revision == snapshot["revision"]:
                self.send_response(204)
                self._common_headers()
                self.end_headers()
                return
            self._send_json(snapshot)
            return
        if parsed.path == "/health":
            self._send_json({"ok": True, "revision": source.snapshot()["revision"]})
            return
        self.send_error(404)

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _common_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; connect-src 'self'; "
            "img-src https://static-cdn.jtvnw.net https://*.ggpht.com "
            "https://*.googleusercontent.com data:; "
            "style-src 'unsafe-inline'; script-src 'unsafe-inline'",
        )

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._common_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._common_headers()
        self.end_headers()
        self.wfile.write(body)


_OBS_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sindrome OBS Chat Source</title>
<style>
:root {
  --font-size: 20px;
  --emote-size: 30px;
  --bubble-alpha: .72;
}
* { box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; background: transparent; }
body {
  font-family: "Segoe UI", Arial, sans-serif;
  color: #fff;
  font-size: var(--font-size);
  text-shadow: 0 1px 2px rgba(0,0,0,.85);
}
#chat {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  max-height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 5px;
  padding: 8px;
}
.chat-message {
  flex: 0 0 auto;
  min-width: 0;
  width: fit-content;
  max-width: 100%;
  padding: 5px 8px;
  border-radius: 7px;
  background: rgba(8, 12, 19, var(--bubble-alpha));
  overflow-wrap: anywhere;
  line-height: 1.28;
}
.platform {
  display: inline-block;
  margin-right: 5px;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: .62em;
  font-weight: 800;
  vertical-align: .12em;
  background: rgba(255,255,255,.14);
}
.platform.twitch { color: #c9a7ff; }
.platform.youtube { color: #ff8595; }
.badge {
  display: inline-block;
  margin-right: 4px;
  padding: 1px 4px;
  border-radius: 4px;
  font-size: .62em;
  font-weight: 800;
  vertical-align: .12em;
  background: rgba(255,255,255,.15);
  color: #e5eaf5;
}
.author { font-weight: 800; }
.amount {
  display: inline-block;
  margin-left: 5px;
  padding: 1px 5px;
  border-radius: 4px;
  color: #17120a;
  background: #f6b73c;
  font-weight: 800;
  font-size: .8em;
  text-shadow: none;
}
.message-text { white-space: pre-wrap; }
.emote {
  display: inline-block;
  height: var(--emote-size);
  width: auto;
  margin: -4px 1px;
  vertical-align: middle;
  object-fit: contain;
}
.timestamp { margin-right: 5px; color: #aab5cb; font-size: .72em; }
</style>
</head>
<body>
<div id="chat" aria-live="polite"></div>
<script>
(() => {
  const chat = document.getElementById('chat');
  let revision = -1;
  let interval = 300;

  function badgeName(value) {
    const text = String(value || '').toUpperCase();
    const aliases = {MODERATOR:'MOD', 'CHAT MODERATOR':'MOD', SUBSCRIBER:'SUB', VERIFIED:'✓'};
    return aliases[text] || text.slice(0, 9);
  }

  function appendTextSegments(parent, segments) {
    for (const segment of (segments || [])) {
      if (segment.type === 'emote' && segment.url) {
        const image = document.createElement('img');
        image.className = 'emote';
        image.src = segment.url;
        image.alt = segment.name || '';
        image.title = segment.name || '';
        parent.appendChild(image);
      } else {
        parent.appendChild(document.createTextNode(String(segment.text || '')));
      }
    }
  }

  function messageNode(message, config) {
    const row = document.createElement('div');
    row.className = `chat-message ${message.platform || ''} ${message.kind || ''}`;

    if (config.show_timestamps && message.timestamp) {
      const timestamp = document.createElement('span');
      timestamp.className = 'timestamp';
      timestamp.textContent = message.timestamp;
      row.appendChild(timestamp);
    }
    if (config.show_platform_labels) {
      const platform = document.createElement('span');
      platform.className = `platform ${message.platform || ''}`;
      platform.textContent = String(message.platform || '').toUpperCase();
      row.appendChild(platform);
    }
    if (config.show_badges) {
      for (const badge of (message.badges || []).slice(0, 3)) {
        const node = document.createElement('span');
        node.className = 'badge';
        node.textContent = badgeName(badge);
        row.appendChild(node);
      }
    }

    const author = document.createElement('span');
    author.className = 'author';
    author.style.color = message.author_colour || '#b7c2d8';
    author.textContent = message.author || 'Unknown';
    row.appendChild(author);
    row.appendChild(document.createTextNode(': '));

    const text = document.createElement('span');
    text.className = 'message-text';
    appendTextSegments(text, message.segments);
    row.appendChild(text);

    if (message.amount) {
      const amount = document.createElement('span');
      amount.className = 'amount';
      amount.textContent = message.amount;
      row.appendChild(amount);
    }
    return row;
  }

  function render(state) {
    const config = state.config || {};
    const fontSize = Math.max(11, Math.min(40, Number(config.font_size) || 20));
    const opacity = Math.max(0, Math.min(100, Number(config.message_background_opacity) || 0)) / 100;
    document.documentElement.style.setProperty('--font-size', `${fontSize}px`);
    document.documentElement.style.setProperty('--emote-size', `${Math.round(fontSize * 1.5)}px`);
    document.documentElement.style.setProperty('--bubble-alpha', String(opacity));

    const fragment = document.createDocumentFragment();
    for (const message of (state.messages || [])) {
      fragment.appendChild(messageNode(message, config));
    }
    chat.replaceChildren(fragment);
    chat.scrollTop = chat.scrollHeight;
  }

  async function poll() {
    try {
      const response = await fetch(`/api/state?revision=${encodeURIComponent(revision)}`, {cache:'no-store'});
      if (response.status === 200) {
        const state = await response.json();
        revision = Number(state.revision);
        interval = Math.max(150, Number(state.poll_interval_ms) || 300);
        render(state);
      }
    } catch (_) {
      // Keep retrying silently. OBS reconnects as soon as the desktop app is available again.
    } finally {
      window.setTimeout(poll, interval);
    }
  }

  poll();
})();
</script>
</body>
</html>
"""
