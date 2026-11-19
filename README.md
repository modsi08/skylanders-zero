# Skylanders Zero

A Raspberry Pi USB portal emulator for a real PlayStation 3, with a local web UI,
figure identification and a saved selection of up to 16 figures.

**Hardware tested:** Raspberry Pi **Zero W Rev 1.1**, Raspberry Pi OS 13 (32-bit),
PS3 Slim **CECH-2004B**. Baseline portal operation was confirmed in **Skylanders:
Giants**, using a separate Pi power supply and isolated USB power from the PS3.
The current installer and latest UI changes have local test coverage and still
need fresh end-to-end hardware confirmation. Zero 2 W is an intended platform,
not a confirmed test result. This Linux project does **not** run on a Pico W.

No figure dumps, game files, keys, character artwork or console firmware are
included. Supply your own 1024-byte figure backups.

## Hardware and USB power — read this first

Use a data-capable USB-A to micro-USB cable and a separate supply for the Pi.

| Connection | Where it goes |
| --- | --- |
| Separate suitable 5 V micro-USB supply | Pi **PWR IN** socket |
| Either front PS3 USB port | **USB power blocker**, then the data cable |
| Data cable's micro-USB plug | Pi **USB** socket (not PWR IN) |

**The PS3 cable must have its +5 V / VBUS conductor disconnected. Keep D+, D−
and ground connected.** The Zero W's USB power inputs share the 5 V rail; an
ordinary cable to the console plus an external supply can backfeed between them.
A power blocker disconnects VBUS while passing USB data. A **data blocker** does
the opposite and will not work for this purpose.

There are two ways to isolate power:

1. Use a USB 2.0 **power blocker** (for example PortaPow USB Power Blocker).
   Plug it into the PS3, then connect the data cable through it to Pi USB.
2. Modify a dedicated data cable: unplug everything, identify the +5 V/VBUS
   conductor with a meter, cut it at one point, and insulate both cut ends
   separately. Do not rely solely on wire colour. Verify that VBUS is interrupted,
   D+, D− and ground remain connected, and no conductors are shorted.

Keep the ground conductor: it is the reference for USB data. Most ordinary USB
Y-cables still connect the two power sources and are not a substitute. Power the
Pi through PWR IN, let it boot, then connect the isolated data cable to the PS3.
The power blocker resolved the original PS3-triggered Pi resets in the tested
setup; it is not proof that every cable/console combination will behave identically.

