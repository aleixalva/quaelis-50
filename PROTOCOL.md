# Quaelis 50 USB protocol (reverse engineered)

Sources: `quaelis_50.pcap` (12 May 2025, read params, download 70 records, set params twice)
and `activate2.pcap` (14 May 2025, set params twice, set time once). Both are USBPcap captures
of the Windows software "Quaelis HT512". The captures are not distributed; decoder: `tools/usbpcap_dump.py`.

Verified on the real monitor (2026-10-06, Linux hidraw): reports 1, 2, 3/7, 4/8 and 5.

Static analysis of the Windows software (`HT512(EN).exe`, MFC C++, 32 bit, from the Google Drive
archive linked in the manual, SHA-256 of the zip `e609c0de...faafb`; never executed) confirmed the
command set below; see "What the Windows software can do". Scripts: `tools/re/`.

Status legend: **[sure]** seen and consistent in both captures; **[guess]** plausible, unverified.

## Transport

- USB VID `0x10c4` (Silicon Labs), PID `0x82cd`, product string `HT512`. Full speed HID.
- One interface, interrupt IN `0x81`, interrupt OUT `0x01`, 64 byte packets.
- Vendor page `0xff00` report descriptor (read in `activate2.pcap`):

| Report ID | Direction | Payload bytes | Meaning |
|---|---|---|---|
| 1 | Output | 6 | set clock |
| 2 | Output | 60 | write parameters (two frames) |
| 3 | Output | 1 | ask for parameters (answer in report 7); **stops a running recording** |
| 4 | Output | 2 | ask for record block *n* (answer in report 8) |
| 5 | Input | 32 (61 returned) | live status |
| 6 | Input | 60 | parameters (two frames), no command needed; read only fields 71..76 and 93 are zero |
| 7 | Input | 60 | parameters, after report 3 (two frames) |
| 8 | Input | 60 | record block |

- Commands are sent as interrupt OUT transfers (first byte = report ID). On Linux, `write()` to `/dev/hidrawN`.
- Answers are fetched with `GET_REPORT` (`bmRequestType 0xa1`, `bRequest 0x01`, `wValue 0x01<ID>`, `wLength 61`),
  i.e. Input report type. On Linux, `HIDIOCGINPUT` ioctl on hidraw, or `ctrl_transfer` with pyusb.
- Multi-byte integers are **big endian** everywhere except inside record blocks (little endian).

## Report 1: set clock **[verified live]**

```
01  68 24 95 f2  ff 88
    epoch UTC    tz offset, int16, minutes, Windows sign convention (UTC minus local; -120 = UTC+2)
```

The device then reports *local* time as if it were a Unix epoch (report 5 offset 1).
The manual says the software sends this automatically on connect / "SET TIME".

## Report 5: live status (61 bytes incl. ID) **[sure unless marked]**

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | report ID `05` |
| 1 | 4 | device clock, local time as epoch |
| 5 | 2 | number of records stored |
| 7 | 2 | T, (raw minus 400)/10 °C |
| 9 | 2 | RH, raw/10 % |
| 11 | 2 | CO2 ppm |
| 13 | 2 | HCHO, raw/100 mg/m³ (software range "0-2.50 mg/m3") |
| 15 | 2 | benzene eq., raw/1000 mg/m³ |
| 17 | 2 | PM2.5 µg/m³ |
| 19 | 24 | thresholds: T lo/hi, RH lo/hi, CO2 lo/hi, HCHO lo/hi, C6H6 lo/hi, PM lo/hi (same scales) |
| 43 | 2 | unknown, seen `00 03` [guess: flags, e.g. unit / alarm] |
| 45 | 1 | `01` while recording, `00` otherwise [verified live] |

## Parameter block (reports 2, 6, 7)

Two frames, `[ID] [frame 0|1] [59 bytes]`. Concatenating the two 59 byte payloads gives 118 bytes:

