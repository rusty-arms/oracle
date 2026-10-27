"""A stand-in for a Python-scripting Dolphin build, for tests. It runs no game.

It takes the same command-line options the launcher passes, provides a fake `dolphin` module,
runs the --script, then emulates frames of a made-up "game":

- 0x80400000 (u32) counts the frames on which A was held;
- 0x80400004 (f32) adds up StickX;
- 0x80400008 (u32) holds a pointer to 0x80400010, where 0x80400014 (u32) is 7.

Each drawn frame is 4x2 RGB pixels derived from the frame number. FAKE_DOLPHIN_MODE changes its
behaviour: "random" makes the A counter jitter, "crash" exits early, "trap" dies of SIGILL after logging a line, "hang" never runs the script.
"""

import argparse
import os
import random
import runpy
import signal
import struct
import sys
import time
import types

MEM1 = 0x80000000


class Ram:
    def __init__(self):
        self.data = bytearray(0x01800000)

    def _span(self, addr, size):
        offset = addr - MEM1
        if offset < 0 or offset + size > len(self.data):
            raise ValueError(f"bad address {addr:#x}")
        return offset

    def read(self, fmt, addr):
        return struct.unpack_from(">" + fmt, self.data, self._span(addr, struct.calcsize(fmt)))[0]

    def write(self, fmt, addr, value):
        struct.pack_into(">" + fmt, self.data, self._span(addr, struct.calcsize(fmt)), value)


FORMATS = {
    "u8": "B",
    "u16": "H",
    "u32": "I",
    "u64": "Q",
    "s8": "b",
    "s16": "h",
    "s32": "i",
    "s64": "q",
    "f32": "f",
    "f64": "d",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--user")
    parser.add_argument("--exec")
    parser.add_argument("--script")
    parser.add_argument("--config", action="append", default=[])
    parser.add_argument("--save_state")
    args, _ = parser.parse_known_args()
    mode = os.environ.get("FAKE_DOLPHIN_MODE", "")
    if mode == "hang":
        time.sleep(600)
    if not os.path.isdir(args.user) or not os.path.isfile(args.exec):
        sys.exit("fake dolphin: missing user folder or disc")

    ram = Ram()
    ram.write("4s", MEM1, b"TEST")
    ram.write("I", MEM1 + 0x28, 0x01800000)
    ram.write("I", 0x80400008, 0x80400010)
    ram.write("I", 0x80400014, 7)
    state = {"pad": {}, "paused": False, "frame": None, "drawn": None}

    dolphin = types.ModuleType("dolphin")
    memory = types.ModuleType("dolphin.memory")
    for name, fmt in FORMATS.items():
        setattr(memory, "read_" + name, lambda addr, fmt=fmt: ram.read(fmt, addr))
    controller = types.ModuleType("dolphin.controller")
    controller.set_gc_buttons = lambda port, pad: state.__setitem__("pad", dict(pad))
    emulation = types.ModuleType("dolphin.emulation")
    emulation.pause = lambda: state.__setitem__("paused", True)
    event = types.ModuleType("dolphin.event")
    event.on_frameadvance = lambda callback: state.__setitem__("frame", callback)
    event.on_framedrawn = lambda callback: state.__setitem__("drawn", callback)
    for module in (memory, controller, emulation, event):
        setattr(dolphin, module.__name__.split(".")[1], module)
        sys.modules[module.__name__] = module
    sys.modules["dolphin"] = dolphin

    runpy.run_path(args.script, run_name="__main__")

    for frame in range(100000):
        if state["paused"]:
            break
        if mode == "crash" and frame == 5:
            sys.exit(3)
        if mode == "trap" and frame == 5:
            print("fake dolphin: about to trap", flush=True)
            signal.raise_signal(signal.SIGILL)
        pad = state["pad"]
        if pad.get("A"):
            jitter = random.randint(0, 1) if mode == "random" else 0
            ram.write("I", 0x80400000, ram.read("I", 0x80400000) + 1 + jitter)
        ram.write("f", 0x80400004, ram.read("f", 0x80400004) + pad.get("StickX", 0.0))
        if state["frame"]:
            state["frame"]()
        if state["drawn"]:
            state["drawn"](4, 2, bytes((frame + i) % 256 for i in range(4 * 2 * 3)))
    time.sleep(600)  # like Dolphin, stay open while paused until the launcher stops it


if __name__ == "__main__":
    main()
