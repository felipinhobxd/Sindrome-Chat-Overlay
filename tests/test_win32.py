from __future__ import annotations

import logging
import sys
import unittest

from sindrome_overlay.win32 import (
    GWL_EXSTYLE,
    HWND_NOTOPMOST,
    HWND_TOPMOST,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    VK_O,
    WM_HOTKEY,
    WINDOW_STATE_FLAGS,
    WS_EX_LAYERED,
    WS_EX_NOACTIVATE,
    WS_EX_TRANSPARENT,
    WindowsGlobalHotkey,
    WindowsOverlayController,
)


class FakeUser32:
    def __init__(self, register_result: bool = True) -> None:
        self.register_result = register_result
        self.register_calls: list[tuple[int, int, int, int]] = []
        self.unregister_calls: list[tuple[int, int]] = []

    def RegisterHotKey(self, hwnd, hotkey_id, modifiers, virtual_key):
        self.register_calls.append((hwnd, hotkey_id, modifiers, virtual_key))
        return self.register_result

    def UnregisterHotKey(self, hwnd, hotkey_id):
        self.unregister_calls.append((hwnd, hotkey_id))
        return True


class FakeOverlayUser32:
    def __init__(self, style: int = 0, position_result: bool = True) -> None:
        self.style = style
        self.position_result = position_result
        self.style_reads: list[tuple[int, int]] = []
        self.style_writes: list[tuple[int, int, int]] = []
        self.position_calls: list[tuple[int, int, int, int, int, int, int]] = []

    def GetWindowLongPtrW(self, hwnd, index):
        self.style_reads.append((hwnd, index))
        return self.style

    def SetWindowLongPtrW(self, hwnd, index, style):
        self.style_writes.append((hwnd, index, style))
        previous = self.style
        self.style = style
        return previous

    def SetWindowPos(self, hwnd, after, x, y, width, height, flags):
        self.position_calls.append((hwnd, after, x, y, width, height, flags))
        return self.position_result


class WindowsGlobalHotkeyTests(unittest.TestCase):
    def test_registers_once_with_no_repeat_and_dispatches_once(self) -> None:
        calls: list[str] = []
        user32 = FakeUser32()
        hotkey = WindowsGlobalHotkey(
            lambda: calls.append("toggle"),
            logging.getLogger("test"),
            user32=user32,
        )
        self.assertTrue(hotkey.register(100))
        self.assertTrue(hotkey.register(100))
        self.assertEqual(len(user32.register_calls), 1)
        _, hotkey_id, modifiers, virtual_key = user32.register_calls[0]
        self.assertEqual(modifiers, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT)
        self.assertEqual(virtual_key, VK_O)

        self.assertFalse(hotkey.dispatch(WM_HOTKEY, hotkey_id + 1))
        self.assertTrue(hotkey.dispatch(WM_HOTKEY, hotkey_id))
        self.assertEqual(calls, ["toggle"])

    def test_handle_change_unregisters_before_registering_again(self) -> None:
        user32 = FakeUser32()
        hotkey = WindowsGlobalHotkey(lambda: None, logging.getLogger("test"), user32=user32)
        hotkey.register(100)
        hotkey.register(200)
        self.assertEqual(user32.unregister_calls, [(100, hotkey.hotkey_id)])
        self.assertEqual([call[0] for call in user32.register_calls], [100, 200])

    def test_unregister_is_idempotent(self) -> None:
        user32 = FakeUser32()
        hotkey = WindowsGlobalHotkey(lambda: None, logging.getLogger("test"), user32=user32)
        hotkey.register(100)
        hotkey.unregister()
        hotkey.unregister()
        self.assertEqual(user32.unregister_calls, [(100, hotkey.hotkey_id)])

    def test_focus_minimize_settings_and_reconnect_do_not_duplicate_listener(self) -> None:
        calls: list[str] = []
        user32 = FakeUser32()
        hotkey = WindowsGlobalHotkey(
            lambda: calls.append("toggle"),
            logging.getLogger("test"),
            user32=user32,
        )
        for context in (
            "focused",
            "unfocused",
            "other-app",
            "windowed-game",
            "minimized",
            "restored",
            "settings",
            "provider-reconnect",
        ):
            with self.subTest(context=context):
                self.assertTrue(hotkey.register(100))
                self.assertTrue(hotkey.dispatch(WM_HOTKEY, hotkey.hotkey_id))
        self.assertEqual(len(user32.register_calls), 1)
        self.assertEqual(len(calls), 8)
        hotkey.unregister()
        self.assertEqual(user32.unregister_calls, [(100, hotkey.hotkey_id)])

    def test_conflict_is_reported_without_registering(self) -> None:
        user32 = FakeUser32(register_result=False)
        hotkey = WindowsGlobalHotkey(lambda: None, logging.getLogger("test"), user32=user32)
        self.assertFalse(hotkey.register(100))
        self.assertFalse(hotkey.is_registered)


class WindowsOverlayControllerTests(unittest.TestCase):
    def test_topmost_click_through_uses_noactivate_without_moving_or_resizing(self) -> None:
        user32 = FakeOverlayUser32(style=0x10)
        controller = WindowsOverlayController(logging.getLogger("test"), user32=user32)
        self.assertTrue(controller.apply(100, always_on_top=True, click_through=True))

        self.assertEqual(user32.style_reads, [(100, GWL_EXSTYLE)])
        expected_style = 0x10 | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE
        self.assertEqual(user32.style_writes, [(100, GWL_EXSTYLE, expected_style)])
        self.assertEqual(
            user32.position_calls,
            [(100, HWND_TOPMOST, 0, 0, 0, 0, WINDOW_STATE_FLAGS)],
        )

    def test_unlock_preserves_layered_style_and_can_remove_topmost(self) -> None:
        original = 0x10 | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE
        user32 = FakeOverlayUser32(style=original)
        controller = WindowsOverlayController(logging.getLogger("test"), user32=user32)
        self.assertTrue(controller.apply(200, always_on_top=False, click_through=False))

        self.assertEqual(user32.style, 0x10 | WS_EX_LAYERED)
        self.assertEqual(user32.position_calls[0][1], HWND_NOTOPMOST)

    def test_recovery_reasserts_topmost_without_rewriting_unchanged_style(self) -> None:
        user32 = FakeOverlayUser32(style=WS_EX_LAYERED)
        controller = WindowsOverlayController(logging.getLogger("test"), user32=user32)
        controller.apply(300, always_on_top=True, click_through=False)
        controller.apply(300, always_on_top=True, click_through=False)
        self.assertEqual(user32.style_writes, [])
        self.assertEqual(len(user32.position_calls), 2)
        self.assertTrue(all(call[1] == HWND_TOPMOST for call in user32.position_calls))


@unittest.skipUnless(sys.platform == "win32", "Requires the Windows RegisterHotKey API")
class WindowsGlobalHotkeyNativeTests(unittest.TestCase):
    def test_real_register_and_unregister(self) -> None:
        hotkey = WindowsGlobalHotkey(lambda: None, logging.getLogger("test"))
        try:
            self.assertTrue(hotkey.register(0))
            self.assertTrue(hotkey.is_registered)
        finally:
            hotkey.unregister()


if __name__ == "__main__":
    unittest.main()
