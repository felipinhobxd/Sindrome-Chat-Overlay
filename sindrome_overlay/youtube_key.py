from __future__ import annotations

import threading
from dataclasses import dataclass
from queue import Queue
from typing import Literal

import requests

YOUTUBE_VALIDATION_URL = "https://www.googleapis.com/youtube/v3/videos"

ValidationStatus = Literal["valid", "invalid", "unavailable"]

_INVALID_REASONS = {
    "accessNotConfigured",
    "forbidden",
    "ipRefererBlocked",
    "keyInvalid",
}
_TEMPORARY_REASONS = {
    "backendError",
    "dailyLimitExceeded",
    "quotaExceeded",
    "rateLimitExceeded",
    "userRequestsExceedRateLimit",
}


@dataclass(frozen=True, slots=True)
class YouTubeKeyValidationResult:
    """A secret-free result that is safe to pass back to the Qt thread."""

    request_id: int
    status: ValidationStatus


def validate_youtube_api_key(
    api_key: str,
    request_id: int,
    *,
    session: requests.Session | None = None,
) -> YouTubeKeyValidationResult:
    """Verify whether a key can make a minimal YouTube Data API request.

    The key is deliberately excluded from the return value and exceptions are never
    copied into it because requests may include query parameters in exception text.
    """

    client = session or requests.Session()
    owns_session = session is None
    try:
        try:
            response = client.get(
                YOUTUBE_VALIDATION_URL,
                params={
                    "part": "id",
                    "id": "dQw4w9WgXcQ",
                    "fields": "items/id",
                    "key": api_key.strip(),
                },
                headers={"User-Agent": "SindromeChatOverlay"},
                timeout=(5, 10),
            )
        except requests.RequestException:
            return YouTubeKeyValidationResult(request_id, "unavailable")

        if response.status_code == 200:
            return YouTubeKeyValidationResult(request_id, "valid")
        if response.status_code == 429 or response.status_code >= 500:
            return YouTubeKeyValidationResult(request_id, "unavailable")

        reason = _api_error_reason(response)
        if reason in _TEMPORARY_REASONS:
            return YouTubeKeyValidationResult(request_id, "unavailable")
        if reason in _INVALID_REASONS or response.status_code in {400, 401}:
            return YouTubeKeyValidationResult(request_id, "invalid")

        # A 403 on this public, read-only endpoint means the credential cannot be used
        # by the desktop app. Unknown responses stay inconclusive rather than falsely
        # labelling a key invalid.
        if response.status_code == 403:
            return YouTubeKeyValidationResult(request_id, "invalid")
        return YouTubeKeyValidationResult(request_id, "unavailable")
    finally:
        if owns_session:
            client.close()


def _api_error_reason(response: requests.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error") if isinstance(payload, dict) else None
        details = error.get("errors") if isinstance(error, dict) else None
        first = details[0] if isinstance(details, list) and details else None
        reason = first.get("reason") if isinstance(first, dict) else ""
        return str(reason or "")
    except (ValueError, TypeError, AttributeError):
        return ""


class YouTubeKeyValidator(threading.Thread):
    """Perform one API-key verification without blocking the interface."""

    def __init__(
        self,
        results: Queue[YouTubeKeyValidationResult],
        api_key: str,
        request_id: int,
        *,
        session: requests.Session | None = None,
    ) -> None:
        super().__init__(name="youtube-key-validation", daemon=True)
        self.results = results
        self._api_key = api_key
        self.request_id = request_id
        self.session = session or requests.Session()
        self._owns_session = session is None
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()
        if self._owns_session:
            self.session.close()

    def run(self) -> None:
        try:
            result = validate_youtube_api_key(
                self._api_key,
                self.request_id,
                session=self.session,
            )
            if not self.stop_event.is_set():
                self.results.put(result)
        finally:
            self._api_key = ""
            if self._owns_session:
                self.session.close()
