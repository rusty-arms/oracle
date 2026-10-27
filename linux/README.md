# Building the scripting Dolphin on Linux

The Python-scripting fork of Dolphin publishes Windows builds only. On a Linux lab PC, build it from source with [`build-dolphin.sh`](build-dolphin.sh). It targets Ubuntu 24.04 and Pop!_OS 24.04.

The fork's scripting module links against the system Python through CMake. These releases ship Python 3.12, the same version the fork's Windows build bundles. Apart from the Python headers, the build is a standard Dolphin build.

## Build

```sh
git clone https://github.com/rusty-arms/oracle.git ~/Develop/rusty-arms/oracle
~/Develop/rusty-arms/oracle/linux/build-dolphin.sh
```

The script:

1. installs Dolphin's build dependencies with `apt` (it asks for your password);
2. clones the fork at the `scripting-preview4` tag, with its submodules, into `~/Develop/rusty-arms/dolphin-scripting/src`;
3. builds it into `~/Develop/rusty-arms/dolphin-scripting/build`.

The first build takes roughly 30 to 60 minutes. To build another release, set `TAG`, for example `TAG=scripting-preview5 linux/build-dolphin.sh`.

The build installs nothing system-wide apart from the `apt` packages, and leaves any Dolphin you already have alone. Keep it outside the lab: it holds no game data.

The script built the fork on Pop!_OS 24.04 on 2026-10-27. If the build fails, send the last 50 lines of its output, which hold no game data, and it will be fixed. If it can't be made to work, [`vm/`](../vm/README.md) runs the Windows build in a local VM instead, more slowly.

## Check it

```sh
~/Develop/rusty-arms/dolphin-scripting/build/Binaries/dolphin-emu
```

Dolphin should open. **View → Scripting** should exist; that menu is the fork's.

## Wayland

On a Wayland desktop, such as COSMIC on Pop!_OS 24.04, this build opens its window but never runs a frame: the video backends hang while booting. The rig avoids this by running Dolphin through X11 (XWayland) with `QT_QPA_PLATFORM=xcb`. To start the build by hand, do the same:

```sh
QT_QPA_PLATFORM=xcb ~/Develop/rusty-arms/dolphin-scripting/build/Binaries/dolphin-emu
```

## Run the smoke test

```sh
export ORACLE_DOLPHIN=~/Develop/rusty-arms/dolphin-scripting/build/Binaries/dolphin-emu
export ORACLE_DISC=~/Develop/rusty-arms/ma-lab/disc/<your image>
cd ~/Develop/rusty-arms/oracle
python3 -m oracle.replay examples/smoke.inputs --watch examples/smoke.watch \
    --out ~/Develop/rusty-arms/ma-lab/traces/smoke \
    --shots ~/Develop/rusty-arms/ma-lab/captures/smoke --repeat 2
```

It should end with "2 runs identical". If it fails, `dolphin.log` in the `--out` folder has Dolphin's output. Delete both output folders before trying again.
