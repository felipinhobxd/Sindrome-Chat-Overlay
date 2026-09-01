from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import Any, Callable

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_O = 0x4F
DEFAULT_HOTKEY_ID = 0x5343

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
WINDOW_STATE_FLAGS = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_FRAMECHANGED


def _set_last_error(value: int) -> None:
    setter = getattr(ctypes, "set_last_error", None)
    if setter is not None:
        setter(value)


def _get_last_error() -> int:
    getter = getattr(ctypes, "get_last_error", None)
    return int(getter()) if getter is not None else 0


class WindowsGlobalHotkey:
    """Register exactly one Win32 hotkey and dispatch its WM_HOTKEY message."""

    def __init__(
        self,
        callback: Callable[[], None],
        logger: logging.Logger,
        *,
        user32: Any | None = None,
        hotkey_id: int = DEFAULT_HOTKEY_ID,
        modifiers: int = MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT,
        virtual_key: int = VK_O,
    ) -> None:
        self.callback = callback
        self.log = logger
        self.user32 = user32 if user32 is not None else _load_user32()
        self.hotkey_id = hotkey_id
        self.modifiers = modifiers
        self.virtual_key = virtual_key
        self.registered_hwnd: int | None = None
        self.last_error = 0

    @property
    def is_registered(self) -> bool:
        return self.registered_hwnd is not None

    def register(self, hwnd: int) -> bool:
        if self.user32 is None:
            return False
        hwnd = int(hwnd)
        if self.registered_hwnd == hwnd:
            return True
        self.unregister()
        _set_last_error(0)
        registered = bool(
            self.user32.RegisterHotKey(
                hwnd,
                self.hotkey_id,
                self.modifiers,
                self.virtual_key,
            )
        )
        if registered:
            self.registered_hwnd = hwnd
            self.last_error = 0
            return True
        self.last_error = _get_last_error()
        self.log.warning("Unable to register the global hotkey (Win32 error %s).", self.last_error)
        return False

    def unregister(self) -> None:
        if self.user32 is None or self.registered_hwnd is None:
            return
        self.user32.UnregisterHotKey(self.registered_hwnd, self.hotkey_id)
        self.registered_hwnd = None

    def dispatch(self, message: int, wparam: int) -> bool:
        if not self.is_registered or message != WM_HOTKEY or int(wparam) != self.hotkey_id:
            return False
        self.callback()
        return True


class WindowsOverlayController:
    """Apply topmost and click-through state without recreating or activating a window."""

    def __init__(self, logger: logging.Logger, *, user32: Any | None = None) -> None:
        self.log = logger
        self.user32 = user32 if user32 is not None else _load_user32()

    @property
    def available(self) -> bool:
        return self.user32 is not None

    def apply(self, hwnd: int, *, always_on_top: bool, click_through: bool) -> bool:
        if self.user32 is None:
            return False
        hwnd = int(hwnd)
        try:
            get_style = getattr(self.user32, "GetWindowLongPtrW", None)
            if get_style is None:
                get_style = self.user32.GetWindowLongW
            set_style = getattr(self.user32, "SetWindowLongPtrW", None)
            if set_style is None:
                set_style = self.user32.SetWindowLongW

            current_style = int(get_style(hwnd, GWL_EXSTYLE))
            updated_style = current_style
            if click_through:
                updated_style |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE
            else:
                updated_style &= ~WS_EX_TRANSPARENT
                updated_style &= ~WS_EX_NOACTIVATE
            if updated_style != current_style:
                set_style(hwnd, GWL_EXSTYLE, updated_style)

            insert_after = HWND_TOPMOST if always_on_top else HWND_NOTOPMOST
            _set_last_error(0)
            positioned = bool(
                self.user32.SetWindowPos(
                    hwnd,
                    insert_after,
                    0,
                    0,
                    0,
                    0,
                    WINDOW_STATE_FLAGS,
                )
            )
            if not positioned:
                self.log.warning(
                    "Unable to apply the native overlay state (Win32 error %s).",
                    _get_last_error(),
                )
            return positioned
        except (AttributeError, OSError, TypeError, ValueError) as exc:
            self.log.warning("Unable to apply the native overlay state: %s", exc)
            return False


def native_message_values(message_pointer: Any) -> tuple[int, int]:
    address = int(message_pointer)
    message = wintypes.MSG.from_address(address)
    return int(message.message), int(message.wParam)


def _load_user32() -> Any | None:
    if sys.platform != "win32":
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.RegisterHotKey.restype = wintypes.BOOL
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.UnregisterHotKey.restype = wintypes.BOOL

    long_pointer = ctypes.c_ssize_t
    get_style = getattr(user32, "GetWindowLongPtrW", None)
    if get_style is None:
        get_style = user32.GetWindowLongW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = long_pointer
    set_style = getattr(user32, "SetWindowLongPtrW", None)
    if set_style is None:
        set_style = user32.SetWindowLongW
    set_style.argtypes = [wintypes.HWND, ctypes.c_int, long_pointer]
    set_style.restype = long_pointer
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    return user32
