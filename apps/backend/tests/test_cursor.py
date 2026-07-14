from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cursor import decode_cursor, encode_cursor  # noqa: E402


class CursorTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        self.assertEqual(decode_cursor(encode_cursor(123)), 123)

    def test_none_starts_from_zero(self) -> None:
        self.assertEqual(decode_cursor(None), 0)

    def test_invalid_cursor_is_rejected(self) -> None:
        for value in ("invalid", "MA", "LTE"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                decode_cursor(value)
