# quaelis

Linux command line tool for the **Quaelis 50** indoor air quality monitor (Orium, ref. 11338),
which reports itself over USB as `HT512` (`10c4:82cd`). The vendor software only runs on
Windows; this tool does everything it does, from Linux, with the Python standard library only.

| Command | What it does |
|---|---|
| `status` | live readings (T, RH, CO2, HCHO, benzene eq., PM2.5), clock, alarm thresholds |
| `params` | stored recording parameters |
| `set-time` | set the monitor clock to this computer's clock |
| `download [-o file.csv]` | download the recorded measurements as CSV, with UTC timestamps |
| `set-params ...` | write recording parameters and alarm thresholds, start a new recording |

The USB protocol, reverse engineered from USB captures and from a static analysis of the Windows
software, is described in [PROTOCOL.md](PROTOCOL.md).

## Requirements

- Linux with the `hidraw` driver (any current distribution).
- Python 3.11 or later. No third party packages.

The monitor must be switched on (and past its warm-up) to appear on USB.

## Access without root

Create `/etc/udev/rules.d/70-quaelis.rules`:

```
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="82cd", MODE="0660", TAG+="uaccess"
```

then `sudo udevadm control --reload` and replug the monitor. The tool finds the right
`/dev/hidrawN` by itself; `--device /dev/hidrawN` overrides that.

## Usage

```
python3 quaelis.py status
python3 quaelis.py download -o measurements.csv
TZ=Europe/Madrid python3 quaelis.py set-time
```

### Time zones

The monitor displays local time, so `set-time` sends the time zone offset of the computer (or of
`TZ`). Like any wall clock, it needs `set-time` again after each daylight saving change.

Recorded data are not affected by this: the monitor stores the start of a recording in UTC, and
`download` writes a `time_utc` column in ISO 8601 (`2025-05-14T13:09:02Z`).

### Starting a recording

```
TZ=Europe/Madrid python3 quaelis.py set-params --name office --records 1440 --interval 1 --unit min \
    --threshold CO2=800,1200 --threshold PM2.5=15,50
```

Options not given keep their current value. Thresholds are `NAME=LOW,HIGH` in display units,
`NAME` one of `T`, `RH`, `CO2`, `HCHO`, `C6H6`, `PM2.5`; the low value is the yellow alarm, the
high value the red (and audible) alarm. Thresholds set this way replace those set with the
buttons.

**`set-params` erases the stored records.** It therefore downloads them first and saves them to
`quaelis_backup_<UTC time>.csv` in the current directory.

By default the recording starts immediately. With `--manual` the monitor waits for a short press
to the LEFT of the button, as the "Manual" option of the Windows software does (useful to start a
recording away from the computer).

## Calibration

CO2 calibration cannot be done over USB: neither the monitor nor the Windows software has a
command for it. The manual (p. 21) describes the button procedure:

1. Charge the battery fully and switch the monitor off.
2. Push the button to the right and, holding it there, also press its centre. Keep both until
   the screen, which lights up and cycles through colours, goes dark; then release.
3. The screen shows 400; press DOWN to show 401.
4. Place the monitor outdoors, in clean air (about 400 ppm CO2), for about 10 minutes, without
   touching it.
5. When the screen shows `00` or `01`, calibration is complete; press DOWN briefly to restart the
   warm-up. If it still shows `401`, calibration failed (the outdoor CO2 was not stable): switch
   off and repeat.

Only CO2 can be calibrated. If readings look frozen or wrong, the manual suggests switching the
monitor off for a few minutes, then leaving it on outdoors for 30 minutes.

## Tools

`tools/usbpcap_dump.py` decodes USBPcap captures (`.pcap`) taken on Windows while the vendor
software runs. `tools/re/` holds the small `pefile`/`capstone` scripts used for the static
analysis of the Windows executable (which is not distributed here).

## Licence

GNU Affero General Public License, version 3 or (at your option) any later version. See
[LICENSE](LICENSE).
