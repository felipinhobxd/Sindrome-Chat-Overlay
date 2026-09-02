from __future__ import annotations

import unittest
import wave
from pathlib import Path

from sindrome_overlay.sounds import SOUND_PRESETS


class AudioAssetTests(unittest.TestCase):
    def test_all_notification_sounds_are_short_valid_waves(self) -> None:
        assets = Path(__file__).resolve().parents[1] / "assets"
        expected = [item.asset_name for item in SOUND_PRESETS] + ["message.wav"]
        for filename in expected:
            with self.subTest(filename=filename):
                with wave.open(str(assets / filename), "rb") as audio:
                    self.assertEqual(audio.getnchannels(), 1)
                    self.assertEqual(audio.getsampwidth(), 2)
                    self.assertEqual(audio.getframerate(), 44_100)
                    duration = audio.getnframes() / audio.getframerate()
                    self.assertGreater(duration, 0.05)
                    self.assertLess(duration, 0.40)
                    self.assertTrue(any(audio.readframes(audio.getnframes())))


if __name__ == "__main__":
    unittest.main()
