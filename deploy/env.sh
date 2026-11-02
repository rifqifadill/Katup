#!/usr/bin/env bash
KATUP_REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export KATUP_RUNTIME="${KATUP_REPO%/*}/runtime"
export KATUP_STATE="$KATUP_RUNTIME/state"
export KATUP_NOVNC="$KATUP_RUNTIME/novnc"
export PATH="$KATUP_RUNTIME/venv/bin:$KATUP_RUNTIME/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$KATUP_RUNTIME/root/usr/lib/x86_64-linux-gnu:$KATUP_RUNTIME/root/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export SUMO_HOME="$KATUP_RUNTIME/venv/lib/python3.10/site-packages/sumo"
export LIBGL_DRIVERS_PATH="$KATUP_RUNTIME/root/usr/lib/x86_64-linux-gnu/dri"
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export LP_NUM_THREADS=1
export DISPLAY=:95
export XAUTHORITY="$KATUP_STATE/Xauthority"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export XDG_DATA_DIRS="$KATUP_RUNTIME/root/usr/share:/usr/local/share:/usr/share"
export FONTCONFIG_PATH="$KATUP_RUNTIME/root/etc/fonts"
export KATUP_TELEMETRY="$KATUP_STATE/telemetry.json"
export PYTHONUNBUFFERED=1

export FONTCONFIG_FILE="$KATUP_STATE/fonts.conf"
export XDG_CACHE_HOME="$KATUP_RUNTIME/cache"
export MESA_SHADER_CACHE_DIR="$KATUP_RUNTIME/cache/mesa"
