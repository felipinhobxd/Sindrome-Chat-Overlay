from __future__ import annotations

import unittest

from sindrome_overlay.settings import Settings
from sindrome_overlay.ui.theme import build_stylesheet


class OverlayOpacityTests(unittest.TestCase):
    def test_background_layers_scale_at_each_supported_level(self) -> None:
        expected = {
            100: (255, 36, 225, 26, 95, 45),
            75: (191, 27, 169, 20, 71, 34),
            50: (127, 18, 112, 13, 48, 22),
            25: (64, 9, 56, 6, 24, 11),
            0: (0, 0, 0, 0, 0, 0),
        }
        for opacity, alphas in expected.items():
            with self.subTest(opacity=opacity):
                style = build_stylesheet(Settings(background_opacity=opacity))
                panel, border, header, header_border, empty, empty_border = alphas
                self.assertIn(f"background-color: rgba(8, 11, 19, {panel});", style)
                self.assertIn(
                    f"border: 1px solid rgba(255, 255, 255, {border});",
                    style,
                )
                self.assertIn(f"background-color: rgba(14, 19, 31, {header});", style)
                self.assertIn(
                    f"border-bottom: 1px solid rgba(255, 255, 255, {header_border});",
                    style,
                )
                self.assertIn(f"background: rgba(8, 11, 19, {empty});", style)
                self.assertIn(
                    f"border: 1px dashed rgba(255, 255, 255, {empty_border});",
                    style,
                )

    def test_zero_background_does_not_hide_message_cards(self) -> None:
        style = build_stylesheet(Settings(background_opacity=0, card_opacity=80))
        self.assertIn("background-color: rgba(11, 16, 27, 204);", style)
        self.assertNotIn("window-opacity", style.casefold())


if __name__ == "__main__":
    unittest.main()
