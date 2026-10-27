"""The frame-by-frame replay loop, kept apart from Dolphin's API so tests can drive it.

Timing, counted in frame-advance callbacks from when the rig starts (after any savestate loads):

- At callback k the rig records trace row k, so row 0 is the state the run started from.
- It then sets the controller to the input script's state for frame k, which the game sees from
  then until callback k + 1. So row k reflects the inputs of frames 0 to k - 1.
- A screenshot for frame k is the first frame drawn after callback k.

After the last frame the controller goes neutral, and the rig waits up to `SHOT_GRACE` more
frames for screenshots still owed, then reports.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable

from . import __version__, png
from .inputs import Pad, Plan, neutral
from .watch import Reader, Watch, format_value

SHOT_GRACE = 30
RESULT = "result.json"
TRACE = "trace.csv"


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def shot_name(frame: int) -> str:
    return f"frame_{frame:06d}.png"


class Recorder:
    def __init__(
        self,
        plan: Plan,
        watches: list[Watch],
        out_dir: str,
        shots_dir: str,
        read: Reader,
        set_pad: Callable[[Pad], None],
    ) -> None:
        self.plan = plan
        self.watches = watches
        self.out_dir = out_dir
        self.shots_dir = shots_dir
        self.read = read
        self.set_pad = set_pad
        self.callbacks = 0
        self.pending: list[int] = []
        self.shots: dict[str, dict[str, Any]] = {}
        self.error: str | None = None
        self.done = False
        os.makedirs(out_dir, exist_ok=True)
        if plan.shots:
            os.makedirs(shots_dir, exist_ok=True)
        # Held open for the whole run and closed in finish().
        self.trace = open(  # noqa: SIM115
            os.path.join(out_dir, TRACE), "w", encoding="ascii", newline="\n"
        )
        self.trace.write(",".join(["frame"] + [w.name for w in watches]) + "\n")

    @property
    def wants_frames(self) -> bool:
        return bool(self.plan.shots)

    def on_frame(self) -> bool:
        """Handle one frame-advance callback. Returns True once the run is over."""
        if self.done:
            return True
        try:
            self._step()
        except Exception as exc:  # noqa: BLE001  report it; never leave Dolphin hanging
            self.error = f"frame {self.callbacks}: {type(exc).__name__}: {exc}"
            self.finish()
        return self.done

    def _step(self) -> None:
        k = self.callbacks
        self.callbacks += 1
        if k < self.plan.frames:
            if k % self.plan.every == 0:
                row = [str(k)] + [format_value(w.read(self.read)) for w in self.watches]
                self.trace.write(",".join(row) + "\n")
            if k in self.plan.shots:
                self.pending.append(k)
            self.set_pad(self.plan.pad_at(k))
            return
        self.set_pad(neutral())
        if not self.pending or k >= self.plan.frames + SHOT_GRACE:
            self.finish()

    def on_drawn(self, width: int, height: int, data: bytes) -> None:
        if self.done or not self.pending:
            return
        frame = self.pending.pop(0)
        try:
            name = shot_name(frame)
            path = os.path.join(self.shots_dir, name)
            with open(path, "wb") as handle:
                handle.write(png.encode(width, height, data))
            self.shots[str(frame)] = {
                "file": name,
                "width": width,
                "height": height,
                "sha256": sha256_file(path),
            }
        except Exception as exc:  # noqa: BLE001  same: report, never hang
            self.error = f"screenshot for frame {frame}: {type(exc).__name__}: {exc}"
            self.finish()

    def finish(self) -> dict[str, Any]:
        if not self.trace.closed:
            self.trace.close()
        self.done = True
        missed = [frame for frame in self.plan.shots if str(frame) not in self.shots]
        if missed and not self.error:
            self.error = f"no frame was drawn for screenshots at {missed}"
        result = {
            "rig_version": __version__,
            "frames": self.plan.frames,
            "every": self.plan.every,
            "callbacks": self.callbacks,
            "columns": ["frame"] + [w.name for w in self.watches],
            "trace_sha256": sha256_file(os.path.join(self.out_dir, TRACE)),
            "shots": self.shots,
            "error": self.error,
        }
        temp = os.path.join(self.out_dir, RESULT + ".tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp, os.path.join(self.out_dir, RESULT))
        return result