References: [Raspberry Pi's Zero W gadget wiring guide](https://magazine.raspberrypi.com/articles/pi-zero-w-smart-usb-flash-drive)
and [PortaPow's power blocker description](https://portablepowersupplies.co.uk/product/usb-power-blocker).

## Quick installation

Start with Raspberry Pi OS Lite, configure Wi-Fi and SSH, and connect the wiring
above. An internet connection is needed for apt and Python dependencies during
installation. The running portal and figure catalogue work offline afterward.

Download this source ZIP and extract it, or clone your copy of the repository.
Open a terminal in the project directory and run:

```bash
./install.sh
```

The script requests sudo itself. If your ZIP extractor did not preserve executable
permissions, use `bash install.sh` or `chmod +x install.sh` first.

The installer:

- Checks for a Raspberry Pi Zero family board and Raspberry Pi OS/Debian.
- Installs Python, build tools, kmod, DKMS and ALSA utilities.
- Reuses `raw_gadget` if the running kernel already provides it. Otherwise it
  installs **matching headers for the running kernel** and builds the bundled,
  pinned Raw Gadget module using DKMS. It does not build a full Linux kernel.
- Backs up replaced application/configuration files under
  `/var/backups/skylanders-zero/` and preserves existing figures, saves,
  `selection.json`, `device-mode.json` and `/etc/skylanders-zero.env`.
- Configures `dtoverlay=dwc2,dr_mode=peripheral` and boot loading of `dwc2` and
  `raw_gadget`, builds the USB bridge and creates a Python virtual environment.
- Enables `skylanders-web.service` for automatic startup. It does not reboot
  automatically. If boot configuration changed, finish with:

```bash
sudo reboot
```

After reboot, open **http://PI-IP:8080**. Find the address with `hostname -I`.

If exact kernel headers are no longer available from apt, installation stops
with an explanation. Update Raspberry Pi OS using its normal apt update/upgrade
process, reboot into that kernel, then rerun `./install.sh`. Do not compile with
headers from a different kernel. DKMS attempts rebuilding for later kernels when
matching headers are installed; future kernel/API compatibility is not guaranteed.
An older Pi Zero W may take a few minutes to build the small module.

### Installer options

```bash
./install.sh --help
./install.sh --dry-run    # Print the plan, change nothing; can run on a development PC
./install.sh --check      # Read-only hardware/module/service diagnostics
./install.sh --no-start   # Install/enable startup, leave the service stopped for now
```

Custom boot `os_prefix` or alternate `cmdline` configurations need manual review.
Only known `usb-manual-test.conf` blocks from troubleshooting are removed, with a
backup. Arbitrary modprobe rules and other gadget services are not silently disabled.

## Use the web UI

1. Upload a 1024-byte `.bin`, `.dump`, `.dmp` or `.sky` backup under **My Skylanders**.
2. Click **Identify figures** to identify existing files. New uploads can be
   identified from their headers directly in your browser. Names, elements,
   figure types, editions and filters are looked up in the browser's offline
   catalogue of 718 character/variant pairs. Unknown entries are labelled unknown.
3. Click **Add to selection**. This fills one of the 16 upper tiles without
   announcing the figure to the console.
4. Click **Activate** on that tile. The previous figure is removed first; the new
   figure is loaded only when removal has completed. This flow activates one
   figure at a time, suitable for the tested single-character Giants use case.
5. **Deactivate** empties the virtual portal. **Remove** clears a selection tile
   without deleting its dump. **Delete** in the library deletes the dump.

Uploads and game writes are saved to the SD card. Selection choices survive
reboot; the active figure is not automatically reloaded. The first figure load
also creates a `.original` backup. Keep your own separate backups. Shut down with
`sudo poweroff` before disconnecting the Pi supply.

The single-figure UI does not currently provide two-player or multi-piece SWAP
Force / accessory staging. The lower-level `/api/load` endpoint retains support
for explicitly managed portal slots; it is an advanced interface. A full
per-game compatibility matrix is not supplied. Edition game means the edition's
release era, not a guarantee of compatibility in all earlier or later games.

## Game status

| PS3 game | Status |
| --- | --- |
| Skylanders: Giants | Baseline portal tested by the owner on the hardware listed above |
| Spyro's Adventure | Target; unverified on this Linux implementation |
| SWAP Force | Target; unverified; normal swapping needs separately managed top/bottom halves |
| Trap Team | Target; unverified; audio playback requires separate validation |
| SuperChargers | Target; unverified |
| Imaginators | Target; unverified |

The USB identity/protocol is based on an upstream PS3 Traptanium portal project.
Upstream compatibility reports do not validate this Linux port or its current UI.

## Updating an existing working portal

If you already have a working USB setup and only want the web UI changes, extract
new source into a separate directory and run:

```bash
sudo bash upgrade-ui.sh
```

This backs up the installed UI, preserves the installed status/USB startup code,
and restarts the web service if it was running. It does not change boot settings,
kernel modules or systemd units. Wait until the game is not saving before updating.
Refresh the browser afterward; close tabs showing older UI versions.

For a full installation update (including installer/module/service changes), run
`./install.sh` again. Existing dumps and configuration are preserved. Read the
installer's reboot message rather than disconnecting power immediately.

## Configuration and limitations

Optional settings are documented in `config.env.example` and installed once as
`/etc/skylanders-zero.env`. Restart the service after editing that file.

The UI is for a **trusted local network**. It binds port 8080 on all interfaces
and uses Flask's development server. The application runs as root to manage the
USB gadget. Do not expose it directly to the internet. Set `SKYLANDERS_TOKEN`
and open `http://PI-IP:8080/?token=YOUR_TOKEN` if write authentication is needed.

Optional audio uses `SKYLANDERS_AUDIO_DEVICE`; see [audio notes](docs/AUDIO.md).
Controller mode is an integration hook only: no 8BitDo Pro 2 backend is included.
See [controller notes](docs/CONTROLLERS.md).

## Troubleshooting

```bash
./install.sh --check
sudo systemctl status skylanders-web --no-pager
sudo journalctl -u skylanders-web -n 60 --no-pager
sudo /opt/skylanders-zero/diagnose.sh
```

- **Pi resets when connecting to PS3:** check the power isolation and supply first.
  Do not connect two ordinary powered cables and assume they are isolated.
- **`raw_gadget` not found:** rerun the installer under the currently running
  kernel. It needs exact matching headers if the module must be built.
- **Operation not permitted when loading a module:** inspect `/proc/cmdline` for
  `module_blacklist=` and review `/etc/modprobe.d`. Reboot after removing a
  kernel-command-line block. The installer removes its known troubleshooting blocks.
- **UDC missing:** check peripheral overlay, reboot, then list `/sys/class/udc`.
  Zero W normally uses `20980000.usb`; the app discovers it rather than hardcoding it.
- **UDC occupied:** another gadget owns USB. Stop that gadget before Portal mode.
- **`not attached`:** check the Pi USB socket, PS3 power, blocker orientation and
  a verified data cable. A lit Pi does not prove a data connection.
- **`configured`:** the host configured USB; this alone does not confirm gameplay.
- **Too many figures:** use Activate in the selection UI; close old UI tabs which
  could still use the direct multi-slot Load API.
- **Game loading loop after an update:** preserve logs and restore the backed-up
  working code. v0.4 and v0.4.1 had confirmed regressions; the current design keeps
  catalogue matching out of the portal process. Report the exact version,
  kernel, figure IDs and logs. See [validation](VALIDATION.md).

## Development and GitHub packaging

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
node tests/test_browser_catalogue.cjs
bash -n install.sh setup-gadget.sh upgrade-ui.sh tools/install_raw_gadget.sh
cc -O2 -Wall -Wextra -Werror -pthread usb/raw_bridge.c -o /tmp/raw-bridge
python tools/package_release.py
```

The last command creates `dist/skylanders-zero-0.7.0-source.zip` using an explicit
source allowlist. It excludes all dump extensions, `.original` backups, runtime
state, secrets, caches and compiled binaries. `.gitignore` prevents accidental
commits of these files too. CI runs source/unit checks and produces a source ZIP;
it does not simulate real PS3 hardware or build an ARM kernel module.

To publish, upload the **extracted project contents** to your GitHub repository
(or commit/push them with git), including `.github`, `.gitignore` and
`.gitattributes`. Do not commit your installed `/opt/skylanders-zero` directory.
Use the generated ZIP as a release attachment. Choose your repository URL before
adding clone/download links; this package does not assume a GitHub owner or URL.

## License and credits

Application: **GPL-3.0-or-later**, see [COPYING](COPYING).
The separately bundled Raw Gadget kernel module is **GPL-2.0-only**; its UAPI
header has the Linux syscall exception. See [THIRD_PARTY.md](THIRD_PARTY.md),
[LICENSES](LICENSES), and the vendored source notices for details.

Skylanders and associated characters/trademarks belong to their respective owners.
This project is unofficial and is not affiliated with Activision or Sony.
