#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
TARGET=/opt/skylanders-zero
KERNEL=$(uname -r)
MODE=${1:-install}
case "$MODE" in
  --help|-h)
    cat <<'HELP'
Usage: ./install.sh [--check | --dry-run | --no-start]
Default: install dependencies, build missing raw_gadget, configure boot, enable service.
Automatically requests sudo when necessary. A reboot is needed after boot changes.
Wire separate power to PWR IN and block ONLY host +5V on the USB data cable first.
--check: read-only module/hardware checks. --dry-run: print plan; no changes.
--no-start: install/enable service, but do not start it during this invocation.
HELP
    exit 0;;
  --dry-run)
    cat <<'PLAN'
No changes made. Installation plan:
1. Require a Raspberry Pi Zero family board running Raspberry Pi OS/Debian.
2. Install Python/Flask build dependencies, kmod, DKMS and ALSA tools.
3. Reuse raw_gadget if present; otherwise install exact running-kernel headers
   and build the bundled, pinned Raw Gadget module through DKMS (not a full kernel).
4. Back up existing code/config; preserve figures, selection, mode and environment.
5. Configure dwc2 peripheral mode and boot module loading; remove only known
   troubleshooting blocks for dwc2/raw_gadget; refresh initramfs where available.
6. Install source and USB bridge under /opt/skylanders-zero, create Python venv,
   install/enable systemd service. Start if boot config is already effective;
   otherwise leave stopped until the user reboots.
7. Run read-only checks. No automatic reboot and no automatic kernel upgrade.
PLAN
    exit 0;;
  --check)
    printf 'Kernel: %s\n' "$KERNEL"
    printf 'Model: '; tr -d '\000' </proc/device-tree/model 2>/dev/null || true
    printf '\nUSB modules:\n'
    modinfo dwc2 2>&1 | head -n 8 || true
    modinfo raw_gadget 2>&1 | head -n 8 || true
    printf '\nUDC:\n'; ls /sys/class/udc 2>/dev/null || true
    printf '\nRaw Gadget device:\n'; ls -l /dev/raw-gadget 2>/dev/null || true
    printf '\nService:\n'; systemctl is-enabled skylanders-web 2>/dev/null || true
    exit 0;;
  install|--no-start) ;;
  *) echo "Unknown option: $MODE (use --help)" >&2; exit 2;;
esac
if [ "$(id -u)" -ne 0 ]; then exec sudo /bin/bash "$HERE/install.sh" "$@"; fi
MODEL=$(tr -d '\000' </proc/device-tree/model 2>/dev/null || true)
case "$MODEL" in *'Raspberry Pi Zero'*) ;; *) echo "Unsupported model: ${MODEL:-unknown}. This installer is for Linux-based Pi Zero boards, not Pico W." >&2; exit 1;; esac
[ -f /etc/os-release ] || { echo 'Cannot detect operating system' >&2; exit 1; }
# shellcheck disable=SC1091
. /etc/os-release
case "${ID:-}" in raspbian|debian) ;; *) echo 'Use Raspberry Pi OS (Debian/Raspbian based).' >&2; exit 1;; esac
BOOT=/boot/firmware
[ -f "$BOOT/config.txt" ] || BOOT=/boot
[ -f "$BOOT/config.txt" ] || { echo 'Missing boot config.txt' >&2; exit 1; }
# Never guess which command line / overlay a custom os_prefix boot uses.
if grep -Eq '^[[:space:]]*os_prefix=.+' "$BOOT/config.txt" || grep -E '^[[:space:]]*cmdline=' "$BOOT/config.txt" | grep -qvE '^[[:space:]]*cmdline=cmdline.txt[[:space:]]*$'; then
  echo 'Custom boot prefix/command line detected. Restore standard Raspberry Pi OS boot configuration first.' >&2; exit 1
fi
for item in app.py VERSION requirements.txt config.env.example CHANGELOG.md tools/install_raw_gadget.sh tools/configure_boot.py vendor/raw_gadget/SHA256SUMS systemd/skylanders-web.service; do
  [ -f "$HERE/$item" ] || { echo "Incomplete source package: $item missing" >&2; exit 1; }
