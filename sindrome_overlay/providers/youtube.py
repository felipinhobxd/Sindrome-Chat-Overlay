from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from queue import Queue
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from ..events import ProviderEvent
from ..models import ChatMessage, clean_text, parse_timestamp_usec
from ..url_utils import normalize_youtube_input, youtube_video_id
from .base import BaseProvider

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIDEO_ID_IN_HTML = re.compile(r'(?:"videoId"\s*:\s*"|watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})')
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.7,en;q=0.5",
}


class StreamOffline(RuntimeError):
    pass


class ChatUnavailable(RuntimeError):
    pass


class RateLimited(RuntimeError):
    pass


@dataclass(slots=True)
class YouTubeBootstrap:
    video_id: str
    video_url: str
    continuation: str
    api_key: str
    client_name: str
    client_name_numeric: str
    client_version: str
    context: dict[str, Any]


def extract_json_object(text: str, marker: str) -> dict[str, Any] | None:
    marker_index = text.find(marker)
    if marker_index < 0:
        return None
    start = text.find("{", marker_index + len(marker))
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start : index + 1])
                    return value if isinstance(value, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def find_first_key(node: Any, key: str) -> Any:
    if isinstance(node, dict):
        if key in node:
            return node[key]
        for value in node.values():
            result = find_first_key(value, key)
            if result is not None:
                return result
    elif isinstance(node, list):
        for value in node:
            result = find_first_key(value, key)
            if result is not None:
                return result
    return None


def find_continuation(node: Any) -> tuple[str, int]:
    priorities = (
        "invalidationContinuationData",
        "timedContinuationData",
        "reloadContinuationData",
    )
    for continuation_type in priorities:
        value = find_first_key(node, continuation_type)
        if isinstance(value, dict) and value.get("continuation"):
            try:
                timeout_ms = int(value.get("timeoutMs") or 2_000)
            except (TypeError, ValueError):
                timeout_ms = 2_000
            return str(value["continuation"]), timeout_ms
    return "", 2_000


def find_live_video_id(node: Any) -> str:
    if isinstance(node, dict):
        video_id = node.get("videoId")
        if isinstance(video_id, str) and _VIDEO_ID_RE.fullmatch(video_id):
            snapshot = json.dumps(node, ensure_ascii=False, separators=(",", ":"))
            live_markers = (
                '"isLiveNow":true',
                '"style":"LIVE"',
                "BADGE_STYLE_TYPE_LIVE_NOW",
                "LIVE NOW",
                "AO VIVO",
            )
            if any(marker in snapshot for marker in live_markers):
                return video_id
        for value in node.values():
            result = find_live_video_id(value)
            if result:
                return result
    elif isinstance(node, list):
        for value in node:
            result = find_live_video_id(value)
            if result:
                return result
    return ""


def extract_video_id_from_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.path == "/watch":
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        return candidate if _VIDEO_ID_RE.fullmatch(candidate) else ""
    if parsed.netloc.lower().removeprefix("www.") == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.fullmatch(candidate) else ""
    return ""


def youtube_messages_from_actions(actions: Iterable[Any]) -> tuple[list[ChatMessage], list[str]]:
    messages: list[ChatMessage] = []
    deletions: list[str] = []

    for raw_action in actions:
        if not isinstance(raw_action, dict):
            continue
        replay = raw_action.get("replayChatItemAction")
        if isinstance(replay, dict):
            nested_messages, nested_deletions = youtube_messages_from_actions(
                replay.get("actions") or []
            )
            messages.extend(nested_messages)
            deletions.extend(nested_deletions)
            continue

        for delete_key in ("markChatItemAsDeletedAction", "removeChatItemAction"):
            delete_action = raw_action.get(delete_key)
            if isinstance(delete_action, dict) and delete_action.get("targetItemId"):
                deletions.append(str(delete_action["targetItemId"]))

        add_action = raw_action.get("addChatItemAction")
        if not isinstance(add_action, dict):
            continue
        item = add_action.get("item")
        if not isinstance(item, dict):
            continue
        parsed = _message_from_renderer(item)
        if parsed is not None:
            messages.append(parsed)

    return messages, deletions


def _message_from_renderer(item: dict[str, Any]) -> ChatMessage | None:
    renderer_types = (
        ("liveChatTextMessageRenderer", "message"),
        ("liveChatPaidMessageRenderer", "paid"),
        ("liveChatPaidStickerRenderer", "paid"),
        ("liveChatMembershipItemRenderer", "membership"),
        ("liveChatSponsorshipsGiftPurchaseAnnouncementRenderer", "membership"),
        ("liveChatSponsorshipsGiftRedemptionAnnouncementRenderer", "membership"),
    )
    renderer: dict[str, Any] | None = None
    kind = "message"
    for key, candidate_kind in renderer_types:
        value = item.get(key)
        if isinstance(value, dict):
            renderer = value
            kind = candidate_kind
            break
    if renderer is None:
        return None

    author = clean_text(renderer.get("authorName")) or "YouTube"
    text = clean_text(renderer.get("message"))
    if not text:
        text = clean_text(renderer.get("headerSubtext"))
    if not text:
        text = clean_text(renderer.get("primaryText"))
    if not text:
        text = clean_text(renderer.get("subtext"))
    if not text and kind == "paid":
        text = "Enviou um Super Chat / Super Sticker"
    if not text and kind == "membership":
        text = "Tornou-se membro do canal"
    if not text:
        return None

    badges: list[str] = []
    for badge in renderer.get("authorBadges") or []:
        if not isinstance(badge, dict):
            continue
        badge_renderer = badge.get("liveChatAuthorBadgeRenderer") or {}
        label = clean_text(badge_renderer.get("tooltip"))
        if label:
            badges.append(label.upper())

    return ChatMessage(
        platform="youtube",
        author=author,
        text=text,
        timestamp=parse_timestamp_usec(renderer.get("timestampUsec")),
        author_colour="#FF5C6C",
        badges=tuple(badges),
        amount=clean_text(renderer.get("purchaseAmountText")),
        message_id=str(renderer.get("id") or ""),
        kind=kind,
    )


def official_message_from_item(item: dict[str, Any]) -> ChatMessage | None:
    snippet = item.get("snippet") or {}
    author_details = item.get("authorDetails") or {}
    if not isinstance(snippet, dict) or not isinstance(author_details, dict):
        return None

    event_type = str(snippet.get("type") or "")
    text = clean_text(snippet.get("displayMessage"))
    amount = ""
    kind = "message"
    if event_type == "superChatEvent":
        details = snippet.get("superChatDetails") or {}
        text = clean_text(details.get("userComment")) or text or "Enviou um Super Chat"
        amount = clean_text(details.get("amountDisplayString"))
        kind = "paid"
    elif event_type == "superStickerEvent":
        details = snippet.get("superStickerDetails") or {}
        amount = clean_text(details.get("amountDisplayString"))
        text = text or "Enviou um Super Sticker"
        kind = "paid"
    elif event_type in {
        "newSponsorEvent",
        "memberMilestoneChatEvent",
        "membershipGiftingEvent",
        "giftMembershipReceivedEvent",
    }:
        text = text or "Evento de membro do canal"
        kind = "membership"
    if not text:
        return None

    badges: list[str] = []
    if author_details.get("isChatOwner"):
        badges.append("DONO")
    if author_details.get("isChatModerator"):
        badges.append("MOD")
    if author_details.get("isChatSponsor"):
        badges.append("MEMBRO")

    timestamp = datetime.now(UTC)
    published_at = snippet.get("publishedAt")
    if isinstance(published_at, str):
        try:
            timestamp = datetime.fromisoformat(published_at)
        except ValueError:
            pass

    return ChatMessage(
        platform="youtube",
        author=clean_text(author_details.get("displayName")) or "YouTube",
        text=text,
        timestamp=timestamp,
        author_colour="#FF5C6C",
        badges=tuple(badges),
        amount=amount,
        message_id=str(item.get("id") or ""),
        kind=kind,
    )


class YouTubeProvider(BaseProvider):
    platform = "youtube"

    def __init__(
        self,
        events: Queue[ProviderEvent],
        user_input: str,
        api_key: str = "",
    ) -> None:
        super().__init__(events)
        self.user_input = normalize_youtube_input(user_input)
        self.user_api_key = api_key.strip()
        self.session = requests.Session()
        self.session.headers.update(_BROWSER_HEADERS)
        self.session.cookies.set("SOCS", "CAI", domain=".youtube.com")
        self._seen_ids: set[str] = set()
        self._seen_order: deque[str] = deque(maxlen=3_000)

    def stop(self) -> None:
        super().stop()
        self.session.close()

    def run(self) -> None:
        delay = 3.0
        while not self.stop_event.is_set():
            try:
                self.emit_status("connecting", "Procurando a live…")
                video_id = self._resolve_video_id()
                if self.user_api_key:
                    self._run_official_api(video_id)
                else:
                    self._run_innertube(video_id)
                delay = 3.0
            except StreamOffline:
                self.emit_status("waiting", "Aguardando a próxima live")
                if self.wait(30):
                    break
            except RateLimited:
                self.emit_status("error", "YouTube limitou o acesso; tentando em 60s")
                if self.wait(60):
                    break
            except Exception as exc:  # noqa: BLE001 - remote network/format boundary
                if self.stop_event.is_set():
                    break
                self.log.warning("YouTube reconnect: %s", exc)
                self.emit_status("waiting", f"Reconectando em {int(delay)}s")
                if self.wait(delay):
                    break
                delay = min(delay * 2, 60.0)
        self.emit_status("stopped", "Desconectado")

    def _resolve_video_id(self) -> str:
        direct_id = youtube_video_id(self.user_input)
        if direct_id:
            return direct_id

        response = self._get(self.user_input)
        redirected_id = extract_video_id_from_url(response.url)
        if redirected_id:
            return redirected_id

        initial_data = (
            extract_json_object(response.text, "var ytInitialData")
            or extract_json_object(response.text, "ytInitialData =")
            or extract_json_object(response.text, 'window["ytInitialData"]')
        )
        if initial_data:
            live_id = find_live_video_id(initial_data)
            if live_id:
                return live_id

        # Some /live responses are watch pages without a redirect.
        if '"isLiveNow":true' in response.text or "BADGE_STYLE_TYPE_LIVE_NOW" in response.text:
            match = _VIDEO_ID_IN_HTML.search(response.text)
            if match:
                return match.group(1)
        raise StreamOffline("Nenhuma transmissão ao vivo foi encontrada.")

    def _run_innertube(self, video_id: str) -> None:
        bootstrap = self._bootstrap_chat(video_id)
        continuation = bootstrap.continuation
        self.emit_status("connected", "Ao vivo · modo automático")

        failures = 0
        while not self.stop_event.is_set():
            url = (
                "https://www.youtube.com/youtubei/v1/live_chat/get_live_chat"
                f"?key={bootstrap.api_key}&prettyPrint=false"
            )
            headers = {
                "Origin": "https://www.youtube.com",
                "Referer": bootstrap.video_url,
                "X-YouTube-Client-Name": bootstrap.client_name_numeric,
                "X-YouTube-Client-Version": bootstrap.client_version,
            }
            try:
                response = self.session.post(
                    url,
                    json={"context": bootstrap.context, "continuation": continuation},
                    headers=headers,
                    timeout=(10, 25),
                )
            except requests.RequestException as exc:
                failures += 1
                if failures >= 3:
                    raise ConnectionError("Falha ao consultar o chat do YouTube.") from exc
                if self.wait(min(2**failures, 10)):
                    return
                continue

            if response.status_code == 429:
                raise RateLimited()
            if response.status_code in {401, 403}:
                bootstrap = self._bootstrap_chat(video_id)
                continuation = bootstrap.continuation
                failures = 0
                continue
            if response.status_code >= 400:
                raise ConnectionError(f"YouTube respondeu HTTP {response.status_code}.")

            try:
                payload = response.json()
            except ValueError as exc:
                raise ConnectionError("Resposta inválida do YouTube.") from exc

            live = (payload.get("continuationContents") or {}).get("liveChatContinuation")
            if not isinstance(live, dict):
                raise ChatUnavailable("A live terminou ou o chat foi desativado.")

            messages, deletions = youtube_messages_from_actions(live.get("actions") or [])
            for message in messages:
                self._emit_once(message)
            for message_id in deletions:
                self.emit_delete(message_id)

            next_continuation, timeout_ms = find_continuation(live.get("continuations") or [])
            if not next_continuation:
                raise ChatUnavailable("O chat da live foi encerrado.")
            continuation = next_continuation
            failures = 0
            if self.wait(max(1.0, min(timeout_ms / 1000, 15.0))):
                return

    def _bootstrap_chat(self, video_id: str) -> YouTubeBootstrap:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        response = self._get(video_url)
        html = response.text
        initial_data = (
            extract_json_object(html, "var ytInitialData")
            or extract_json_object(html, "ytInitialData =")
            or extract_json_object(html, 'window["ytInitialData"]')
        )
        if not initial_data:
            raise ChatUnavailable("Não foi possível ler os dados da live.")

        live_renderer = find_first_key(initial_data, "liveChatRenderer")
        if not isinstance(live_renderer, dict):
            raise ChatUnavailable("A live não possui chat público ativo.")
        continuation, _ = find_continuation(live_renderer.get("continuations") or live_renderer)
        if not continuation:
            raise ChatUnavailable("O YouTube não forneceu acesso ao chat.")

        api_key = _extract_string(html, "INNERTUBE_API_KEY")
        client_name = _extract_string(html, "INNERTUBE_CLIENT_NAME") or "WEB"
        client_version = _extract_string(html, "INNERTUBE_CLIENT_VERSION")
        client_name_numeric = _extract_number(html, "INNERTUBE_CONTEXT_CLIENT_NAME") or "1"
        if not api_key or not client_version:
            raise ChatUnavailable("Configuração interna do YouTube não encontrada.")

        context = extract_json_object(html, '"INNERTUBE_CONTEXT"') or {
            "client": {
                "hl": "pt-BR",
                "gl": "BR",
                "clientName": client_name,
                "clientVersion": client_version,
            }
        }
        client = context.setdefault("client", {})
        if isinstance(client, dict):
            client.setdefault("hl", "pt-BR")
            client.setdefault("gl", "BR")
            client.setdefault("clientName", client_name)
            client.setdefault("clientVersion", client_version)
            visitor_data = _extract_string(html, "VISITOR_DATA")
            if visitor_data:
                client.setdefault("visitorData", visitor_data)

        return YouTubeBootstrap(
            video_id=video_id,
            video_url=video_url,
            continuation=continuation,
            api_key=api_key,
            client_name=client_name,
            client_name_numeric=client_name_numeric,
            client_version=client_version,
            context=context,
        )

    def _run_official_api(self, video_id: str) -> None:
        details = self._get_json(
            "https://www.googleapis.com/youtube/v3/videos",
            params={
                "part": "liveStreamingDetails",
                "id": video_id,
                "key": self.user_api_key,
            },
        )
        items = details.get("items") or []
        if not items:
            raise StreamOffline("A transmissão não foi encontrada.")
        live_details = items[0].get("liveStreamingDetails") or {}
        live_chat_id = live_details.get("activeLiveChatId")
        if not live_chat_id:
            raise ChatUnavailable("A transmissão não possui chat ativo.")

        self.emit_status("connected", "Ao vivo · API oficial")
        page_token = ""
        while not self.stop_event.is_set():
            params = {
                "part": "id,snippet,authorDetails",
                "liveChatId": live_chat_id,
                "maxResults": 200,
                "key": self.user_api_key,
            }
            if page_token:
                params["pageToken"] = page_token
            payload = self._get_json(
                "https://www.googleapis.com/youtube/v3/liveChat/messages",
                params=params,
            )
            for item in payload.get("items") or []:
                if isinstance(item, dict):
                    message = official_message_from_item(item)
                    if message:
                        self._emit_once(message)
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                raise ChatUnavailable("O chat oficial foi encerrado.")
            try:
                interval = int(payload.get("pollingIntervalMillis") or 5_000) / 1000
            except (TypeError, ValueError):
                interval = 5.0
            if self.wait(max(1.0, min(interval, 15.0))):
                return

    def _emit_once(self, message: ChatMessage) -> None:
        message_id = message.message_id
        if not message_id:
            self.emit_message(message)
            return
        if message_id in self._seen_ids:
            return
        if len(self._seen_order) == self._seen_order.maxlen:
            oldest = self._seen_order.popleft()
            self._seen_ids.discard(oldest)
        self._seen_order.append(message_id)
        self._seen_ids.add(message_id)
        self.emit_message(message)

    def _get(self, url: str) -> requests.Response:
        try:
            response = self.session.get(url, timeout=(10, 25), allow_redirects=True)
        except requests.RequestException as exc:
            raise ConnectionError("Não foi possível acessar o YouTube.") from exc
        if response.status_code == 429 or "/sorry/" in response.url:
            raise RateLimited()
        if response.status_code >= 400:
            raise ConnectionError(f"YouTube respondeu HTTP {response.status_code}.")
        return response

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.session.get(url, params=params, timeout=(10, 25))
        except requests.RequestException as exc:
            raise ConnectionError("Falha ao acessar a API do YouTube.") from exc
        if response.status_code == 429:
            raise RateLimited()
        if response.status_code >= 400:
            try:
                reason = response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                reason = f"HTTP {response.status_code}"
            raise ChatUnavailable(f"API do YouTube: {reason}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ConnectionError("A API do YouTube retornou dados inválidos.") from exc
        if not isinstance(payload, dict):
            raise ConnectionError("A API do YouTube retornou dados inesperados.")
        return payload


def _extract_string(html: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"((?:\\.|[^"\\])*)"', html)
    if not match:
        return ""
    try:
        return json.loads(f'"{match.group(1)}"')
    except json.JSONDecodeError:
        return match.group(1)


def _extract_number(html: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"?(\d+)"?', html)
    return match.group(1) if match else ""
