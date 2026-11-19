#!/bin/bash
set -u
printf 'Kernel: '; uname -a
printf '\nRaw Gadget module:\n'; modinfo raw_gadget 2>&1 | head -n 12
printf '\nDevice node:\n'; ls -l /dev/raw-gadget 2>&1
printf '\nUDC:\n'; ls -l /sys/class/udc 2>&1
for path in /sys/class/udc/*; do
  [ -d "$path" ] || continue
  printf '\n%s\n' "$path"
  for field in state function maximum_speed current_speed; do printf '%s: ' "$field"; cat "$path/$field" 2>/dev/null || true; done
done
printf '\nServices:\n'; systemctl --no-pager --full status skylanders-gadget skylanders-web 2>&1
printf '\nRecent logs (no dump files included):\n'; journalctl --no-pager -u skylanders-gadget -u skylanders-web -n 120 2>&1
printf '\nApp state:\n'; curl --max-time 3 -s http://127.0.0.1:8080/api/state
printf '\n'
