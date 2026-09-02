from __future__ import annotations

import hashlib
import hmac
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from typing import Any
from urllib.parse import urlparse

import requests

LATEST_RELEASE_API = (
    "https://api.github.com/repos/felipinhobxd/Sindrome-Chat-Overlay/releases/latest"
)
_REPOSITORY_PATH = "/felipinhobxd/Sindrome-Chat-Overlay"
_RELEASE_PATH_PREFIX = f"{_REPOSITORY_PATH}/releases/tag/"
_DOWNLOAD_PATH_PREFIX = f"{_REPOSITORY_PATH}/releases/download/"
_CHECKSUM_ASSET_NAME = "SHA256SUMS.txt"
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")
_CHECKSUM_LINE_RE = re.compile(r"^([0-9a-fA-F]{64})[ \t]+\*?(.+?)\s*$")
_MAX_RESPONSE_BYTES = 1_000_000
_MAX_CHECKSUM_BYTES = 64 * 1024
_MAX_INSTALLER_BYTES = 250 * 1024 * 1024
_DOWNLOAD_CHUNK_BYTES = 128 * 1024
_TRUSTED_FINAL_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    version: str
    release_name: str
    release_url: str
    installer_name: str
    installer_url: str
    installer_size: int
    checksums_url: str
    checksums_size: int


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    status: str
    update: UpdateInfo | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class UpdateDownloadResult:
    status: str
    update: UpdateInfo
    progress: int = 0
    installer_path: Path | None = None
    sha256: str = ""
    error_code: str = ""
    error: str = ""


class _UpdateFailure(RuntimeError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail[:160]


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

    version = ".".join(str(part) for part in available)
    installer_name = f"SindromeChatOverlay-Setup-v{version}.exe"
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return None
    installer = _unique_release_asset(assets, installer_name)
    checksums = _unique_release_asset(assets, _CHECKSUM_ASSET_NAME)
    if installer is None or checksums is None:
        return None

    installer_url = str(installer.get("browser_download_url") or "").strip()
    checksums_url = str(checksums.get("browser_download_url") or "").strip()
    installer_size = _valid_asset_size(installer.get("size"), _MAX_INSTALLER_BYTES)
    checksums_size = _valid_asset_size(checksums.get("size"), _MAX_CHECKSUM_BYTES)
    if (
        installer_size is None
        or checksums_size is None
        or not _trusted_asset_url(installer_url, tag_name, installer_name)
        or not _trusted_asset_url(checksums_url, tag_name, _CHECKSUM_ASSET_NAME)
    ):
        return None

    release_name = str(payload.get("name") or tag_name).strip()[:120]
    return UpdateInfo(
        version=version,
        release_name=release_name or f"v{version}",
        release_url=release_url,
        installer_name=installer_name,
        installer_url=installer_url,
        installer_size=installer_size,
        checksums_url=checksums_url,
        checksums_size=checksums_size,
    )


def _unique_release_asset(assets: list[Any], expected_name: str) -> dict[str, Any] | None:
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and asset.get("name") == expected_name
        and asset.get("state", "uploaded") == "uploaded"
    ]
    return matches[0] if len(matches) == 1 else None


def _valid_asset_size(value: Any, maximum: int) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        size = int(value)
    except (TypeError, ValueError):
        return None
    return size if 0 < size <= maximum else None


def _trusted_release_url(value: str, tag_name: str) -> bool:
    return _strict_github_url(value, f"{_RELEASE_PATH_PREFIX}{tag_name}")


def _trusted_asset_url(value: str, tag_name: str, filename: str) -> bool:
    return _strict_github_url(
        value,
        f"{_DOWNLOAD_PATH_PREFIX}{tag_name}/{filename}",
    )


def _strict_github_url(value: str, expected_path: str) -> bool:
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
        and parsed.path == expected_path
        and not parsed.query
        and not parsed.fragment
    )


def _trusted_final_download_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in _TRUSTED_FINAL_DOWNLOAD_HOSTS
        and port is None
        and not parsed.username
        and not parsed.password
        and not parsed.fragment
    )


