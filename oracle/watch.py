"""Parse watch lists: which emulated RAM values to record each frame.

Format (one watch per line, `#` starts a comment):

    disc_id     0x80000000                  u32
    some_value  0x80401000 -> 0x10 -> 0x4   f32

The first column is the name used as the trace's column header. The address is a GameCube
main-memory address (0x80000000 to 0x817FFFFF). Each `-> offset` follows a pointer: read the
32-bit word at the current address, then add the offset. If a pointer on the way is outside main
memory, the value is recorded as empty for that frame.

Types: u8 u16 u32 u64 s8 s16 s32 s64 f32 f64.

Watch lists name addresses in the game, which are observations, so real ones stay in the lab.
"""

from __future__ import annotations

import re
from typing import Callable, NamedTuple, Union

MEM1_START = 0x80000000
MEM1_END = 0x81800000  # exclusive: 24 MiB of main memory

TYPES = ("u8", "u16", "u32", "u64", "s8", "s16", "s32", "s64", "f32", "f64")
SIZES = {"8": 1, "16": 2, "32": 4, "64": 8}

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

Value = Union[int, float, None]
Reader = Callable[[str, int], Union[int, float]]


class WatchError(ValueError):
    pass


class Watch(NamedTuple):
    name: str
    base: int
    offsets: tuple[int, ...]
    type: str

    def size(self) -> int:
        return SIZES[self.type[1:]]

    def read(self, reader: Reader) -> Value:
        """Read this watch's value now; `reader(type, address)` reads one value from memory."""
        address = self.base
        for offset in self.offsets:
            pointer = int(reader("u32", address))
            address = pointer + offset
            if not in_mem1(address, 1):
                return None
        if not in_mem1(address, self.size()):
            return None
        return reader(self.type, address)


def in_mem1(address: int, size: int) -> bool:
    return MEM1_START <= address and address + size <= MEM1_END


def _number(text: str, lineno: int) -> int:
    try:
        return int(text, 0)
    except ValueError:
        raise WatchError(f"line {lineno}: {text!r} is not a number (use 0x for hex)") from None


def parse(text: str) -> list[Watch]:
    watches: list[Watch] = []
    seen = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        words = raw.split("#", 1)[0].split()
        if not words:
            continue
        if len(words) < 3:
            raise WatchError(f"line {lineno}: expected 'name address type'")
        name, kind = words[0], words[-1]
        if not _NAME.match(name) or name == "frame":
            raise WatchError(f"line {lineno}: {name!r} is not a usable column name")
        if name in seen:
            raise WatchError(f"line {lineno}: {name!r} is watched twice")
        if kind not in TYPES:
            raise WatchError(f"line {lineno}: unknown type {kind!r}; use one of {' '.join(TYPES)}")
        address = words[1:-1]
        base = _number(address[0], lineno)
        offsets: list[int] = []
        rest = address[1:]
        if len(rest) % 2:
            raise WatchError(f"line {lineno}: write pointer steps as '-> offset'")
        for arrow, offset in zip(rest[::2], rest[1::2]):
            if arrow != "->":
                raise WatchError(f"line {lineno}: expected '->', got {arrow!r}")
            offsets.append(_number(offset, lineno))
        size = 4 if offsets else SIZES[kind[1:]]
        if not in_mem1(base, size):
            raise WatchError(f"line {lineno}: {address[0]} is outside main memory")
        seen.add(name)
        watches.append(Watch(name, base, tuple(offsets), kind))
    return watches


def format_value(value: Value) -> str:
    """Write a value for the trace: exact, and identical across runs and Python versions."""
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(int(value))


def parse_value(text: str) -> int | float | None:
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return float(text)
