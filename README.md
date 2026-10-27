# Rusty Arms oracle rig

The oracle rig replays a scripted input file in Dolphin, running the owner's own disc, and records a RAM trace and screenshots. Those recordings are the reference that the engine is checked against ([D4, oracle-first](https://github.com/rusty-arms/core/blob/main/docs/decisions/0004-oracle-first.md)).

This repo holds **only the rig's code**. It has no game data, no addresses in the game and no captures, and it never will. Real input scripts, watch lists, traces and screenshots live in the owner's local lab ([D9](https://github.com/rusty-arms/core/blob/main/docs/decisions/0009-lab-off-github.md)).

Standard library Python only. The part that runs inside Dolphin works on Python 3.8 or later.

## What you need

- **A Dolphin build with Python scripting.** Mainline Dolphin has no scripting. The rig uses [Felk's public fork of Dolphin](https://github.com/Felk/dolphin), which adds an embedded Python interpreter and a `dolphin` module (memory, controller, events, savestates). Its "Python Scripting Preview" releases ship Windows x64 builds; on other systems you build the fork from source.
- Python 3.8 or later on the host, to run the launcher.
- The disc image, verified as in core's owner checklist.

## Quick start

```sh
export ORACLE_DOLPHIN=/path/to/Dolphin.exe      # the scripting build
export ORACLE_DISC=/path/to/lab/disc/image.iso
cd /path/to/this/repo

# Check the files and see the command, without starting Dolphin:
python3 -m oracle.replay examples/smoke.inputs --watch examples/smoke.watch \
    --out /path/to/lab/traces/smoke --shots /path/to/lab/captures/smoke --dry-run

# Replay twice and check that both runs match:
python3 -m oracle.replay examples/smoke.inputs --watch examples/smoke.watch \
    --out /path/to/lab/traces/smoke --shots /path/to/lab/captures/smoke --repeat 2
```

The smoke test boots the disc, waits ten seconds and takes two screenshots. Its watches are generic GameCube boot values from public hardware documentation, so it needs no knowledge of the game.

## Input scripts

One statement per line; `#` starts a comment.

```text
frames 900               # total frames to run; required
every 2                  # record the trace every 2nd frame (default 1)
shot 0 450 899           # screenshots after these frames

300 Start                # hold Start on frame 300
360-369 Down             # hold Down on frames 360 to 369
480-539 StickX=-0.5 TriggerRight=1.0
```

- Frames no line covers are neutral: no buttons, sticks centred, triggers released.
- Ranges must not overlap.
- Buttons: `A B X Y Z Start Up Down Left Right L R`.
- Axes: `StickX StickY CStickX CStickY` from -1 to 1, and `TriggerLeft TriggerRight` from 0 to 1.

Frames are counted in Dolphin frame-advance callbacks from the moment the run starts, after any savestate has loaded:

- trace row *k* is the state at callback *k*, so row 0 is where the run started and row *k* reflects the inputs of frames 0 to *k* − 1;
- the inputs for frame *k* are set at callback *k* and held until callback *k* + 1;
- the screenshot for frame *k* is the first frame drawn after callback *k*.

[`examples/menu-walk.inputs`](examples/menu-walk.inputs) shows every statement. It is made up and is not a route through any real menu.

## Watch lists

```text
# name      address                    type
counter     0x80401000                 u32
some_float  0x80401000 -> 0x10 -> 0x4  f32
```

- The name becomes the trace's column header.
- Addresses are in main memory, 0x80000000 to 0x817FFFFF.
- Each `-> offset` follows a pointer: read the 32-bit word at the current address and add the offset. If a pointer leaves main memory, that frame's value is empty.
- Types: `u8 u16 u32 u64 s8 s16 s32 s64 f32 f64`.

Addresses in the game are observations, so **real watch lists stay in the lab** (for example in `notes/`), and each fact they lead to gets a provenance entry in core before it goes into a spec.

## What a run writes

| File | Where | Contents |
|---|---|---|
| `trace.csv` | `--out` | One row per traced frame: `frame`, then one column per watch. Integers in decimal, floats exactly as Python's `repr`, empty for an unreadable pointer. |
| `run.json` | `--out` | Hashes of the trace, the input script, the watch list, the savestate and each screenshot; the Dolphin command and settings; whether repeats matched; any error. |
| `dolphin.log` | `--out` | Dolphin's own output. |
| `frame_NNNNNN.png` | `--shots` | One screenshot per `shot` frame. |

In the lab, point `--out` at `traces/<name>` (tracked in the lab's git) and `--shots` at `captures/<name>` (not tracked). The launcher **refuses to write into a folder that already has files**, so a golden trace is never overwritten.

## Repeatable runs

Each run starts Dolphin with a fresh, empty user folder, so your everyday settings, memory cards and controller setup never leak in. Pass `--user-template DIR` to copy a prepared user folder instead, for example one with a formatted memory card. The launcher also sets these overrides, listed in `oracle/replay.py`:

- single-core emulation and a fixed real-time clock, for determinism;
- cheats off, unlimited emulation speed, no pause on focus loss, no analytics prompt;
- internal resolution 1x, as the research brief recommends.

`--repeat N` replays N times and fails unless every trace and screenshot is identical. Run it whenever the rig, the Dolphin build or the settings change.

`--state FILE` starts from a Dolphin savestate instead of booting. Savestates only load in the Dolphin version that made them, and `run.json` records the savestate's hash.

## Comparing traces

```sh
python3 -m oracle.compare golden/trace.csv candidate/trace.csv --tol some_float=0.001
```

It reports, for each column, the first frame where the two traces differ. Exit code 0 means they match. Phase 2 uses this to check the engine's traces against Dolphin's.

## Tests

```sh
python3 -m unittest discover -s tests
```

The tests drive the launcher end to end against `tests/fake_dolphin.py`, a stand-in that provides the same `dolphin` module and command line over a made-up "game". CI runs them on GitHub-hosted runners; nothing in CI touches the disc or Dolphin.

## Not yet verified on a real Dolphin

These come from the scripting fork's published API stubs and Dolphin's source, and the first real run checks them:

- that `--script` runs in `--batch` mode and its callbacks fire from the first frame;
- the pixel layout that `on_framedrawn` passes (the rig accepts RGB or RGBA);
- that `controller.set_gc_buttons` fully overrides port 1 every frame;
- that the settings above make two runs from boot identical.

## Licence

MIT OR Apache-2.0, at your option.
