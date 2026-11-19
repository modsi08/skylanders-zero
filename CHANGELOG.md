# Changelog

## 0.7.0

- Source package prepared for GitHub; explicit dump/runtime exclusions and CI.
- Installer self-elevates, checks Zero hardware, preserves user data, configures
  peripheral boot settings and enables systemd startup.
- Missing Raw Gadget can be built from pinned vendored source with exact matching
  headers and DKMS, without a full kernel build.
- Documented power isolation, Zero W test platform and unverified game/features.

## 0.6

- Separate 16 saved choices from the one activated figure; wait for removal before
  loading the next choice; persist choices across reboot.

## 0.5

- Moved metadata lookup into the browser; explicit one-time header identification.
- Restored the pre-catalogue status path to reduce portal-process work.

## 0.4 / 0.4.1

- Introduced local figure catalogue. Both builds had confirmed loading-loop
  regressions on the tested PS3. The lock-only fix in 0.4.1 was insufficient.

## Earlier baseline

- Linux Raw Gadget bridge, figure save persistence, web uploads and mode hooks.
- Baseline Giants gameplay confirmed on Zero W + PS3 Slim with isolated host power.
