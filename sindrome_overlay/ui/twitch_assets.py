from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .. import __version__
from ..emotes import twitch_emote_url
from ..models import ChatBadge
from ..settings import app_data_dir

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_GLOBAL_BADGES_URL = "https://badges.twitch.tv/v1/badges/global/display"
_CHANNEL_BADGES_URL = "https://badges.twitch.tv/v1/badges/channels/{room_id}/display"
_MAX_ACTIVE_DOWNLOADS = 6
_MAX_QUEUED_DOWNLOADS = 128
_MAX_MEMORY_IMAGES = 48
_MAX_RETRY_ENTRIES = 256


class TwitchAssetCache(QObject):
    emote_ready = Signal(str)
    badge_ready = Signal()

    def __init__(self, logger: logging.Logger, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.log = logger
        self.cache_dir = app_data_dir() / "twitch-assets"
        self._memory_sources: OrderedDict[str, str] = OrderedDict()
        self._pending: set[str] = set()
        self._queued: OrderedDict[str, tuple[str, Path, str, str]] = OrderedDict()
        self._retry_after: dict[str, float] = {}
        self._badge_urls: dict[str, str] = {}
        self._manifest_pending: set[str] = set()
        self._manifest_loaded: set[str] = set()
        self._manifest_retry_after: dict[str, float] = {}
        self._writes_since_prune = 0
        self._network = QNetworkAccessManager(self)
        self._network.finished.connect(self._download_finished)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._prune_disk_cache()
        except OSError as exc:
            self.log.debug("Unable to prepare the Twitch asset cache: %s", exc)

    def emote_source(self, emote_id: str) -> str:
        if not _SAFE_ID.fullmatch(emote_id):
            return ""
        asset_key = f"emote:{emote_id}"
        path = self.cache_dir / f"emote-{emote_id}.png"
        source = self._cached_source(asset_key, path)
        if source:
            return source
        if self._may_retry(asset_key):
            self._start_image_download(
                asset_key,
                twitch_emote_url(emote_id),
                path,
                "emote",
                emote_id,
            )
        return ""

    def badge_source(self, badge: ChatBadge) -> str:
        if not _SAFE_ID.fullmatch(badge.set_id) or not _SAFE_ID.fullmatch(badge.version):
            return ""

        scopes = ["global"]
        if badge.room_id.isdigit():
            scopes.append(badge.room_id)

        for scope in scopes:
            badge_key = self._badge_key(scope, badge.set_id, badge.version)
            asset_key = f"badge:{badge_key}"
            path = self._badge_path(scope, badge.set_id, badge.version)
            source = self._cached_source(asset_key, path)
            if source:
                return source
            image_url = self._badge_urls.get(badge_key, "")
            if image_url and self._may_retry(asset_key):
                self._start_image_download(asset_key, image_url, path, "badge", badge_key)

        for scope in scopes:
            self._request_badge_manifest(scope)
        return ""

    def _start_image_download(
        self,
        asset_key: str,
        url: str,
        path: Path,
        asset_type: str,
        signal_key: str,
    ) -> None:
        if not self._is_trusted_image_url(url):
            self._remember_retry(asset_key, 300)
            return
        if asset_key in self._pending or asset_key in self._queued:
            return
        if len(self._pending) >= _MAX_ACTIVE_DOWNLOADS:
            if len(self._queued) >= _MAX_QUEUED_DOWNLOADS:
                self._remember_retry(asset_key, 2)
                return
            self._queued[asset_key] = (url, path, asset_type, signal_key)
            return
        self._begin_image_download(asset_key, url, path, asset_type, signal_key)

    def _begin_image_download(
        self,
        asset_key: str,
        url: str,
        path: Path,
        asset_type: str,
        signal_key: str,
    ) -> None:
        self._pending.add(asset_key)
        reply = self._network.get(self._request(url))
        reply.setProperty("download_kind", "image")
        reply.setProperty("asset_key", asset_key)
        reply.setProperty("asset_type", asset_type)
        reply.setProperty("signal_key", signal_key)
        reply.setProperty("cache_path", str(path))

    def _request_badge_manifest(self, scope: str) -> None:
        if scope in self._manifest_loaded or scope in self._manifest_pending:
            return
        if time.monotonic() < self._manifest_retry_after.get(scope, 0.0):
            return
        if scope != "global" and not scope.isdigit():
            return
        url = _GLOBAL_BADGES_URL if scope == "global" else _CHANNEL_BADGES_URL.format(room_id=scope)
        self._manifest_pending.add(scope)
        reply = self._network.get(self._request(url))
        reply.setProperty("download_kind", "badge_manifest")
        reply.setProperty("manifest_scope", scope)

    def _download_finished(self, reply: QNetworkReply) -> None:
        try:
            kind = str(reply.property("download_kind") or "")
            if kind == "image":
                self._image_download_finished(reply)
            elif kind == "badge_manifest":
                self._manifest_download_finished(reply)
        except Exception as exc:  # noqa: BLE001 - Qt network callback boundary
            self.log.debug("Unable to process a Twitch asset response: %s", exc)
        finally:
            reply.deleteLater()
            self._start_queued_downloads()

    def _image_download_finished(self, reply: QNetworkReply) -> None:
        asset_key = str(reply.property("asset_key") or "")
        asset_type = str(reply.property("asset_type") or "")
        signal_key = str(reply.property("signal_key") or "")
        self._pending.discard(asset_key)
        if not self._reply_succeeded(reply):
            self._mark_failed(asset_key, reply.errorString())
            return

        data = bytes(reply.readAll())
        if len(data) > 2_000_000:
            self._mark_failed(asset_key, "image exceeds the 2 MB limit")
            return
        image = QImage.fromData(data)
        if image.isNull():
            self._mark_failed(asset_key, "invalid image data")
            return

        path = Path(str(reply.property("cache_path") or ""))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(data)
            os.replace(temporary, path)
            self._writes_since_prune += 1
            if self._writes_since_prune >= 50:
                self._prune_disk_cache()
                self._writes_since_prune = 0
        except OSError as exc:
            encoded = base64.b64encode(data).decode("ascii")
            self._memory_sources[asset_key] = f"data:image/png;base64,{encoded}"
            self._memory_sources.move_to_end(asset_key)
            while len(self._memory_sources) > _MAX_MEMORY_IMAGES:
                self._memory_sources.popitem(last=False)
            self.log.debug("Unable to persist Twitch asset %s: %s", asset_key, exc)

        self._retry_after.pop(asset_key, None)
        if asset_type == "emote":
            self.emote_ready.emit(signal_key)
        else:
            self.badge_ready.emit()

    def _manifest_download_finished(self, reply: QNetworkReply) -> None:
        scope = str(reply.property("manifest_scope") or "")
        self._manifest_pending.discard(scope)
        if not self._reply_succeeded(reply):
            self._manifest_retry_after[scope] = time.monotonic() + 300
            self.log.debug(
                "Unable to download Twitch badge manifest %s: %s", scope, reply.errorString()
            )
            return

        data = bytes(reply.readAll())
        if len(data) > 5_000_000:
            self._manifest_retry_after[scope] = time.monotonic() + 300
            return
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._manifest_retry_after[scope] = time.monotonic() + 300
            return

        self._load_badge_urls(scope, payload)
        self._manifest_loaded.add(scope)
        self._manifest_retry_after.pop(scope, None)
        self.badge_ready.emit()

    def _load_badge_urls(self, scope: str, payload: Any) -> None:
        if not isinstance(payload, dict):
            return
        badge_sets = payload.get("badge_sets")
        if not isinstance(badge_sets, dict):
            return
        for set_id, set_payload in badge_sets.items():
            if not isinstance(set_id, str) or not _SAFE_ID.fullmatch(set_id):
                continue
            versions = set_payload.get("versions") if isinstance(set_payload, dict) else None
            if not isinstance(versions, dict):
                continue
            for version, version_payload in versions.items():
                if not isinstance(version, str) or not _SAFE_ID.fullmatch(version):
                    continue
                if not isinstance(version_payload, dict):
                    continue
                image_url = str(
                    version_payload.get("image_url_4x")
                    or version_payload.get("image_url_2x")
                    or version_payload.get("image_url_1x")
                    or ""
                )
                if self._is_trusted_image_url(image_url):
                    self._badge_urls[self._badge_key(scope, set_id, version)] = image_url

    def _request(self, url: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(
            b"User-Agent",
            f"SindromeChatOverlay/{__version__}".encode("ascii"),
        )
        return request

    @staticmethod
    def _reply_succeeded(reply: QNetworkReply) -> bool:
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        return reply.error() == QNetworkReply.NetworkError.NoError and (
            status is None or int(status) < 400
        )

    @staticmethod
    def _is_trusted_image_url(url: str) -> bool:
        parsed = QUrl(url)
        host = parsed.host().lower()
        return parsed.scheme().lower() == "https" and (
            host == "static-cdn.jtvnw.net"
            or host == "badges.twitch.tv"
            or host.endswith(".twitch.tv")
        )

    def _cached_source(self, asset_key: str, path: Path) -> str:
        memory_source = self._memory_sources.get(asset_key)
        if memory_source:
            self._memory_sources.move_to_end(asset_key)
            return memory_source
        return QUrl.fromLocalFile(str(path)).toString() if path.is_file() else ""

    def _may_retry(self, asset_key: str) -> bool:
        return (
            asset_key not in self._pending
            and asset_key not in self._queued
            and time.monotonic() >= self._retry_after.get(asset_key, 0.0)
        )

    def _mark_failed(self, asset_key: str, reason: str) -> None:
        if not asset_key:
            return
        self._remember_retry(asset_key, 300)
        self.log.debug("Unable to download Twitch asset %s: %s", asset_key, reason)

    def _remember_retry(self, asset_key: str, delay_seconds: float) -> None:
        if len(self._retry_after) >= _MAX_RETRY_ENTRIES and asset_key not in self._retry_after:
            oldest_key = min(self._retry_after, key=self._retry_after.get)
            self._retry_after.pop(oldest_key, None)
        self._retry_after[asset_key] = time.monotonic() + delay_seconds

    def _start_queued_downloads(self) -> None:
        while self._queued and len(self._pending) < _MAX_ACTIVE_DOWNLOADS:
            asset_key, details = self._queued.popitem(last=False)
            url, path, asset_type, signal_key = details
            self._begin_image_download(asset_key, url, path, asset_type, signal_key)

    @staticmethod
    def _badge_key(scope: str, set_id: str, version: str) -> str:
        return f"{scope}:{set_id}/{version}"

    def _badge_path(self, scope: str, set_id: str, version: str) -> Path:
        return self.cache_dir / f"badge-{scope}-{set_id}-{version}.png"

    def _prune_disk_cache(self) -> None:
        dated_files: list[tuple[float, Path]] = []
        for path in self.cache_dir.glob("*.png"):
            try:
                dated_files.append((path.stat().st_mtime, path))
            except OSError:
                continue
        dated_files.sort(reverse=True)
        for _, old_path in dated_files[800:]:
            try:
                old_path.unlink()
            except OSError:
                pass
