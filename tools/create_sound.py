from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 44_100


def _tone(frequency: float, duration: float, volume: float = 0.17) -> bytes:
    frame_count = round(SAMPLE_RATE * duration)
    fade_in = max(1, round(SAMPLE_RATE * 0.007))
    fade_out = max(1, round(SAMPLE_RATE * 0.020))
    frames = bytearray()
    for index in range(frame_count):
        if frequency <= 0:
            sample = 0
        else:
            envelope = min(1.0, index / fade_in, (frame_count - index) / fade_out)
            value = math.sin(2 * math.pi * frequency * index / SAMPLE_RATE)
            sample = round(32_767 * volume * max(0.0, envelope) * value)
        frames.extend(struct.pack("<h", sample))
    return bytes(frames)


def create_message_sound(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frames = b"".join(
        (
            _tone(660, 0.055),
            _tone(0, 0.018),
            _tone(880, 0.075),
        )
    )
    with wave.open(str(destination), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(frames)


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "assets" / "message.wav"
    create_message_sound(destination)
    print(f"Som gerado em: {destination}")


if __name__ == "__main__":
    main()
