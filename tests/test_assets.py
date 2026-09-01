from __future__ import annotations

import unittest
import wave
from pathlib import Path


class AudioAssetTests(unittest.TestCase):
    def test_message_sound_is_a_short_valid_wave(self) -> None:
        path = Path(__file__).resolve().parents[1] / "assets" / "message.wav"
        with wave.open(str(path), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertEqual(audio.getframerate(), 44_100)
            duration = audio.getnframes() / audio.getframerate()
            self.assertGreater(duration, 0.10)
            self.assertLess(duration, 0.25)
            self.assertTrue(any(audio.readframes(audio.getnframes())))


if __name__ == "__main__":
    unittest.main()
