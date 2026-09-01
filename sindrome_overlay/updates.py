from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from queue import Queue
from typing import Any
from urllib.parse import urlparse

import requests

LATEST_RELEASE_API = (
    "https://api.github.com/repos/felipinhobxd/Sindrome-Chat-Overlay/releases/latest"
)
_RELEASE_PATH_PREFIX = "/felipinhobxd/Sindrome-Chat-Overlay/releases/tag/"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_MAX_RESPONSE_BYTES = 1_000_000


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    release_name: str
    release_url: str


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    status: str
    update: UpdateInfo | None = None
    error: str = ""


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = _VERSION_RE.fullmatch(value.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def update_from_release(payload: Any, current_version: str) -> UpdateInfo | None:
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        return None
    current = version_tuple(current_version)
    tag_name = str(payload.get("tag_name") or "").strip()
    available = version_tuple(tag_name)
    if current is None or available is None or available <= current:
        return None

    release_url = str(payload.get("html_url") or "").strip()
    if not _trusted_release_url(release_url, tag_name):
        return None
    release_name = str(payload.get("name") or tag_name).strip()[:120]
    return UpdateInfo(
        version=".".join(str(part) for part in available),
        release_name=release_name or f"v{'.'.join(str(part) for part in available)}",
        release_url=release_url,
    )


def _trusted_release_url(value: str, tag_name: str) -> bool:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and port is None
        and not parsed.username
        and not parsed.password
        and parsed.path == f"{_RELEASE_PATH_PREFIX}{tag_name}"
        and not parsed.query
        and not parsed.fragment
    )


class UpdateChecker(threading.Thread):
    """Perform one GitHub release check away from the Qt interface thread."""

    def __init__(
        self,
        results: Queue[UpdateCheckResult],
        current_version: str,
        *,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(name="update-check", daemon=True)
        self.results = results
        self.current_version = current_version
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()
        if self._owns_session:
            self.session.close()

    def run(self) -> None:
        try:
            response = self.session.get(
                LATEST_RELEASE_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10",
                    "User-Agent": f"SindromeChatOverlay/{self.current_version}",
                },
                timeout=(5, 10),
            )
            if self.stop_event.is_set():
                return
            if response.status_code != 200:
                self.results.put(
                    UpdateCheckResult(
                        status="error",
                        error=f"GitHub returned HTTP {response.status_code}",
                    )
                )
                return
            if len(response.content) > _MAX_RESPONSE_BYTES:
                self.results.put(
                    UpdateCheckResult(status="error", error="GitHub response was too large")
                )
                return
            try:
                payload = response.json()
            except ValueError:
                self.results.put(
                    UpdateCheckResult(status="error", error="GitHub returned invalid JSON")
                )
                return
            update = update_from_release(payload, self.current_version)
            self.results.put(
                UpdateCheckResult(
                    status="update" if update is not None else "current",
                    update=update,
                )
            )
        except requests.RequestException as exc:
            if not self.stop_event.is_set():
                self.results.put(UpdateCheckResult(status="error", error=str(exc)[:200]))
        finally:
            if self._owns_session:
                self.session.close()
