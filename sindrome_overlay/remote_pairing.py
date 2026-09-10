"""In-memory pairing for one phone; no network listener is started here.

Only the local PC interface may call begin_pairing(). A future transport must
protect the code and session token in transit and must never log either one.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PairingStatus:
    code_seconds: int
    session_active: bool


class RemotePairing:
    CODE_LIFETIME = 120
    SESSION_LIFETIME = 8 * 60 * 60
    MAX_ATTEMPTS = 5

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._code_hash: bytes | None = None
        self._code_deadline = 0.0
        self._attempts = 0
        self._session_hash: bytes | None = None
        self._session_deadline = 0.0

    def begin_pairing(self) -> str:
        """Generate a one-use six-digit code for display on the PC only."""
        with self._lock:
            code = f"{secrets.randbelow(1_000_000):06d}"
            self._code_hash = hashlib.sha256(code.encode("ascii")).digest()
            self._code_deadline = self._clock() + self.CODE_LIFETIME
            self._attempts = self.MAX_ATTEMPTS
            return code

    def exchange_code(self, code: object) -> str | None:
        """Consume a valid code and replace the previous phone's session."""
        with self._lock:
            if self._clock() >= self._code_deadline or self._attempts <= 0:
                self._code_hash = None
            if self._code_hash is None:
                return None
            self._attempts -= 1
            if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
                return None
            if not hmac.compare_digest(hashlib.sha256(code.encode("ascii")).digest(), self._code_hash):
                return None
            token = secrets.token_urlsafe(32)
            self._code_hash = None
            self._session_hash = hashlib.sha256(token.encode("ascii")).digest()
            self._session_deadline = self._clock() + self.SESSION_LIFETIME
            return token

    def authorized(self, token: object) -> bool:
        if not isinstance(token, str) or len(token) != 43 or not token.isascii():
            return False
        with self._lock:
            if self._clock() >= self._session_deadline:
                self._session_hash = None
            return self._session_hash is not None and hmac.compare_digest(
                hashlib.sha256(token.encode("ascii")).digest(), self._session_hash,
            )

    def status(self) -> PairingStatus:
        """Return local UI state without disclosing the code or session token."""
        with self._lock:
            now = self._clock()
            remaining = 0
            if self._code_hash is not None and self._attempts > 0:
                remaining = max(0, math.ceil(self._code_deadline - now))
            return PairingStatus(
                code_seconds=remaining,
                session_active=self._session_hash is not None and now < self._session_deadline,
            )

    def cancel_pairing(self) -> None:
        """Cancel a pending PC code while keeping the authorized phone."""
        with self._lock:
            self._code_hash = None
            self._attempts = 0

    def revoke(self) -> None:
        """Disconnect the paired phone and cancel any pending pairing code."""
        with self._lock:
            self._code_hash = None
            self._session_hash = None
            self._attempts = 0
