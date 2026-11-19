#!/bin/bash
set -euo pipefail
# Raw Gadget owns the UDC; remove only the old prototype's gadget binding.
G=/sys/kernel/config/usb_gadget/skylanders
if [ -d "$G" ] && [ -s "$G/UDC" ]; then printf '\n' > "$G/UDC"; fi
modprobe dwc2
if ! modprobe raw_gadget; then
  echo 'This kernel lacks CONFIG_USB_RAW_GADGET. Use a Pi kernel with Raw Gadget support; see README.' >&2
  exit 1
fi
[ -c /dev/raw-gadget ] || { echo '/dev/raw-gadget missing' >&2; exit 1; }
shopt -s nullglob
udcs=(/sys/class/udc/*)
[ "${#udcs[@]}" -eq 1 ] || { echo 'Expected exactly one USB device controller' >&2; exit 1; }
if [ -n "$(cat "${udcs[0]}/function")" ]; then
  echo 'UDC is occupied by another gadget. Disable that gadget before starting Skylanders.' >&2
  exit 1
fi
echo "Raw Gadget available on ${udcs[0]##*/}; app will bind it."