done
printf '\nModel: %s\nKernel: %s\n' "$MODEL" "$KERNEL"
echo 'Wiring required: power supply -> PWR IN; PS3 -> USB power blocker -> data cable -> USB.'
echo 'Block only +5V/VBUS on the console cable; keep D+, D- and ground connected.'
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-pip build-essential linux-libc-dev alsa-utils dkms kmod
bash "$HERE/tools/install_raw_gadget.sh"
# Build prerequisites before stopping the existing working portal.
STAGE=$(mktemp -d /tmp/skylanders-install.XXXXXX)
trap 'rm -rf "$STAGE"' EXIT
cc -O2 -Wall -Wextra -Werror -pthread "$HERE/usb/raw_bridge.c" -o "$STAGE/raw-bridge"
BACKUP="/var/backups/skylanders-zero/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$BACKUP"
if [ -d "$TARGET" ]; then
  tar -C "$TARGET" --exclude='./figures' --exclude='./.venv' --exclude='./__pycache__' -cf "$BACKUP/application.tar" .
fi
for file in /etc/systemd/system/skylanders-web.service /etc/systemd/system/skylanders-gadget.service /etc/skylanders-zero.env; do
  if [ -f "$file" ]; then cp --parents -a "$file" "$BACKUP/"; fi
done
python3 "$HERE/tools/configure_boot.py" --boot "$BOOT" --backup "$BACKUP" --validate-only
systemctl stop skylanders-web.service skylanders-gadget.service 2>/dev/null || true
python3 "$HERE/tools/configure_boot.py" --boot "$BOOT" --backup "$BACKUP"
if [ -e "$BACKUP/reboot-required" ] && command -v update-initramfs >/dev/null; then
  update-initramfs -u -k "$KERNEL"
fi
mkdir -p "$TARGET/figures"
# Explicit source allowlist: no user dumps, virtualenv, secrets or saved mode/selection copied.
if [ "$HERE" != "$TARGET" ]; then
  for item in app.py audio.py portal.py transport.py modes.py catalogue.py identity_api.py selection.py \
      requirements.txt setup-gadget.sh diagnose.sh install.sh upgrade-ui.sh VERSION README.md COPYING \
      THIRD_PARTY.md VALIDATION.md CHANGELOG.md config.env.example catalog templates static usb tools systemd docs LICENSES vendor; do
    cp -a "$HERE/$item" "$TARGET/"
  done
fi
install -m 755 "$STAGE/raw-bridge" "$TARGET/usb/raw-bridge"
python3 -m venv "$TARGET/.venv"
"$TARGET/.venv/bin/pip" install -r "$TARGET/requirements.txt"
chmod +x "$TARGET/setup-gadget.sh" "$TARGET/diagnose.sh"
if [ ! -e /etc/skylanders-zero.env ]; then install -m 600 "$HERE/config.env.example" /etc/skylanders-zero.env; fi
for unit in skylanders-gadget skylanders-web; do
  sed "s|@@ROOT@@|$TARGET|g" "$HERE/systemd/$unit.service" > "/etc/systemd/system/$unit.service"
done
systemctl daemon-reload
systemctl disable skylanders-gadget.service 2>/dev/null || true
systemctl enable skylanders-web.service
# Boot parameters still active in memory may retain the old blacklist until reboot.
if grep -Eq 'module_blacklist=[^ ]*(dwc2|raw_gadget)' /proc/cmdline || [ ! -d /sys/class/udc ] || ! ls /sys/class/udc/* >/dev/null 2>&1; then
  touch "$BACKUP/reboot-required"
fi
if [ -e "$BACKUP/reboot-required" ]; then
  echo 'Installation complete. Boot configuration changed: run sudo reboot when ready.'
elif [ "$MODE" = '--no-start' ]; then
  echo 'Installation complete; automatic startup enabled. Start later: sudo systemctl start skylanders-web'
else
  systemctl start skylanders-web.service
  echo 'Installation complete; web service started.'
fi
echo "Backup: $BACKUP"
echo 'After reboot: http://<PI-IP>:8080 ; check logs: sudo journalctl -u skylanders-web -n 40 --no-pager'
echo 'Kernel changes need matching raw_gadget support; rerun ./install.sh if a later kernel cannot load it.'

bash "$TARGET/install.sh" --check
