from __future__ import annotations

import unittest


class CardThemePresetTests(unittest.TestCase):
    def test_invalid_theme_falls_back_to_dark(self) -> None:
        from sindrome_overlay.card_themes import DEFAULT_CARD_THEME, normalize_card_theme

        self.assertEqual(normalize_card_theme("neon"), DEFAULT_CARD_THEME)
        self.assertEqual(normalize_card_theme(""), DEFAULT_CARD_THEME)
        self.assertEqual(normalize_card_theme("light"), "light")

    def test_settings_normalizes_unknown_theme_on_save(self) -> None:
        from sindrome_overlay.settings import Settings

        settings = Settings(card_theme="velcro").normalized()
        self.assertEqual(settings.card_theme, "dark")

    def test_every_preset_has_distinct_bubble_and_text(self) -> None:
        from sindrome_overlay.card_themes import CARD_THEMES, CARD_THEME_ORDER

        self.assertEqual(set(CARD_THEMES), set(CARD_THEME_ORDER))
        for key in CARD_THEME_ORDER:
            theme = CARD_THEMES[key]
            self.assertEqual(len(theme.bubble_rgb), 3)
            self.assertTrue(theme.text_colour.startswith("#"))
            self.assertTrue(theme.badge_background.startswith("rgba("))

    def test_stylesheet_applies_light_theme(self) -> None:
        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.theme import build_stylesheet

        light = build_stylesheet(Settings(card_theme="light"))
        self.assertIn("rgba(243, 245, 249, 199)", light)  # bubble background
        self.assertIn("color: #1B2432", light)  # message text
        self.assertNotIn("rgba(3, 5, 9,", light)

    def test_stylesheet_defaults_to_dark_theme(self) -> None:
        from sindrome_overlay.settings import Settings
        from sindrome_overlay.ui.theme import build_stylesheet

        dark = build_stylesheet(Settings())
        self.assertIn("rgba(3, 5, 9, 199)", dark)
        self.assertIn("color: #F5F7FB", dark)

    def test_dialog_lists_themes_in_both_languages(self) -> None:
        from sindrome_overlay.card_themes import CARD_THEME_ORDER
        from sindrome_overlay.i18n import SUPPORTED_LANGUAGES, tr

        for language in SUPPORTED_LANGUAGES:
            for key in ("card_theme", *(f"card_theme_{t}" for t in CARD_THEME_ORDER)):
                label = tr(language, key)
                self.assertTrue(label, f"{language}/{key} has an empty label")


if __name__ == "__main__":
    unittest.main()
