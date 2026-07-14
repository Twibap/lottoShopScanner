from __future__ import annotations

import base64
import binascii


def encode_cursor(result_rank: int) -> str:
    if result_rank < 1:
        raise ValueError("result rank must be positive")
    return base64.urlsafe_b64encode(str(result_rank).encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        padding = "=" * (-len(cursor) % 4)
        value = int(base64.urlsafe_b64decode(cursor + padding).decode())
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise ValueError("invalid cursor") from exc
    if value < 1:
        raise ValueError("invalid cursor")
    return value
