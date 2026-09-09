"""Small command contract for a future paired phone controller.

This module validates commands and exposes an allowlisted state snapshot.
The transport must authenticate the phone and dispatch execution on the Qt
thread. No network listener or command execution is enabled here.
"""
from __future__ import annotations

from typing import Any

from .profiles import iter_profile_choices, normalize_profile_ref
from .settings import Settings

_APPEARANCE_LIMITS = {
    "font_size": (11, 30),
    "background_opacity": (0, 100),
    "card_opacity": (0, 100),
}
_BOOLEAN_ACTIONS = {"set_auto_scroll", "set_click_through"}
_ACTIONS = _BOOLEAN_ACTIONS | {"set_appearance", "apply_profile", "clear_messages"}


def validate_remote_command(payload: object, settings: Settings) -> dict[str, Any]:
    """Return an independent validated command; reject unknown fields and types.

    set_auto_scroll only pauses/resumes scrolling; chat reception continues.
    Validation errors deliberately omit submitted data, which may contain secrets.
    """
    if not isinstance(payload, dict):
        raise ValueError("Command must be an object")
    action = payload.get("action")
    if not isinstance(action, str) or action not in _ACTIONS:
        raise ValueError("Unknown remote action")
    fields = {"action"} if action == "clear_messages" else {"action", "value"}
    if set(payload) != fields:
        raise ValueError("Invalid command fields")
    if action == "clear_messages":
        return {"action": action}

    value = payload["value"]
    if action in _BOOLEAN_ACTIONS:
        if type(value) is not bool:
            raise ValueError("Command requires a boolean")
    elif action == "set_appearance":
        if not isinstance(value, dict) or not value or set(value) - _APPEARANCE_LIMITS.keys():
            raise ValueError("Invalid appearance fields")
        for field, number in value.items():
            minimum, maximum = _APPEARANCE_LIMITS[field]
            if type(number) is not int or not minimum <= number <= maximum:
                raise ValueError("Appearance value is out of range")
        value = dict(value)
    elif action == "apply_profile":
        value = normalize_profile_ref(value, settings.overlay_profiles)
        if not value:
            raise ValueError("Profile is unavailable")
    return {"action": action, "value": value}


def remote_control_state(settings: Settings) -> dict[str, Any]:
    """Expose controls only: no credentials, channels, game paths or chat content."""
    return {
        "appearance": {field: getattr(settings, field) for field in _APPEARANCE_LIMITS},
        "auto_scroll": settings.auto_scroll,
        "click_through": settings.click_through,
        "active_profile": normalize_profile_ref(
            settings.active_overlay_profile, settings.overlay_profiles,
        ),
        "profiles": [
            {"id": ref, "name": label}
            for ref, label, _ in iter_profile_choices(settings.overlay_profiles, settings.language)
        ],
    }
