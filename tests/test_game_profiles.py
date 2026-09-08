from __future__ import annotations

import tempfile
import os
import sys
import unittest
from pathlib import Path

from sindrome_overlay.game_profiles import WindowsGameDetector
from sindrome_overlay.profiles import MAX_GAME_PROFILES, normalize_game_path, normalize_game_profiles
from sindrome_overlay.settings import Settings, SettingsStore

GAME = r"c:\games\game.exe"
OTHER = r"c:\games\other.exe"
BINDINGS = {GAME: "builtin:compact_fps", OTHER: "builtin:chat_focus"}


class FakeWindows:
    def __init__(self):
        self.foreground = 1
        self.processes = {
            1: {"path": GAME, "alive": True},
            2: {"path": r"c:\browser.exe", "alive": True},
            3: {"path": OTHER, "alive": True},
        }
        self.handles = {}
        self.next_handle = 2**40
        self.denied = False
        self.query_failure = False

    def GetForegroundWindow(self):
        return self.foreground

    def GetWindowThreadProcessId(self, hwnd, pid):
        pid._obj.value = hwnd
        return 1

    def OpenProcess(self, flags, inherit, pid):
        if self.denied:
            return None
        self.next_handle += 1
        self.handles[self.next_handle] = self.processes[pid]
        return self.next_handle

    def QueryFullProcessImageNameW(self, handle, flags, buffer, size):
        buffer.value = self.handles[handle]["path"]
        return not self.query_failure

    def WaitForSingleObject(self, handle, timeout):
        assert timeout == 0
        return 0x102 if self.handles[handle]["alive"] else 0

    def CloseHandle(self, handle):
        del self.handles[handle]
        return True


class GameProfileTests(unittest.TestCase):
    def setUp(self):
        self.native = FakeWindows()
        self.detector = WindowsGameDetector(user32=self.native, kernel32=self.native)
        self.addCleanup(self.detector.close)

    def test_alt_tab_retains_profile_and_only_one_handle(self):
        self.assertEqual(self.detector.profile(BINDINGS), BINDINGS[GAME])
        self.native.foreground = 2
        for _ in range(50):
            self.assertEqual(self.detector.profile(BINDINGS), BINDINGS[GAME])
            self.assertEqual(len(self.native.handles), 1)
        self.native.foreground = 0
        self.assertEqual(self.detector.profile(BINDINGS), BINDINGS[GAME])
        self.native.processes[1]["alive"] = False
        self.assertEqual(self.detector.profile(BINDINGS), "")
        self.assertFalse(self.native.handles)

    def test_switching_games_releases_previous_handle(self):
        self.detector.profile(BINDINGS)
        self.native.foreground = 3
        self.assertEqual(self.detector.profile(BINDINGS), BINDINGS[OTHER])
        self.assertEqual(len(self.native.handles), 1)
        self.detector.close()
        self.detector.close()
        self.assertFalse(self.native.handles)

    def test_reused_pid_does_not_keep_dead_game_profile(self):
        self.detector.profile(BINDINGS)
        self.native.processes[1]["alive"] = False
        self.native.processes[1] = {"path": r"c:\other\game.exe", "alive": True}
        self.assertEqual(self.detector.profile(BINDINGS), "")
        self.assertFalse(self.native.handles)

    def test_access_denied_or_failed_query_does_not_drop_live_profile_or_leak_handles(self):
        self.detector.profile(BINDINGS)
        self.native.foreground = 2
        self.native.denied = True
        self.assertEqual(self.detector.profile(BINDINGS), BINDINGS[GAME])
        self.native.denied = False
        self.native.query_failure = True
        self.assertEqual(self.detector.profile(BINDINGS), BINDINGS[GAME])
        self.assertEqual(len(self.native.handles), 1)
        self.assertEqual(self.detector.profile({}), "")
        self.assertFalse(self.native.handles)

    def test_bindings_are_validated_bounded_and_round_trip(self):
        supplied = {
            "C:/Games/Game.EXE": BINDINGS[GAME],
            r"c:\bad.exe": "custom:Missing",
            "relative.exe": BINDINGS[GAME],
            r"c:relative.exe": BINDINGS[GAME],
            r"c:\script.bat": BINDINGS[GAME],
            "c:\\bad\x00.exe": BINDINGS[GAME],
        }
        self.assertEqual(normalize_game_profiles(supplied, {}), {GAME: BINDINGS[GAME]})
        many = {rf"c:\games\{n}.exe": BINDINGS[GAME] for n in range(100)}
        self.assertEqual(len(normalize_game_profiles(many, {})), MAX_GAME_PROFILES)
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            store.save(Settings(automatic_profiles_enabled=True, game_profiles=supplied))
            loaded = store.load()
        self.assertTrue(loaded.automatic_profiles_enabled)
        self.assertEqual(loaded.game_profiles, {GAME: BINDINGS[GAME]})
        self.assertFalse(Settings().automatic_profiles_enabled)

    @unittest.skipUnless(sys.platform == "win32", "Real Win32 process API validation")
    def test_real_windows_process_query_uses_correct_native_handle_types(self):
        detector = WindowsGameDetector()
        self.addCleanup(detector.close)
        foreground = FakeWindows()
        foreground.foreground = os.getpid()
        detector.user32 = foreground
        bindings = {normalize_game_path(sys.executable): "builtin:compact_fps"}
        self.assertEqual(detector.profile(bindings), "builtin:compact_fps")
        foreground.foreground = 0
        self.assertEqual(detector.profile(bindings), "builtin:compact_fps")
