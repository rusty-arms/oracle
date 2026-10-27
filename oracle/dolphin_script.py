"""Entry point that Dolphin runs with `--script`. Start runs with `python3 -m oracle.replay`.

It needs a build of Dolphin with Python scripting, which provides the `dolphin` module. The
launcher passes the run's settings through a JSON file named by the ORACLE_RUN variable.
"""

import json
import os
import sys

with open(os.environ["ORACLE_RUN"], encoding="utf-8") as _handle:
    _config = json.load(_handle)
sys.path.insert(0, _config["package_dir"])

from dolphin import controller, emulation, event, memory

from oracle import inputs, watch
from oracle.recorder import Recorder

_READERS = {name: getattr(memory, "read_" + name) for name in watch.TYPES}


def _read(kind, address):
    return _READERS[kind](address)


def _set_pad(pad):
    controller.set_gc_buttons(_config.get("port", 0), pad)


with open(_config["inputs"], encoding="utf-8") as _handle:
    _plan = inputs.parse(_handle.read())
_watches = []
if _config.get("watch"):
    with open(_config["watch"], encoding="utf-8") as _handle:
        _watches = watch.parse(_handle.read())

_recorder = Recorder(_plan, _watches, _config["out_dir"], _config["shots_dir"], _read, _set_pad)
_stopped = False


def _stop():
    # The scripting fork can't unregister a callback (it rejects None), so once the run is over
    # the callbacks stay registered and do nothing. Pause once; the launcher then stops Dolphin.
    global _stopped
    if not _stopped:
        _stopped = True
        emulation.pause()


def _on_frame():
    if _stopped:
        return
    if _recorder.on_frame():
        _stop()


def _on_drawn(width, height, data):
    if _stopped:
        return
    _recorder.on_drawn(width, height, data)
    if _recorder.done:
        _stop()


event.on_frameadvance(_on_frame)
if _recorder.wants_frames:
    event.on_framedrawn(_on_drawn)
