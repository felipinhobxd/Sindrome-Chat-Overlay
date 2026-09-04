from __future__ import annotations

import json
import os
import platform
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import qVersion

from .settings import Settings, app_data_dir

_API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{16,}")
_QUERY_KEY_PATTERN = re.compile(r"(?i)([?&](?:key|api_key)=)[^&\s]+")
_JSON_SECRET_PATTERN = re.compile(
    r'(?i)("(?:youtube_api_key|api_key|token|secret)"\s*:\s*")[^"]*(")'
)
_BEARER_PATTERN = re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+")
_MAX_LOG_BYTES = 2_000_000
_RUNTIME_SECRET_KEYS = {
    "api_key",
    "youtube_api_key",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "twitch_channel",
    "youtube_input",
    "channel_input",
}


def export_diagnostics(
    destination: Path,
    settings: Settings,
    runtime: Mapping[str, Any] | None = None,
    *,
    app_version: str,
    log_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> Path:
    """Create an atomic, sanitized diagnostic ZIP suitable for sharing with support."""
    destination = Path(destination)
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)

    base_dir = log_dir or app_data_dir()
    asset_dir = cache_dir or (app_data_dir() / "twitch-assets")
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "application": {
            "name": "Sindrome Chat Overlay",
            "version": app_version,
        },
        "system": {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "pyside6": pyside_version,
            "qt": qVersion(),
            "frozen": bool(getattr(sys, "frozen", False)),
        },
        "settings": _safe_settings(settings),
        "runtime": _sanitize_runtime(runtime or {}),
        "cache": _cache_stats(asset_dir),
        "privacy": {
            "api_keys_included": False,
            "channel_or_live_identifiers_included": False,
            "chat_messages_included": False,
            "user_home_path_included": False,
        },
    }

    temporary = destination.with_name(destination.name + ".tmp")
    try:
        with zipfile.ZipFile(
            temporary,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            archive.writestr(
                "diagnostic.json",
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
            )
            archive.writestr(
                "README.txt",
                _readme(settings.language),
            )
            for log_path in _candidate_logs(base_dir):
                text = _read_log_text(log_path)
                if text is None:
                    continue
                archive.writestr(
                    f"logs/{log_path.name}.txt",
                    _redact_text(text, settings),
                )
        os.replace(temporary, destination)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return destination


def _safe_settings(settings: Settings) -> dict[str, Any]:
    active = settings.active_overlay_profile
    if active.startswith("custom:"):
        active = "custom"
    return {
        "language": settings.language,
        "twitch_enabled": settings.twitch_enabled,
        "youtube_enabled": settings.youtube_enabled,
        "youtube_api_key_configured": bool(settings.youtube_api_key.strip()),
        "always_on_top": settings.always_on_top,
        "click_through": settings.click_through,
        "background_opacity": settings.background_opacity,
        "card_opacity": settings.card_opacity,
        "font_size": settings.font_size,
        "max_messages": settings.max_messages,
        "message_lifetime_seconds": settings.message_lifetime_seconds,
        "auto_scroll": settings.auto_scroll,
        "sound_enabled": settings.sound_enabled,
        "sound_volume": settings.sound_volume,
        "sound_min_interval_ms": settings.sound_min_interval_ms,
        "check_for_updates": settings.check_for_updates,
        "show_timestamps": settings.show_timestamps,
        "show_platform_labels": settings.show_platform_labels,
        "hide_commands": settings.hide_commands,
        "window_width": settings.window_width,
        "window_height": settings.window_height,
        "active_overlay_profile": active,
        "custom_profile_count": len(settings.overlay_profiles),
    }


def _sanitize_runtime(value: Any, *, depth: int = 0) -> Any:
    if depth > 5:
        return "[depth limit]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_generic(value)
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for key, item in list(value.items())[:100]:
            key_text = str(key)
            normalized_key = key_text.casefold()
            if (
                normalized_key in _RUNTIME_SECRET_KEYS
                or normalized_key.endswith("_secret")
                or normalized_key.endswith("_token")
                or normalized_key.endswith("_api_key")
            ):
                clean[key_text] = "[redacted]"
                continue
            # Runtime diagnostics intentionally report counts but never raw chat text.
            if normalized_key in {"chat_messages", "messages", "last_message", "message_text"}:
                clean[key_text] = "[redacted]"
                continue
            clean[key_text] = _sanitize_runtime(item, depth=depth + 1)
        return clean
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_runtime(item, depth=depth + 1) for item in list(value)[:100]]
    return _redact_generic(str(value))


def _cache_stats(cache_dir: Path) -> dict[str, int]:
    files = 0
    total_bytes = 0
    try:
        if cache_dir.exists():
            for path in cache_dir.rglob("*"):
                if not path.is_file():
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                files += 1
                total_bytes += size
    except OSError:
        pass
    return {"file_count": files, "bytes": total_bytes}


def _candidate_logs(log_dir: Path) -> list[Path]:
    result: list[Path] = []
    for name in ("overlay.log", "overlay.log.1", "overlay.log.2"):
        path = log_dir / name
        try:
            if path.is_file():
                result.append(path)
        except OSError:
            continue
    return result


def _read_log_text(path: Path) -> str | None:
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > _MAX_LOG_BYTES:
                handle.seek(size - _MAX_LOG_BYTES)
                handle.readline()
            data = handle.read(_MAX_LOG_BYTES)
        return data.decode("utf-8", "replace")
    except OSError:
        return None


def _redact_text(text: str, settings: Settings) -> str:
    redacted = _redact_generic(text)
    sensitive_values = (
        (settings.youtube_api_key.strip(), "[REDACTED_API_KEY]"),
        (settings.twitch_channel.strip(), "[REDACTED_CHANNEL]"),
        (settings.youtube_input.strip(), "[REDACTED_YOUTUBE_INPUT]"),
    )
    for value, replacement in sensitive_values:
        redacted = _replace_sensitive(redacted, value, replacement)

    home = str(Path.home())
    redacted = _replace_sensitive(redacted, home, "%USERPROFILE%")
    redacted = _replace_sensitive(redacted, home.replace("\\", "/"), "%USERPROFILE%")
    return redacted


def _redact_generic(text: str) -> str:
    text = _API_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)
    text = _QUERY_KEY_PATTERN.sub(r"\1[REDACTED]", text)
    text = _JSON_SECRET_PATTERN.sub(r"\1[REDACTED]\2", text)
    text = _BEARER_PATTERN.sub(r"\1[REDACTED]", text)
    home = str(Path.home())
    text = _replace_sensitive(text, home, "%USERPROFILE%")
    text = _replace_sensitive(text, home.replace("\\", "/"), "%USERPROFILE%")
    return text


def _replace_sensitive(text: str, value: str, replacement: str) -> str:
    if not value:
        return text
    return re.sub(re.escape(value), lambda _match: replacement, text, flags=re.IGNORECASE)


def _readme(language: str) -> str:
    if language == "pt-BR":
        return (
            "Pacote de diagnóstico do Sindrome Chat Overlay\n\n"
            "Este arquivo foi criado para suporte. Ele não inclui API Key do YouTube, "
            "identificadores de canal/live, mensagens do chat nem o caminho completo da pasta "
            "do usuário. Revise o conteúdo antes de compartilhá-lo se desejar.\n"
        )
    return (
        "Sindrome Chat Overlay diagnostic package\n\n"
        "This file was created for troubleshooting. It does not include the YouTube API key, "
        "channel/live identifiers, chat messages, or the full user-home path. You may review "
        "the contents before sharing it.\n"
    )
