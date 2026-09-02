from __future__ import annotations

import math
import struct
import wave
from collections.abc import Callable
from pathlib import Path

SAMPLE_RATE = 44_100


def _frames(
    duration: float,
    signal: Callable[[float], float],
    *,
    volume: float,
    attack: float = 0.006,
    release: float = 0.035,
) -> bytes:
    frame_count = max(1, round(SAMPLE_RATE * duration))
    attack_frames = max(1, round(SAMPLE_RATE * attack))
    release_frames = max(1, round(SAMPLE_RATE * release))
    frames = bytearray()
    for index in range(frame_count):
        envelope = min(
            1.0,
            index / attack_frames,
            (frame_count - index - 1) / release_frames,
        )
        value = max(-1.0, min(1.0, signal(index / SAMPLE_RATE)))
        sample = round(32_767 * volume * max(0.0, envelope) * value)
        frames.extend(struct.pack("<h", sample))
    return bytes(frames)


def _silence(duration: float) -> bytes:
    return b"\0\0" * round(SAMPLE_RATE * duration)


def _tone(frequency: float, duration: float, volume: float = 0.20) -> bytes:
    return _frames(
        duration,
        lambda seconds: math.sin(2 * math.pi * frequency * seconds),
        volume=volume,
    )


def _sweep(
    start_frequency: float,
    end_frequency: float,
    duration: float,
    volume: float,
) -> bytes:
    rate = (end_frequency - start_frequency) / duration
    return _frames(
        duration,
        lambda seconds: math.sin(
            2 * math.pi * (start_frequency * seconds + 0.5 * rate * seconds * seconds)
        ),
        volume=volume,
    )


def _soft() -> bytes:
    return _frames(
        0.18,
        lambda seconds: (
            math.sin(2 * math.pi * 523.25 * seconds)
            + 0.45 * math.sin(2 * math.pi * 783.99 * seconds)
        ) / 1.45,
        volume=0.18,
        release=0.085,
    )


def _pop() -> bytes:
    return _sweep(520, 980, 0.12, 0.24)


def _chime() -> bytes:
    return b"".join(
        (
            _tone(659.25, 0.075, 0.20),
            _silence(0.012),
            _frames(
                0.16,
                lambda seconds: (
                    math.sin(2 * math.pi * 987.77 * seconds)
                    + 0.35 * math.sin(2 * math.pi * 1_975.54 * seconds)
                ) / 1.35,
                volume=0.21,
                release=0.075,
            ),
        )
    )


def _arcade() -> bytes:
    def square(frequency: float, duration: float) -> bytes:
        return _frames(
            duration,
            lambda seconds: 1.0 if math.sin(2 * math.pi * frequency * seconds) >= 0 else -1.0,
            volume=0.12,
            attack=0.002,
            release=0.012,
        )

    return square(783.99, 0.055) + _silence(0.016) + square(1_174.66, 0.075)


def _bubble() -> bytes:
    return _sweep(1_050, 430, 0.16, 0.22)


def _bell() -> bytes:
    return _frames(
        0.32,
        lambda seconds: (
            math.sin(2 * math.pi * 740.0 * seconds)
            + 0.50 * math.sin(2 * math.pi * 1_480.0 * seconds)
            + 0.24 * math.sin(2 * math.pi * 2_220.0 * seconds)
        ) / 1.74,
        volume=0.22,
        release=0.22,
    )


SOUNDS = {
    "notification-soft.wav": _soft,
    "notification-pop.wav": _pop,
    "notification-chime.wav": _chime,
    "notification-arcade.wav": _arcade,
    "notification-bubble.wav": _bubble,
    "notification-bell.wav": _bell,
}


def _write_wave(destination: Path, frames: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(frames)


def create_notification_sounds(destination: Path) -> list[Path]:
    generated: list[Path] = []
    rendered: dict[str, bytes] = {}
    for filename, builder in SOUNDS.items():
        frames = builder()
        rendered[filename] = frames
        path = destination / filename
        _write_wave(path, frames)
        generated.append(path)

    # Kept for older portable builds that still look for the original filename.
    legacy = destination / "message.wav"
    _write_wave(legacy, rendered["notification-pop.wav"])
    generated.append(legacy)
    return generated


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "assets"
    generated = create_notification_sounds(destination)
    print(f"Generated {len(generated)} notification sound files in {destination}")


if __name__ == "__main__":
    main()
