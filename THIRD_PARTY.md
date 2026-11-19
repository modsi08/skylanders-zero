# Source and licensing

The application is distributed under GPL-3.0-or-later; see COPYING.
The separately bundled fallback kernel module retains its own GPL-2.0 license.
Descriptor bytes and portal startup/status/audio behavior are adapted from:

- Alexander Shaffer, SkylandersPortalEmulator
- https://github.com/AlexanderShaffer/SkylandersPortalEmulator
- Commit: a2a9a10408598e73a1f5a5dac60e0c86df098853
- Original copyright: Copyright (C) 2026 Alexander Shaffer
- Original license: GPL-3.0-or-later
- Consulted files: pico/config/UsbDescriptors.cpp, pico/src/Main.cpp,
  gui/src/PortalEmulator.cpp, common/Common.hpp.

The upstream descriptor source says it captured the device, configuration,
HID and string descriptors from a PS3 Traptanium portal. Its README reports
compatibility with all six games on PS3. That report does not validate this
Linux port. The protocol adaptation, bounds checks, durability, web UI and
Raw Gadget bridge must be tested separately.

Flask and Werkzeug are installed as dependencies, not bundled. Their respective
licenses remain applicable. No copyrighted character dumps or artwork are included.

Kernel documentation: https://docs.kernel.org/usb/raw-gadget.html
Kernel HID function: https://github.com/torvalds/linux/blob/master/drivers/usb/gadget/function/f_hid.c
Raw Gadget UDC documentation: https://github.com/xairy/raw-gadget

## Offline identification catalogue (v0.4)

`catalog/figures.json` adapts the identity/type/element table from Dolphin:
Copyright 2022 Dolphin Emulator Project; GPL-2.0-or-later (used here under GPLv3).
Source: https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/IOS/USB/Emulated/Skylanders/Skylander.cpp

Additional character/variant identity facts, including Imaginators, were compiled
from Texthead1 / Portal-To-Unity and contributors:
https://github.com/Texthead1/Skylander-IDs
Original contributor credits: Fershock, Dead-Donutz, BoomBringer, jackthebloke,
Scarlett/eclipse_kyo, Blennz Fire, Whacky Zacky/Quazzazza and Djdigby.
No figure dumps or artwork from those projects are included.

Header format reference: NefariousTechSupport / Runes,
https://github.com/NefariousTechSupport/Runes/blob/master/Docs/SkylanderFormat.md

The JSON source manifest records retrieval date and SHA-256 hashes of the two
input snapshots. Local corrections include consistent Astroblast Light element,
Gill Runt sidekick/mini metadata, and SuperCharger/Sensei/crystal classifications.
Community source catalogues may contain mistakes; not every unusual ID pair or
unreleased entry has been verified with a physical figure or on a real PS3.

## Bundled fallback kernel module (0.7.0)

The unmodified raw_gadget.c and raw_gadget.h under vendor/raw_gadget come from
https://github.com/xairy/raw-gadget at commit
8c6de5448ef2b8e4fc37021208c86c3f4dd579dc.
Copyright (c) 2020 Google, Inc.; author Andrey Konovalov.
The C driver is GPL-2.0-only, and the UAPI header is GPL-2.0 WITH Linux-syscall-note.
These files are built as a separate Linux kernel module, not linked into the
userspace application. See LICENSES/GPL-2.0.txt and LICENSES/Linux-syscall-note.txt.
License texts were obtained from the Linux kernel's LICENSES directory. The local
module Makefile, DKMS config and install helper have their own SPDX notices.
