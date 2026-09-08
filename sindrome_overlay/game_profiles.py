from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Any, Mapping

from .profiles import normalize_game_path


class WindowsGameDetector:
    """Observe the foreground game; retain one process handle across Alt+Tab.

    A retained handle identifies the process even if Windows reuses its PID.
    No process enumeration, elevated permissions or background worker is needed.
    """

    def __init__(self, *, user32: Any = None, kernel32: Any = None) -> None:
        self.user32 = user32
        self.kernel32 = kernel32
        self._handle: Any = None
        self._pid = 0
        self._path = ""
        if user32 is None and kernel32 is None and sys.platform == "win32":
            loader = getattr(ctypes, "WinDLL")
            self.user32 = loader("user32", use_last_error=True)
            self.kernel32 = loader("kernel32", use_last_error=True)
            self.user32.GetForegroundWindow.argtypes = []
            self.user32.GetForegroundWindow.restype = wintypes.HWND
            self.user32.GetWindowThreadProcessId.argtypes = [
                wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
            ]
            self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
            self.kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            self.kernel32.OpenProcess.restype = wintypes.HANDLE
            self.kernel32.QueryFullProcessImageNameW.argtypes = [
                wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
            ]
            self.kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
            self.kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            self.kernel32.WaitForSingleObject.restype = wintypes.DWORD
            self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            self.kernel32.CloseHandle.restype = wintypes.BOOL

    @property
    def available(self) -> bool:
        return self.user32 is not None and self.kernel32 is not None

    def close(self) -> None:
        if self._handle is not None:
            self.kernel32.CloseHandle(self._handle)
        self._handle = None
        self._pid = 0
        self._path = ""

    def profile(self, bindings: Mapping[str, str]) -> str:
        if not self.available:
            return ""
        # WAIT_TIMEOUT means the process is still alive. Treat invalid handles
        # conservatively as unavailable; never block the Qt event loop.
        if self._handle is not None and (
            self.kernel32.WaitForSingleObject(self._handle, 0) != 0x102
            or self._path not in bindings
        ):
            self.close()

        hwnd = self.user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        if hwnd:
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and pid.value != self._pid:
            # PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE
            handle = self.kernel32.OpenProcess(0x1000 | 0x100000, False, pid.value)
            if handle:
                try:
                    buffer = ctypes.create_unicode_buffer(32768)
                    size = wintypes.DWORD(len(buffer))
                    if self.kernel32.QueryFullProcessImageNameW(
                        handle, 0, buffer, ctypes.byref(size)
                    ):
                        path = normalize_game_path(buffer.value)
                        if path in bindings and self.kernel32.WaitForSingleObject(handle, 0) == 0x102:
                            self.close()
                            self._handle, self._pid, self._path = handle, pid.value, path
                            handle = None
                finally:
                    if handle is not None:
                        self.kernel32.CloseHandle(handle)
        return bindings.get(self._path, "")
