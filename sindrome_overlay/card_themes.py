"""Card colour presets shared by the stylesheet, the fallback painter and the settings dialog.

Kept Qt-free at the package root so ``settings`` can normalise the value
without importing UI modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings import Settings

DEFAULT_CARD_THEME = "dark"


@dataclass(frozen=True)
class CardTheme:
    """Colours for the message card bubble and its text layers."""

    key: str
    bubble_rgb: tuple[int, int, int]
    text_colour: str
    meta_colour: str
    badge_background: str

    @property
    def bubble_rgb_css(self) -> str:
        return "{}, {}, {}".format(*self.bubble_rgb)


CARD_THEMES: dict[str, CardTheme] = {
    "dark": CardTheme(
        key="dark",
        bubble_rgb=(3, 5, 9),
        text_colour="#F5F7FB",
        meta_colour="#9BA8BE",
        badge_background="rgba(255,255,255,26)",
    ),
    "amoled": CardTheme(
        key="amoled",
        bubble_rgb=(0, 0, 0),
        text_colour="#F5F7FB",
        meta_colour="#8FA0B8",
        badge_background="rgba(255,255,255,22)",
    ),
    "ocean": CardTheme(
        key="ocean",
        bubble_rgb=(8, 22, 44),
        text_colour="#EAF2FF",
        meta_colour="#A7BCDD",
        badge_background="rgba(255,255,255,30)",
    ),
    "light": CardTheme(
        key="light",
        bubble_rgb=(243, 245, 249),
        text_colour="#1B2432",
        meta_colour="#55617A",
        badge_background="rgba(11,18,32,16)",
    ),
}

CARD_THEME_ORDER: tuple[str, ...] = ("dark", "amoled", "ocean", "light")


def normalize_card_theme(value: str) -> str:
    return value if value in CARD_THEMES else DEFAULT_CARD_THEME


def card_theme(settings: "Settings") -> CardTheme:
    """Resolve the theme for a settings instance, falling back safely."""
    return CARD_THEMES[normalize_card_theme(getattr(settings, "card_theme", DEFAULT_CARD_THEME))]