def parse_checksum_manifest(content: bytes, installer_name: str) -> str | None:
    if len(content) > _MAX_CHECKSUM_BYTES:
        return None
    try:
        text = content.decode("ascii")
    except UnicodeDecodeError:
        return None
    matches: list[str] = []
    for line in text.splitlines():
        match = _CHECKSUM_LINE_RE.fullmatch(line)
        if match and match.group(2) == installer_name:
            matches.append(match.group(1).lower())
    return matches[0] if len(matches) == 1 else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(_DOWNLOAD_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_matches(path: Path, expected: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        return False
    try:
        actual = sha256_file(path)
    except OSError:
        return False
    return hmac.compare_digest(actual, expected)


def update_download_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "SindromeChatOverlay" / "updates"


class UpdateChecker(threading.Thread):
    """Perform one GitHub release check away from the Qt interface thread."""

    def __init__(
        self,
        results: Queue[UpdateCheckResult | UpdateDownloadResult],
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
                    "X-GitHub-Api-Version": "2022-11-28",
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


class UpdateDownloader(threading.Thread):
    """Download and verify one installer without blocking Qt."""

    def __init__(
        self,
        results: Queue[UpdateCheckResult | UpdateDownloadResult],
        update: UpdateInfo,
        *,
        download_dir: Path | None = None,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(name="update-download", daemon=True)
        self.results = results
        self.update = update
        self.download_dir = Path(download_dir) if download_dir else update_download_dir()
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.stop_event = threading.Event()
        self._partial_path: Path | None = None

    def stop(self) -> None:
        self.stop_event.set()
        if self._owns_session:
            self.session.close()

    def run(self) -> None:
        try:
            self._emit_progress(1)
            checksum_content = self._download_bytes(
                self.update.checksums_url,
                self.update.checksums_size,
                _MAX_CHECKSUM_BYTES,
            )
            expected_hash = parse_checksum_manifest(
                checksum_content,
                self.update.installer_name,
            )
            if expected_hash is None:
                raise _UpdateFailure("checksum_manifest")

            self._emit_progress(5)
            partial_path, actual_hash = self._download_installer()
            if not hmac.compare_digest(actual_hash, expected_hash):
                raise _UpdateFailure("checksum_mismatch")

            self._raise_if_stopped()
            self._emit_progress(98)
            final_path = self.download_dir / self.update.installer_name
            os.replace(partial_path, final_path)
            self._partial_path = None
            self.results.put(
                UpdateDownloadResult(
                    status="ready",
                    update=self.update,
                    progress=100,
                    installer_path=final_path,
                    sha256=expected_hash,
                )
            )
        except _UpdateFailure as exc:
            if exc.code == "cancelled":
                self.results.put(UpdateDownloadResult(status="cancelled", update=self.update))
            else:
                self.results.put(
                    UpdateDownloadResult(
                        status="error",
                        update=self.update,
                        error_code=exc.code,
                        error=exc.detail,
                    )
                )
        except requests.RequestException as exc:
            if self.stop_event.is_set():
                self.results.put(UpdateDownloadResult(status="cancelled", update=self.update))
            else:
                self.results.put(
                    UpdateDownloadResult(
                        status="error",
                        update=self.update,
                        error_code="network",
                        error=type(exc).__name__,
                    )
                )
        except OSError as exc:
            self.results.put(
                UpdateDownloadResult(
                    status="error",
                    update=self.update,
                    error_code="storage",
                    error=type(exc).__name__,
                )
            )
        finally:
            if self._partial_path is not None:
                try:
                    self._partial_path.unlink(missing_ok=True)
                except OSError:
                    pass
            if self._owns_session:
                self.session.close()

    def _download_bytes(self, url: str, expected_size: int, maximum: int) -> bytes:
        response = self._open_download(url, maximum)
        content = bytearray()
        try:
            for chunk in response.iter_content(chunk_size=32 * 1024):
                self._raise_if_stopped()
                if not chunk:
                    continue
                content.extend(chunk)
                if len(content) > maximum:
                    raise _UpdateFailure("download_size")
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        if len(content) != expected_size:
            raise _UpdateFailure("download_size")
        return bytes(content)

    def _download_installer(self) -> tuple[Path, str]:
        self.download_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        _remove_stale_downloads(self.download_dir)
        partial_path = self.download_dir / f".{uuid.uuid4().hex}.download.exe"
        self._partial_path = partial_path
        response = self._open_download(self.update.installer_url, _MAX_INSTALLER_BYTES)
        digest = hashlib.sha256()
        written = 0
        try:
            with partial_path.open("xb") as output:
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK_BYTES):
                    self._raise_if_stopped()
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > _MAX_INSTALLER_BYTES or written > self.update.installer_size:
                        raise _UpdateFailure("download_size")
                    output.write(chunk)
                    digest.update(chunk)
                    progress = 5 + int((written / self.update.installer_size) * 82)
                    self._emit_progress(min(progress, 87))
                output.flush()
                os.fsync(output.fileno())
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
        if written != self.update.installer_size:
            raise _UpdateFailure("download_size")
        return partial_path, digest.hexdigest()

    def _open_download(self, url: str, maximum: int):
        self._raise_if_stopped()
        response = self.session.get(
            url,
            headers={
                "Accept": "application/octet-stream",
                "User-Agent": f"SindromeChatOverlay/{self.update.version}",
            },
            timeout=(8, 45),
            stream=True,
            allow_redirects=True,
        )
        try:
            if response.status_code != 200:
                raise _UpdateFailure("network", f"HTTP {response.status_code}")
            final_url = str(getattr(response, "url", "") or url)
            if not _trusted_final_download_url(final_url):
                raise _UpdateFailure("untrusted_download")
            headers = getattr(response, "headers", {}) or {}
            content_length = headers.get("Content-Length")
            if content_length:
                try:
                    announced = int(content_length)
                except (TypeError, ValueError) as exc:
                    raise _UpdateFailure("download_size") from exc
                if announced <= 0 or announced > maximum:
                    raise _UpdateFailure("download_size")
        except Exception:
            close = getattr(response, "close", None)
            if callable(close):
                close()
            raise
        return response

    def _raise_if_stopped(self) -> None:
        if self.stop_event.is_set():
            raise _UpdateFailure("cancelled")

    def _emit_progress(self, progress: int) -> None:
        self.results.put(
            UpdateDownloadResult(
                status="progress",
                update=self.update,
                progress=max(0, min(100, progress)),
            )
        )


def _remove_stale_downloads(directory: Path) -> None:
    cutoff = time.time() - 14 * 24 * 60 * 60
    for candidate in directory.iterdir():
        if not candidate.is_file():
            continue
        if not (
            candidate.name.startswith("SindromeChatOverlay-Setup-v")
            or candidate.name.endswith(".download.exe")
        ):
            continue
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except OSError:
            continue
