#!/bin/bash
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run with sudo' >&2; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
python3 "$HERE/tools/upgrade_ui.py" "$@"
