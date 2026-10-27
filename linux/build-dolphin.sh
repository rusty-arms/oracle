#!/bin/sh
# Build the Python-scripting fork of Dolphin from source on Ubuntu 24.04 or Pop!_OS 24.04.
# The fork publishes Windows builds only. Its scripting module links against the system
# Python 3 (3.12 on these releases). See linux/README.md.
#
#   linux/build-dolphin.sh [DEST]     DEST defaults to ~/Develop/rusty-arms/dolphin-scripting
#
# Re-running it skips the clone and rebuilds. The result is
# DEST/build/Binaries/dolphin-emu, which you pass to the rig as --dolphin.
set -eu

TAG="${TAG:-scripting-preview4}"
DEST="${1:-$HOME/Develop/rusty-arms/dolphin-scripting}"

# Dolphin's documented Ubuntu build dependencies, plus Python headers and Ninja.
sudo apt-get install -y --no-install-recommends \
  ca-certificates git cmake ninja-build make gcc g++ pkg-config python3-dev \
  qt6-base-dev qt6-base-private-dev qt6-svg-dev \
  libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
  libxi-dev libxrandr-dev libudev-dev libevdev-dev libsfml-dev libminiupnpc-dev \
  libmbedtls-dev libcurl4-openssl-dev libhidapi-dev libsystemd-dev libbluetooth-dev \
  libasound2-dev libpulse-dev libpugixml-dev libbz2-dev libzstd-dev liblzo2-dev \
  libpng-dev libusb-1.0-0-dev gettext

if [ ! -d "$DEST/src/.git" ]; then
  git clone --depth 1 --branch "$TAG" --recurse-submodules --shallow-submodules \
    https://github.com/Felk/dolphin.git "$DEST/src"
fi

# LINUX_LOCAL_DEV keeps Dolphin's data files next to the binary, so nothing is installed
# system-wide and the normal Dolphin on this PC is untouched.
cmake -S "$DEST/src" -B "$DEST/build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DLINUX_LOCAL_DEV=ON
cmake --build "$DEST/build"

# A LINUX_LOCAL_DEV build looks for its Sys data folder next to the binary, but on Linux the
# build doesn't copy it there. Without it Dolphin can't load its icons and crashes at start.
ln -sfn "$DEST/src/Data/Sys" "$DEST/build/Binaries/Sys"

echo
echo "Built: $DEST/build/Binaries/dolphin-emu"
echo "Use it with: export ORACLE_DOLPHIN=$DEST/build/Binaries/dolphin-emu"
