"""Write raw RGB or RGBA frames as PNG files, with the standard library only."""

from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def encode(width: int, height: int, data: bytes) -> bytes:
    """Encode `data`, rows top to bottom, as PNG. Works out RGB or RGBA from its length."""
    if width < 1 or height < 1:
        raise ValueError(f"bad frame size {width}x{height}")
    channels, extra = divmod(len(data), width * height)
    if extra or channels not in (3, 4):
        raise ValueError(f"{len(data)} bytes is not an RGB or RGBA frame of {width}x{height}")
    stride = width * channels
    rows = b"".join(b"\x00" + data[y * stride : (y + 1) * stride] for y in range(height))
    colour = 2 if channels == 3 else 6
    header = struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(rows, 6))
        + _chunk(b"IEND", b"")
    )
