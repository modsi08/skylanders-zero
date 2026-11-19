# Vendored Raw Gadget fallback module

Upstream: https://github.com/xairy/raw-gadget
Commit: 8c6de5448ef2b8e4fc37021208c86c3f4dd579dc
Retrieved: 2026-11-19
Files copied unchanged: raw_gadget/raw_gadget.c and raw_gadget/raw_gadget.h.
Copyright (c) 2020 Google, Inc.; author Andrey Konovalov.

The driver is GPL-2.0-only. Its UAPI header is GPL-2.0 WITH Linux-syscall-note.
The license and exception texts are in ../../LICENSES. This separately built
kernel module is an aggregate alongside the GPLv3 userspace app; it is not linked
into the app. The Makefile and DKMS configuration are local packaging additions.
SHA256SUMS pins these files; the installer verifies them before fallback builds.

Only used when the running kernel lacks raw_gadget. Exact matching kernel headers
and the kernel's USB gadget API/symbols are required. DKMS rebuilds just this module;
it does not build an entire kernel. Compatibility must be retested after Linux API
changes. Installer/helper tests run locally; the vendored fallback's real ARM kernel
build has not been executed in the source-packaging environment.
