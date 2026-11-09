from __future__ import annotations

import unittest
from types import SimpleNamespace

from PySide6.QtCore import QByteArray

from sindrome_overlay.ui.twitch_assets import (
    TwitchAssetCache,
    _MAX_IMAGE_BYTES,
    _MAX_MANIFEST_BYTES,
)


class FakeReply:
    def __init__(self) -> None:
        self.pending = bytearray()
        self.aborted = False
        self.bytes_read = 0

    def bytesAvailable(self) -> int:
        return len(self.pending)

    def read(self, amount: int) -> QByteArray:
        chunk = bytes(self.pending[:amount])
        del self.pending[:amount]
        self.bytes_read += len(chunk)
        return QByteArray(chunk)

    def abort(self) -> None:
        self.aborted = True


def _context(reply: FakeReply, limit: int) -> SimpleNamespace:
    return SimpleNamespace(
        _reply_buffers={reply: bytearray()},
        _reply_limits={reply: limit},
        _oversized_replies=set(),
    )


def _receive(context: SimpleNamespace, reply: FakeReply, data: bytes) -> None:
    reply.pending.extend(data)
    TwitchAssetCache._consume_reply_data(context, reply)


class BoundedQtDownloadTests(unittest.TestCase):
    def test_image_accepts_incremental_chunks_through_exact_limit(self) -> None:
        reply = FakeReply()
        context = _context(reply, _MAX_IMAGE_BYTES)
        _receive(context, reply, b"a" * 100)
        _receive(context, reply, b"b" * (_MAX_IMAGE_BYTES - 100))
        self.assertEqual(len(context._reply_buffers[reply]), _MAX_IMAGE_BYTES)
        self.assertFalse(reply.aborted)

    def test_image_aborts_before_reading_oversized_chunk(self) -> None:
        reply = FakeReply()
        context = _context(reply, _MAX_IMAGE_BYTES)
        _receive(context, reply, b"x" * (_MAX_IMAGE_BYTES + 1))
        self.assertTrue(reply.aborted)
        self.assertIn(reply, context._oversized_replies)
        self.assertEqual(reply.bytes_read, 0)
        self.assertEqual(len(context._reply_buffers[reply]), 0)

    def test_image_aborts_on_later_chunk_exceeding_limit(self) -> None:
        reply = FakeReply()
        context = _context(reply, 10)
        _receive(context, reply, b"abcde")
        _receive(context, reply, b"fghijk")
        self.assertTrue(reply.aborted)
        self.assertEqual(bytes(context._reply_buffers[reply]), b"abcde")
        self.assertEqual(reply.bytes_read, 5)

    def test_manifest_has_separate_limit(self) -> None:
        reply = FakeReply()
        context = _context(reply, _MAX_MANIFEST_BYTES)
        _receive(context, reply, b"m" * (_MAX_IMAGE_BYTES + 1))
        self.assertFalse(reply.aborted)
        _receive(context, reply, b"n" * (_MAX_MANIFEST_BYTES - _MAX_IMAGE_BYTES))
        self.assertTrue(reply.aborted)
        self.assertEqual(len(context._reply_buffers[reply]), _MAX_IMAGE_BYTES + 1)


if __name__ == "__main__":
    unittest.main()
