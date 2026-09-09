from __future__ import annotations

import json
import unittest

from sindrome_overlay.remote_control import remote_control_state, validate_remote_command
from sindrome_overlay.settings import Settings


class RemoteControlContractTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(overlay_profiles={"Game": {"font_size": 20}})

    def test_supported_commands_and_boundary_values(self):
        commands = [
            {"action": "set_appearance", "value": {"font_size": 11, "background_opacity": 0}},
            {"action": "set_appearance", "value": {"font_size": 30, "card_opacity": 100}},
            {"action": "set_auto_scroll", "value": False},
            {"action": "set_click_through", "value": True},
            {"action": "apply_profile", "value": "builtin:compact_fps"},
            {"action": "apply_profile", "value": "custom:Game"},
            {"action": "clear_messages"},
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(validate_remote_command(command, self.settings), command)

    def test_malformed_or_extra_fields_are_rejected(self):
        invalid = [None, [], "clear_messages", {}, {"action": []}, {"action": "run_shell"},
                   {"action": "clear_messages", "value": None},
                   {"action": "set_auto_scroll"},
                   {"action": "set_auto_scroll", "value": False, "youtube_api_key": "private"}]
        for command in invalid:
            with self.subTest(command=command), self.assertRaises(ValueError):
                validate_remote_command(command, self.settings)

    def test_boolean_commands_do_not_coerce_strings_or_numbers(self):
        for action in ("set_auto_scroll", "set_click_through"):
            for value in (0, 1, "false", "true", None, []):
                with self.subTest(action=action, value=value), self.assertRaises(ValueError):
                    validate_remote_command({"action": action, "value": value}, self.settings)

    def test_appearance_rejects_credentials_wrong_types_and_out_of_range_values(self):
        invalid = [{}, [], {"font_size": True}, {"font_size": "20"}, {"font_size": 20.5},
                   {"font_size": 10}, {"font_size": 31}, {"background_opacity": -1},
                   {"card_opacity": 101}, {"youtube_api_key": "private"}, {"window_x": 50}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_remote_command({"action": "set_appearance", "value": value}, self.settings)

    def test_deleted_or_unknown_profiles_are_rejected(self):
        del self.settings.overlay_profiles["Game"]
        for value in ("custom:Game", "builtin:missing", {}, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_remote_command({"action": "apply_profile", "value": value}, self.settings)

    def test_validation_does_not_modify_settings_or_share_mutable_payload(self):
        payload = {"action": "set_appearance", "value": {"font_size": 20}}
        validated = validate_remote_command(payload, self.settings)
        payload["value"]["font_size"] = 999
        self.assertEqual(validated["value"], {"font_size": 20})
        self.assertEqual(self.settings.font_size, 15)

    def test_snapshot_omits_private_settings_and_cannot_mutate_profiles(self):
        self.settings.youtube_api_key = "private-key"
        self.settings.youtube_input = "private-channel"
        self.settings.game_profiles = {r"c:\private\game.exe": "custom:Game"}
        snapshot = remote_control_state(self.settings)
        self.assertNotIn("private", json.dumps(snapshot))
        self.assertEqual(set(snapshot), {
            "appearance", "auto_scroll", "click_through", "active_profile", "profiles",
        })
        snapshot["appearance"]["font_size"] = 999
        snapshot["profiles"].clear()
        self.assertEqual(self.settings.font_size, 15)
        self.assertIn("Game", self.settings.overlay_profiles)

    def test_error_messages_do_not_echo_submitted_secrets(self):
        with self.assertRaises(ValueError) as caught:
            validate_remote_command({"action": "private-api-key"}, self.settings)
        self.assertNotIn("private-api-key", str(caught.exception))
