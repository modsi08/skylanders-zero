# Validation — 0.7.0, 2026-11-19

## Hardware evidence

- Owner confirmed Raspberry Pi Zero W Rev 1.1 (not Pico W), Raspberry Pi OS 13
  32-bit and PS3 Slim CECH-2004B.
- Original portal operation in Skylanders: Giants was confirmed after isolating
  console +5 V and providing separate power to PWR IN.
- Metadata builds 0.4 and 0.4.1 caused loading loops; returning to the earlier
  app resolved the loop. No definitive console-level timing root cause was proved.
- Latest UI/selection and 0.7 installer require fresh end-to-end confirmation.
  Other PS3 games and Zero 2 W have not been validated here.

## Local release checks

- 54 Python tests passed: protocol, persistence, modes, catalogue, header API,
  saved selection, concurrent single-figure switching, updater and installation helpers.
- Boot configuration tests cover idempotency, preservation of other model settings,
  targeted blacklist removal, backups and refusal to erase custom modprobe rules.
- Module-helper tests exercise existing-module reuse and clean failure for unavailable
  matching headers, using stub commands; no actual apt or kernel changes in tests.
- The bundled module source/checksums were verified. Its real ARM/DKMS build was
  not run in this environment because no matching Pi kernel headers/hardware exist.
- C userspace bridge compiles with -Wall -Wextra -Werror; shell syntax passes.
- Node tests pass for all 718 catalogue ID pairs and unknown/header cases.
- Source packaging tests exclude dumps (including mixed-case extensions), secrets,
  saved state and binaries, and preserve executable install.sh permissions.
- Git ignore checks verify dump/runtime exclusions. A fresh extracted source ZIP
  was used for the final test pass.

GitHub Actions repeats source tests and source ZIP packaging. It does not prove
USB enumeration or gameplay on a console, or kernel module compatibility with
all future Raspberry Pi OS kernels. No precompiled modules are distributed.
