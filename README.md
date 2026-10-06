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

## First steps

Switch the monitor on, wait for the warm-up, plug it in, and ask for its live readings:

```
$ python3 quaelis.py status
clock        2026-10-07 00:12:07
records      17
T            23.6
RH           70.5
CO2          505
HCHO         0.0
C6H6         0.017
PM2.5        4
thresholds   {'T': (0.0, 70.0), 'RH': (10.0, 95.0), 'CO2': (600, 1200), 'HCHO': (0.01, 0.1), 'C6H6': (0.002, 0.03), 'PM2.5': (15, 50)}
flags        0003
recording    True
```

- `clock` is the monitor clock, in local time, as shown on its screen.
- `records` is the number of measurements stored so far; `recording True` means a recording is
  in progress.
- The six readings are in the units of the table below.
- `thresholds` are the (yellow, red) alarm levels of each reading.
- `flags` is not understood yet.

If the clock is wrong, set it (the monitor shows local time, so give your time zone):

```
$ TZ=Europe/Madrid python3 quaelis.py set-time
clock now 2026-10-07 00:14:30
```

| Column | Quantity | Unit |
|---|---|---|
| `T` | temperature | °C |
| `RH` | relative humidity | % |
| `CO2` | carbon dioxide | ppm |
| `HCHO` | formaldehyde | mg/m³ |
| `C6H6` | benzene equivalent (volatile organic compounds) | mg/m³ |
| `PM2.5` | fine particles | µg/m³ |

## Logging data

There are two ways, and they can be combined:

| | Recording on the monitor | Live logging from the computer |
|---|---|---|
| Computer needed during logging | no | yes, all the time |
| Maximum length | 10000 records | unlimited |
| Interval | 1 s to 255 h | any |
| Commands | `set-params`, then `download` | `examples/live_log.py` |

### Recording on the monitor

**1. Choose the interval and the number of records.** Their product is the length of the
recording:

| Interval | Records | Length |
|---|---|---|
| 10 s | 360 | 1 hour |
| 1 min | 1440 | 1 day |
| 5 min | 2016 | 1 week |
| 10 min | 4320 | 30 days |
| 1 h | 8760 | 1 year |

**2. Start the recording.** For one day, one record per minute:

```
TZ=Europe/Madrid python3 quaelis.py set-params --name office --interval 1 --unit min --records 1440
```

This first saves the records stored in the monitor to `quaelis_backup_<UTC time>.csv` in the
current directory (**`set-params` erases them**), then writes the parameters, starts the
recording and prints the parameters as read back. It also stores the time zone offset, hence
the `TZ`.

Options not given keep their current value, so repeating a recording with the same settings is
just `python3 quaelis.py set-params`. With `--manual` the monitor does not start at once, but
waits for a short press to the LEFT of its button (useful to start away from the computer).

**3. Check the progress** at any time, without disturbing the recording:

```
$ python3 quaelis.py params
address        1
serial
test_name
tz_offset_min  -120
total_records  100
interval       60
interval_unit  0
state          1
start          2026-10-06 21:55:34
records        17
thresholds     {'T': (0.0, 70.0), ...}
```

Here 17 of 100 records are taken, one every 60 `s` (`interval_unit` 0 = s, 1 = min, 2 = h).
`start` is in UTC; `tz_offset_min` is minus the offset of local time (`-120` is UTC+2).
When `records` reaches `total_records`, the monitor stops by itself.

**4. Download** (during or after the recording; it does not erase anything):

```
$ python3 quaelis.py download -o office.csv
$ head -4 office.csv
index,time_utc,T,RH,CO2,HCHO,C6H6,PM2.5
0,2026-10-06T21:55:34Z,23.6,70.3,501,0.0,0.017,4
1,2026-10-06T21:56:34Z,23.6,70.3,494,0.0,0.017,4
2,2026-10-06T21:57:34Z,23.6,70.4,497,0.0,0.017,4
```

Without `-o`, the CSV goes to the standard output. Timestamps are UTC, in ISO 8601, computed
from the start of the recording and the interval.

**What stops a recording:** `set-params` (it starts a new one), the Windows software, and,
according to the manual, pressing the monitor's buttons. `status`, `params`, `download` and
`set-time` do not stop it.

### Live logging from the computer

`examples/live_log.py` reads the live values every few seconds and writes them as CSV until you
press Ctrl+C. It does not touch the stored records or a recording in progress.

```
$ python3 examples/live_log.py 2 > live.csv
^C
$ cat live.csv
time_utc,T,RH,CO2,HCHO,C6H6,PM2.5
2026-10-06T22:12:51Z,23.5,70.5,499,0.0,0.017,4
2026-10-06T22:12:53Z,23.5,70.4,499,0.0,0.017,4
2026-10-06T22:12:55Z,23.5,70.5,499,0.0,0.017,4
```

The argument is the interval in seconds (default 10). For long sessions, run it under `nohup`,
`tmux` or a systemd service. The script is also a short example of using `quaelis.py` as a
Python module (`Quaelis().status()` returns a dictionary).

### Using the CSV files

Both kinds of file open directly in a spreadsheet, or in Python:

```python
import pandas as pd
df = pd.read_csv("office.csv", parse_dates=["time_utc"]).set_index("time_utc")
df["CO2"].plot()
```

## Alarm thresholds

The face on the screen turns yellow when a reading passes the low threshold and red (with a beep)
when it passes the high one. `set-params` can set them, as `NAME=LOW,HIGH` in the units above:

```
TZ=Europe/Madrid python3 quaelis.py set-params --threshold CO2=800,1200 --threshold PM2.5=15,50
```

`NAME` is one of `T`, `RH`, `CO2`, `HCHO`, `C6H6`, `PM2.5`. Thresholds set this way replace
those set with the buttons. Like any `set-params`, this starts a new recording (after saving
the old records).

## Time zones

The monitor displays local time, so `set-time` and `set-params` send the time zone offset of the
computer (or of `TZ`). Like any wall clock, it needs `set-time` again after each daylight saving
change. Recorded data are not affected by this: the monitor stores the start of a recording in
UTC.

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
