from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_TWITCH_NAME = re.compile(r"^[A-Za-z0-9_]{3,25}$")


def normalize_twitch_channel(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("Informe o canal da Twitch.")
    raw = raw.removeprefix("@").strip()
    if "://" in raw or raw.lower().startswith("www."):
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = parsed.netloc.lower().removeprefix("www.")
        if host not in {"twitch.tv", "m.twitch.tv"}:
            raise ValueError("Use um link válido da Twitch.")
        raw = parsed.path.strip("/").split("/")[0]
    raw = raw.lower()
    if not _TWITCH_NAME.fullmatch(raw):
        raise ValueError("O nome do canal da Twitch parece inválido.")
    return raw


def twitch_channel_url(value: str) -> str:
    return f"https://www.twitch.tv/{normalize_twitch_channel(value)}"


def normalize_youtube_input(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("Informe o canal ou vídeo do YouTube.")

    if _VIDEO_ID.fullmatch(raw):
        return f"https://www.youtube.com/watch?v={raw}"
    if raw.startswith("@"):
        return f"https://www.youtube.com/{raw}/live"
    if "://" not in raw:
        if raw.lower().startswith(("youtube.com/", "www.youtube.com/", "youtu.be/")):
            raw = f"https://{raw}"
        else:
            raw = f"https://www.youtube.com/@{raw.lstrip('@')}/live"

    parsed = urlparse(raw)
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
        if not _VIDEO_ID.fullmatch(video_id):
            raise ValueError("O link curto do YouTube parece inválido.")
        return f"https://www.youtube.com/watch?v={video_id}"
    if host not in {"youtube.com", "m.youtube.com"}:
        raise ValueError("Use um link válido do YouTube.")

    if parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        if not _VIDEO_ID.fullmatch(video_id):
            raise ValueError("O link do vídeo do YouTube parece inválido.")
        return f"https://www.youtube.com/watch?v={video_id}"
    if parsed.path.startswith("/live/"):
        video_id = parsed.path.split("/")[2]
        if _VIDEO_ID.fullmatch(video_id):
            return f"https://www.youtube.com/watch?v={video_id}"

    path = parsed.path.rstrip("/")
    if not path:
        raise ValueError("Informe um canal específico do YouTube.")
    if not path.endswith("/live"):
        path += "/live"
    return f"https://www.youtube.com{path}"


def youtube_video_id(value: str) -> str:
    normalized = normalize_youtube_input(value)
    parsed = urlparse(normalized)
    if parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        return video_id if _VIDEO_ID.fullmatch(video_id) else ""
    return ""


def is_youtube_channel_input(value: str) -> bool:
    return not bool(youtube_video_id(value))