| Offset | Size | Field |
|---|---|---|
| 0 | 1 | address (`01`) |
| 1 | 10 | serial number, ASCII, NUL padded (software limit: "<= 10 Letters/Numbers") |
| 11 | 20 | test name, UTF-16LE, NUL padded (software limit: "<= 10 Characters"); 31..48 zero |
| 49 | 2 | tz offset (`ff 88`), same as report 1 |
| 51 | 2 | total records to record (`00 64` = 100; software limit 10000) |
| 53 | 1 | record interval value (`3c`, `1e`, `0a`, `32`) |
| 54 | 1 | interval unit: 0 = s, 1 = min, 2 = h (software list "Sec/Min/Hour") |
| 55 | 1 | recording state: `00` when written, `01` when read back after a write [guess] |
| 56 | 1 | temperature unit [guess] |
| 57 | 24 | thresholds, interleaved with the times below: T lo/hi, RH lo/hi at 57..64 |
| 65 | 1 | `00` |
| 66 | 4 | recording start, true UTC epoch (unlike the report 5 clock, which is local) |
| 70 | 1 | start mode when written: `01` Immediately, `00` Manual (wait for a short LEFT press); reads back `00` |
| 71 | 4 | read only; start + 9..13 s in the captures, which used Manual mode [guess: time of the button press] |
| 75 | 2 | records stored (read only; `00 00` when written) |
| 77 | 12 | CO2, HCHO, C6H6, PM lo/hi |
| 89 | 1 | read only, `14`, `10`, `1c` [unknown] |
| 95..117 | 23 | when written, uninitialised stack memory (`48 13 cf 01 ...`, `01` at 116); the software serialises only 95 bytes |

Writing report 2 (both frames) applies the alarm thresholds at once (report 5 shows them). With start mode
Immediately it also erases the stored records and starts the new recording; with Manual the new
recording starts only after a short LEFT press, and until then report 7 still returns the old block.
The software's "Set Param" dialog writes byte 70 from its Immediately/Manual radio button (OK handler
around 0x41b4e9) and then shows "The meter is recording data" or "To recording data,you must press the
button on the meter". Both captures used Manual.
Thresholds set here override those set with the buttons (manual, troubleshooting table).

Sending report 3 stops a running recording at once (status byte 45 drops to `00`, the count
freezes; verified live). Report 1 (set clock), report 4/8 (download), report 5 (status) and
GET_REPORT 6 do not. This is the "do not perform any actions on the software" warning in the
manual. `quaelis.py` therefore reads the parameters from report 6, and the record count from
report 5.

## Records (reports 4 and 8) **[sure]**

Send `04 00 nn` (block index nn, 16-bit BE), then GET_REPORT 8. Each block carries 5 records of 11 bytes
(55 bytes) plus 5 bytes of junk. 70 records = blocks 0x00..0x0d.

```
b0      T low 8 bits                T  = ((b2 & 0x0f) << 8 | b0), then (T-400)/10 °C
b1      RH low 8 bits               RH = ((b2 >> 4)  << 8 | b1) / 10 %
b2      high nibbles RH|T
b3-b4   CO2 ppm, LE
b5-b6   HCHO, LE, /100 mg/m³
b7-b8   C6H6 eq, LE, /1000 mg/m³
b9-b10  PM2.5 µg/m³, LE
```

Records carry no timestamp; time = start (param offset 66, true UTC) + i × interval.
`quaelis.py download` writes this as an ISO 8601 UTC column, `time_utc`, so daylight saving changes
do not affect stored data. The clock shown on the monitor is local time and needs `set-time` again
after each change.

## What the Windows software can do

The program calls `SLABHIDDevice.dll` from exactly five routines (around 0x414340..0x414e56):

| Routine | Sends | Reads |
|---|---|---|
| 0x414340 | nothing | report 5 (status) |
| 0x414650 | `03 00` (only when called with 0x80) | report 7, or report 6 when called with 1; two frames |
| 0x414980 | `04 hi lo` | report 8, retried up to 4 times while all bytes are `ff` |
| 0x414b40 | report 2, two frames of 59 bytes | nothing |
| 0x414cd0 | report 1 (clock) | nothing |

There is no other output report and no calibration command. The 16-bit fields that the
software byte swaps after reading the parameters are at offsets 49, 51, 57..64, 75..92, and the
32-bit ones at 66 and 71; nothing after offset 92 is a multi-byte field.

The executable does contain a dialog (resource 344) with "Calibration Param", "Read Sensor" and
"Default Calibration", but no code ever constructs it (the program only opens dialogs 100, 129,
326, 331 and 343) and its buttons have no message handlers. It is a leftover from another model
of the same family, like the noise, pressure and flow fields in the unused dialog 312.

## Not seen in any capture

- CO2 calibration. The manual describes it only as a button procedure (hold right, press centre,
  then DOWN to 401, about 10 minutes outdoors at 400 ppm). The Windows software has no USB
  command for it either (see above).
- Alarm sound on/off, °C/°F toggle (buttons; may be the unknown flag bytes).
