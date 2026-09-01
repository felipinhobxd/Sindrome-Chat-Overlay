from __future__ import annotations

import unittest

from sindrome_overlay.i18n import SUPPORTED_LANGUAGES, tr, translation_keys
from sindrome_overlay.url_utils import normalize_twitch_channel


class TranslationTests(unittest.TestCase):
    def test_all_languages_have_the_same_keys(self) -> None:
        expected = translation_keys("en")
        for language in SUPPORTED_LANGUAGES:
            self.assertEqual(translation_keys(language), expected)

    def test_english_is_the_fallback_language(self) -> None:
        self.assertEqual(tr("unknown", "settings"), "Settings")

    def test_format_values_are_translated(self) -> None:
        self.assertEqual(tr("en", "reconnecting", seconds=5), "Reconnecting in 5s")
        self.assertEqual(tr("pt-BR", "reconnecting", seconds=5), "Reconectando em 5s")

    def test_validation_uses_the_selected_language(self) -> None:
        with self.assertRaisesRegex(ValueError, "Enter a Twitch channel"):
            normalize_twitch_channel("", "en")
        with self.assertRaisesRegex(ValueError, "Informe o canal da Twitch"):
            normalize_twitch_channel("", "pt-BR")


if __name__ == "__main__":
    unittest.main()
