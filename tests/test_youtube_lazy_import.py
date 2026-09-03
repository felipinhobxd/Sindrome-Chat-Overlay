from __future__ import annotations

import json
import subprocess
import sys
import unittest


class YouTubeLazyImportTests(unittest.TestCase):
    @staticmethod
    def _run_probe(code: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout.strip())

    def test_importing_youtube_provider_does_not_load_grpc_or_protobuf(self) -> None:
        probe = self._run_probe(
            """
import json
import sys
import sindrome_overlay.providers.youtube  # noqa: F401

loaded = sorted(
    name
    for name in sys.modules
    if name == "grpc"
    or name.startswith("grpc.")
    or name == "google.protobuf"
    or name.startswith("google.protobuf.")
    or name.startswith("sindrome_overlay.youtube_grpc.stream_list_pb2")
)
print(json.dumps({"loaded": loaded}))
"""
        )
        self.assertEqual(probe["loaded"], [])

    def test_compatibility_provider_creation_keeps_official_stack_unloaded(self) -> None:
        probe = self._run_probe(
            """
import json
import queue
import sys
from sindrome_overlay.providers.youtube import YouTubeProvider

provider = YouTubeProvider(queue.Queue(), "https://youtu.be/abcdefghijk")
loaded = sorted(
    name
    for name in sys.modules
    if name == "grpc"
    or name.startswith("grpc.")
    or name == "google.protobuf"
    or name.startswith("google.protobuf.")
    or name.startswith("sindrome_overlay.youtube_grpc.stream_list_pb2")
)
provider.stop()
print(json.dumps({"loaded": loaded}))
"""
        )
        self.assertEqual(probe["loaded"], [])

    def test_official_stack_loads_only_when_first_used(self) -> None:
        probe = self._run_probe(
            """
import json
import sys
import sindrome_overlay.providers.youtube as youtube

before = {
    "grpc": "grpc" in sys.modules,
    "protobuf": "google.protobuf" in sys.modules,
}
_ = youtube.grpc.StatusCode.OK
_ = youtube.stream_list_pb2.LiveChatMessage

after = {
    "grpc": "grpc" in sys.modules,
    "protobuf": "google.protobuf" in sys.modules,
    "pb2": "sindrome_overlay.youtube_grpc.stream_list_pb2" in sys.modules,
}
print(json.dumps({"before": before, "after": after}))
"""
        )
        self.assertEqual(probe["before"], {"grpc": False, "protobuf": False})
        self.assertEqual(
            probe["after"],
            {"grpc": True, "protobuf": True, "pb2": True},
        )


if __name__ == "__main__":
    unittest.main()
