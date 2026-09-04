from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .feature_i18n import feature_tr

_MAX_CUSTOM_PROFILES = 12
_MAX_PROFILE_NAME = 40

# Overlay profiles intentionally exclude credentials, channel inputs, update preferences,
# notification sounds and click-through. Applying a visual/layout profile must never alter
# secrets or unexpectedly lock the user out of the overlay.
_PROFILE_FIELDS: tuple[str, ...] = (
    "always_on_top",
    "background_opacity",
    "card_opacity",
    "font_size",
    "max_messages",
    "message_lifetime_seconds",
    "auto_scroll",
    "show_timestamps",
    "show_platform_labels",
    "hide_commands",
    "window_x",
    "window_y",
    "window_width",
    "window_height",
)

_BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "compact_fps": {
        "always_on_top": True,
        "background_opacity": 32,
        "card_opacity": 76,
        "font_size": 13,
        "max_messages": 80,
        "message_lifetime_seconds": 35,
        "auto_scroll": True,
        "show_timestamps": False,
        "show_platform_labels": False,
        "hide_commands": True,
        "window_width": 360,
        "window_height": 520,
    },
    "chat_focus": {
        "always_on_top": True,
        "background_opacity": 62,
        "card_opacity": 84,
        "font_size": 15,
        "max_messages": 180,
        "message_lifetime_seconds": 0,
        "auto_scroll": True,
        "show_timestamps": True,
        "show_platform_labels": True,
        "hide_commands": False,
        "window_width": 440,
        "window_height": 720,
    },
    "clean_stream": {
        "always_on_top": True,
        "background_opacity": 0,
        "card_opacity": 72,
        "font_size": 17,
        "max_messages": 150,
        "message_lifetime_seconds": 45,
        "auto_scroll": True,
        "show_timestamps": False,
        "show_platform_labels": False,
        "hide_commands": True,
        "window_width": 500,
        "window_height": 760,
    },
}

_BUILTIN_LABEL_KEYS = {
    "compact_fps": "profile_compact_fps",
    "chat_focus": "profile_chat_focus",
    "clean_stream": "profile_clean_stream",
}


def builtin_profile_refs() -> tuple[str, ...]:
    return tuple(f"builtin:{identifier}" for identifier in _BUILTIN_PROFILES)


def profile_display_name(profile_ref: str, language: str) -> str:
    if profile_ref.startswith("builtin:"):
        identifier = profile_ref.removeprefix("builtin:")
        key = _BUILTIN_LABEL_KEYS.get(identifier)
        if key:
            return feature_tr(language, key)
    if profile_ref.startswith("custom:"):
        return profile_ref.removeprefix("custom:")
    return profile_ref


def iter_profile_choices(
    custom_profiles: Mapping[str, Mapping[str, Any]] | None,
    language: str,
) -> list[tuple[str, str, bool]]:
    result = [
        (ref, profile_display_name(ref, language), True)
        for ref in builtin_profile_refs()
    ]
    normalized = normalize_custom_profiles(custom_profiles)
    result.extend(
        (f"custom:{name}", name, False)
        for name in sorted(normalized, key=str.casefold)
    )
    return result


def normalize_profile_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    clean = " ".join(value.replace("\x00", "").split()).strip()
    if not 1 <= len(clean) <= _MAX_PROFILE_NAME:
        return ""
    if any(ord(char) < 32 for char in clean):
        return ""
    return clean


def normalize_custom_profiles(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for raw_name, raw_values in value.items():
        if len(normalized) >= _MAX_CUSTOM_PROFILES:
            break
        name = normalize_profile_name(raw_name)
        if not name or name in normalized:
            continue
        values = sanitize_profile_values(raw_values)
        if values:
            normalized[name] = values
    return normalized


def normalize_profile_ref(
    profile_ref: Any,
    custom_profiles: Mapping[str, Mapping[str, Any]] | None,
) -> str:
    if not isinstance(profile_ref, str):
        return ""
    if profile_ref.startswith("builtin:"):
        identifier = profile_ref.removeprefix("builtin:")
        return profile_ref if identifier in _BUILTIN_PROFILES else ""
    if profile_ref.startswith("custom:"):
        name = normalize_profile_name(profile_ref.removeprefix("custom:"))
        return profile_ref if name and name in normalize_custom_profiles(custom_profiles) else ""
    return ""


def resolve_profile(
    profile_ref: str,
    custom_profiles: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any] | None:
    if profile_ref.startswith("builtin:"):
        identifier = profile_ref.removeprefix("builtin:")
        values = _BUILTIN_PROFILES.get(identifier)
        return dict(values) if values is not None else None
    if profile_ref.startswith("custom:"):
        name = normalize_profile_name(profile_ref.removeprefix("custom:"))
        values = normalize_custom_profiles(custom_profiles).get(name)
        return dict(values) if values is not None else None
    return None


def capture_overlay_profile(settings: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field_name in _PROFILE_FIELDS:
        if hasattr(settings, field_name):
            values[field_name] = getattr(settings, field_name)
    return sanitize_profile_values(values)


def apply_overlay_profile(settings: Any, values: Mapping[str, Any]) -> Any:
    updated = replace(settings)
    for field_name, value in sanitize_profile_values(values).items():
        setattr(updated, field_name, value)
    return updated.normalized()


def sanitize_profile_values(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    bool_fields = {
        "always_on_top",
        "auto_scroll",
        "show_timestamps",
        "show_platform_labels",
        "hide_commands",
    }
    ranges = {
        "background_opacity": (0, 100),
        "card_opacity": (0, 100),
        "font_size": (11, 30),
        "max_messages": (20, 500),
        "message_lifetime_seconds": (0, 600),
        "window_x": (-10_000, 10_000),
        "window_y": (-10_000, 10_000),
        "window_width": (300, 2_000),
        "window_height": (240, 1_400),
    }
    for field_name in _PROFILE_FIELDS:
        if field_name not in value:
            continue
        raw = value[field_name]
        if field_name in bool_fields:
            if isinstance(raw, bool):
                result[field_name] = raw
            continue
        minimum, maximum = ranges[field_name]
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        result[field_name] = max(minimum, min(maximum, number))
    return result
