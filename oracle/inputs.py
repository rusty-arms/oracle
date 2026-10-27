"""Parse input scripts: which GameCube controller state to hold on which frame.

Format (one statement per line, `#` starts a comment):

    frames 600              total frames to run; required, exactly once
    shot 0 300 599          take a screenshot after these frames; may repeat
    every 1                 record the trace every N frames (default 1)
    60 Start                hold Start on frame 60
    120-239 A StickY=1.0    hold A and full up on the main stick, frames 120 to 239 inclusive

Frames that no line covers are neutral: no buttons, sticks centred, triggers released.
Ranges must not overlap. Buttons are A B X Y Z Start Up Down Left Right L R. Axes are StickX
StickY CStickX CStickY (-1 to 1) and TriggerLeft TriggerRight (0 to 1).
"""

from __future__ import annotations

import re
from typing import Dict, NamedTuple, Union

BUTTONS = ("A", "B", "X", "Y", "Z", "Start", "Up", "Down", "Left", "Right", "L", "R")
STICKS = ("StickX", "StickY", "CStickX", "CStickY")
TRIGGERS = ("TriggerLeft", "TriggerRight")

Pad = Dict[str, Union[bool, float]]

_RANGE = re.compile(r"^(\d+)(?:-(\d+))?$")


class InputError(ValueError):
    pass


class Span(NamedTuple):
    first: int
    last: int
    pad: Pad
    line: int


class Plan(NamedTuple):
    frames: int
    shots: tuple[int, ...]
    every: int
    spans: tuple[Span, ...]

    def pad_at(self, frame: int) -> Pad:
        for span in self.spans:
            if span.first <= frame <= span.last:
                return span.pad
        return neutral()


def neutral() -> Pad:
    pad: Pad = {name: False for name in BUTTONS}
    pad.update({name: 0.0 for name in STICKS + TRIGGERS})
    return pad


def _int(text: str, lineno: int, what: str) -> int:
    if not text.isdigit():
        raise InputError(f"line {lineno}: {what} must be a whole number, got {text!r}")
    return int(text)


def _pad(tokens: list[str], lineno: int) -> Pad:
    pad = neutral()
    for token in tokens:
        if "=" in token:
            name, _, raw = token.partition("=")
            if name not in STICKS + TRIGGERS:
                raise InputError(f"line {lineno}: unknown axis {name!r}")
            try:
                value = float(raw)
            except ValueError:
                raise InputError(f"line {lineno}: {name} needs a number, got {raw!r}") from None
            low = 0.0 if name in TRIGGERS else -1.0
            if not low <= value <= 1.0:
                raise InputError(f"line {lineno}: {name}={raw} is outside {low:g} to 1")
            pad[name] = value
        elif token in BUTTONS:
            pad[token] = True
        else:
            raise InputError(f"line {lineno}: unknown button {token!r}")
    return pad


def parse(text: str) -> Plan:
    frames: int | None = None
    every = 1
    shots: list[int] = []
    spans: list[Span] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        words = raw.split("#", 1)[0].split()
        if not words:
            continue
        head, rest = words[0], words[1:]
        if head == "frames":
            if frames is not None:
                raise InputError(f"line {lineno}: 'frames' given twice")
            if len(rest) != 1:
                raise InputError(f"line {lineno}: 'frames' takes one number")
            frames = _int(rest[0], lineno, "frames")
            if frames < 1:
                raise InputError(f"line {lineno}: 'frames' must be at least 1")
        elif head == "every":
            if len(rest) != 1:
                raise InputError(f"line {lineno}: 'every' takes one number")
            every = _int(rest[0], lineno, "every")
            if every < 1:
                raise InputError(f"line {lineno}: 'every' must be at least 1")
        elif head == "shot":
            if not rest:
                raise InputError(f"line {lineno}: 'shot' needs at least one frame")
            shots.extend(_int(word, lineno, "a shot frame") for word in rest)
        else:
            match = _RANGE.match(head)
            if not match:
                raise InputError(f"line {lineno}: expected a frame or range, got {head!r}")
            first = int(match.group(1))
            last = int(match.group(2)) if match.group(2) else first
            if last < first:
                raise InputError(f"line {lineno}: range {head} runs backwards")
            spans.append(Span(first, last, _pad(rest, lineno), lineno))

    if frames is None:
        raise InputError("missing 'frames N' line")
    spans.sort(key=lambda span: span.first)
    for before, after in zip(spans, spans[1:]):
        if after.first <= before.last:
            raise InputError(f"line {after.line}: overlaps the range on line {before.line}")
    for span in spans:
        if span.last >= frames:
            raise InputError(
                f"line {span.line}: frame {span.last} is past the last frame ({frames - 1})"
            )
    for shot in shots:
        if shot >= frames:
            raise InputError(f"shot at frame {shot} is past the last frame ({frames - 1})")
    return Plan(frames, tuple(sorted(set(shots))), every, tuple(spans))
