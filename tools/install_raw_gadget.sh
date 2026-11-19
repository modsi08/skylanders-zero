#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
KERNEL=$(uname -r)
MODULE=skylanders-raw-gadget
VERSION=0.1.8c6de544
if modinfo -k "$KERNEL" raw_gadget >/dev/null 2>&1; then
  echo "Raw Gadget already available for $KERNEL."
  exit 0
fi
if [ -r "/lib/modules/$KERNEL/modules.builtin" ] && grep -q '/raw_gadget.ko$' "/lib/modules/$KERNEL/modules.builtin"; then
  echo 'Raw Gadget is built into this kernel.'
  exit 0
fi
BUILD="/lib/modules/$KERNEL/build"
if [ ! -f "$BUILD/Makefile" ]; then
  echo "Installing headers for the running kernel: linux-headers-$KERNEL"
  if ! apt-get install -y "linux-headers-$KERNEL"; then
    echo "No matching headers for $KERNEL. No full-kernel build will be attempted." >&2
    echo 'Update Raspberry Pi OS using apt, reboot into the updated kernel, then rerun ./install.sh.' >&2
    exit 1
  fi
fi
[ -f "$BUILD/Makefile" ] || { echo "Matching kernel headers missing: $BUILD" >&2; exit 1; }
RELEASE=$(make -s -C "$BUILD" kernelrelease)
[ "$RELEASE" = "$KERNEL" ] || { echo "Headers are for $RELEASE, but running kernel is $KERNEL. Reboot or install matching headers." >&2; exit 1; }
(cd "$HERE/vendor/raw_gadget" && sha256sum -c SHA256SUMS)
SOURCE="/usr/src/$MODULE-$VERSION"
if [ ! -d "$SOURCE" ]; then
  mkdir -p "$SOURCE"
  cp "$HERE/vendor/raw_gadget/"{raw_gadget.c,raw_gadget.h,Makefile,dkms.conf} "$SOURCE/"
fi
if ! dkms status -m "$MODULE" -v "$VERSION" | grep -q .; then
  dkms add -m "$MODULE" -v "$VERSION"
fi
# Build one small module, not Linux. A single job keeps memory use low on Zero W.
MAKEFLAGS=-j1 dkms build -m "$MODULE" -v "$VERSION" -k "$KERNEL"
dkms install -m "$MODULE" -v "$VERSION" -k "$KERNEL"
depmod -a "$KERNEL"
modinfo -k "$KERNEL" raw_gadget >/dev/null
