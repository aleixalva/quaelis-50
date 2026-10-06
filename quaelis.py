#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Talk to a Quaelis 50 (HT512, USB 10c4:82cd) air quality monitor through Linux hidraw.

Usage:
    quaelis.py status            live readings and thresholds
    quaelis.py params            stored recording parameters
    quaelis.py set-time          set the monitor clock to this computer's clock
    quaelis.py download [-o f]   download recorded measurements as CSV, with UTC timestamps
    quaelis.py set-params ...    write parameters and start a new recording (erases the stored
                                 records, so it first saves them to quaelis_backup_<UTC>.csv)

The monitor displays local time: run set-time with TZ set (e.g. TZ=Europe/Madrid), and again
after each daylight saving change. Download timestamps are UTC, so they are not affected.

See PROTOCOL.md for the byte layouts.
"""
import argparse
import csv
import datetime as dt
import fcntl
import glob
import os
import struct
import sys
import time

VID, PID = 0x10C4, 0x82CD
REPORT_LEN = 61  # report ID + 60 bytes, as the Windows software requests
RECORD_LEN = 11
RECORDS_PER_BLOCK = 5
PARAM_LEN = 95  # bytes of the parameter block the Windows software serialises; the rest is junk
FRAME_LEN = 59  # parameter bytes per report 2/6/7 frame
UNIT_SECONDS = {0: 1, 1: 60, 2: 3600}  # interval unit byte: Sec/Min/Hour


def find_hidraw():
    for path in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        with open(os.path.join(path, "device/uevent")) as f:
            if f"HID_ID=0003:{VID:08X}:{PID:08X}" in f.read():
                return "/dev/" + os.path.basename(path)
    raise SystemExit("Quaelis 50 not found (is it switched on and plugged in?)")


def HIDIOCGINPUT(length):
    return (3 << 30) | (length << 16) | (ord("H") << 8) | 0x0A


class Quaelis:
    def __init__(self, path=None):
        self.fd = os.open(path or find_hidraw(), os.O_RDWR)

    def close(self):
        os.close(self.fd)

    def send(self, data):
        os.write(self.fd, bytes(data))

    def get(self, report_id):
        buf = bytearray(REPORT_LEN)
        buf[0] = report_id
        fcntl.ioctl(self.fd, HIDIOCGINPUT(REPORT_LEN), buf)
        return bytes(buf)

    def status(self):
        return decode_status(self.get(5))

    def params(self):
        return decode_params(self.raw_params())

    def raw_params(self):
        self.send([3, 0])
        time.sleep(0.01)
        frames = sorted([self.get(7), self.get(7)], key=lambda r: r[1])
        assert [r[1] for r in frames] == [0, 1], "unexpected parameter frames"
        return frames[0][2:] + frames[1][2:]

    def set_time(self, when=None):
        when = when or time.time()
        local = dt.datetime.fromtimestamp(when).astimezone()
        offset = -int(local.utcoffset().total_seconds() // 60)
        self.send(struct.pack(">BIh", 1, int(when), offset))

    def set_params(self, raw):
        """raw: parameter block as returned by encode_params. Starts a new recording."""
        for frame in range(2):
            self.send(bytes([2, frame]) + raw[frame * FRAME_LEN:(frame + 1) * FRAME_LEN])
            time.sleep(0.01)

    def download(self, count):
        records = []
        for block in range((count + RECORDS_PER_BLOCK - 1) // RECORDS_PER_BLOCK):
            self.send(struct.pack(">BH", 4, block))
            time.sleep(0.01)
            records += decode_block(self.get(8))
        return records[:count]


def u16(b, i):
    return b[i] << 8 | b[i + 1]


def thresholds(b, i):
    """12 big-endian values: T lo/hi, RH lo/hi, CO2, HCHO, C6H6, PM2.5 lo/hi."""
    v = [u16(b, i + 2 * k) for k in range(12)]
    return {
        "T": ((v[0] - 400) / 10, (v[1] - 400) / 10),
        "RH": (v[2] / 10, v[3] / 10),
        "CO2": (v[4], v[5]),
        "HCHO": (v[6] / 100, v[7] / 100),
        "C6H6": (v[8] / 1000, v[9] / 1000),
        "PM2.5": (v[10], v[11]),
    }


def decode_status(r):
    assert r[0] == 5, r[0]
    return {
        "clock": dt.datetime.fromtimestamp(struct.unpack_from(">I", r, 1)[0], dt.UTC).replace(tzinfo=None),
        "records": u16(r, 5),
        "T": (u16(r, 7) - 400) / 10,
        "RH": u16(r, 9) / 10,
        "CO2": u16(r, 11),
        "HCHO": u16(r, 13) / 100,
        "C6H6": u16(r, 15) / 1000,
        "PM2.5": u16(r, 17),
        "thresholds": thresholds(r, 19),
        "flags": r[43:45].hex(),
    }


def decode_params(p):
    """p: the two 59-byte frame payloads concatenated (118 bytes)."""
    th = thresholds(p[57:65] + p[77:93], 0)
    return {
        "address": p[0],
        "serial": p[1:11].split(b"\0")[0].decode("ascii", "replace"),
        "test_name": p[11:49].decode("utf-16-le", "replace").split("\0")[0],
        "tz_offset_min": struct.unpack_from(">h", p, 49)[0],
        "total_records": u16(p, 51),
        "interval": p[53],
        "interval_unit": p[54],
        "state": p[55],
        "start": dt.datetime.fromtimestamp(struct.unpack_from(">I", p, 66)[0], dt.UTC).replace(tzinfo=None),
        "records": u16(p, 75),
        "thresholds": th,
    }


THRESHOLD_SCALE = {"T": 10, "RH": 10, "CO2": 1, "HCHO": 100, "C6H6": 1000, "PM2.5": 1}
THRESHOLD_OFFSETS = [57, 59, 61, 63, 77, 79, 81, 83, 85, 87, 89, 91]  # in thresholds() order


def encode_params(raw, serial=None, test_name=None, total_records=None, interval=None,
                  interval_unit=None, thresholds=None, manual=False, when=None):
    """Build a report 2 parameter block from one read back (raw), changing the given fields.

    Like the Windows software, the recording start is now and the read only fields are cleared.
    thresholds: {"CO2": (lo, hi), ...} in display units.
    manual: the monitor waits for a short LEFT button press instead of recording immediately.
    """
    p = bytearray(2 * FRAME_LEN)
    p[:PARAM_LEN] = raw[:PARAM_LEN]
    if serial is not None:
        b = serial.encode("ascii")
        assert len(b) <= 10 and serial.isalnum(), "serial: up to 10 letters or digits"
        p[1:11] = b.ljust(10, b"\0")
    if test_name is not None:
        assert len(test_name) <= 10, "test name: up to 10 characters"
        p[11:49] = test_name.encode("utf-16-le").ljust(38, b"\0")
    when = when or time.time()
    local = dt.datetime.fromtimestamp(when).astimezone()
    struct.pack_into(">h", p, 49, -int(local.utcoffset().total_seconds() // 60))
    if total_records is not None:
        assert 1 <= total_records <= 10000, "total records: 1 to 10000"
        struct.pack_into(">H", p, 51, total_records)
    if interval is not None:
        assert 1 <= interval <= 255, "interval: 1 to 255"
        p[53] = interval
    if interval_unit is not None:
        p[54] = interval_unit
    p[55] = 0  # state, 1 once recording
    for name, (lo, hi) in (thresholds or {}).items():
        k = list(THRESHOLD_SCALE).index(name)
        off = 400 if name == "T" else 0
        for i, v in zip(THRESHOLD_OFFSETS[2 * k:2 * k + 2], (lo, hi)):
            struct.pack_into(">H", p, i, round(v * THRESHOLD_SCALE[name]) + off)
    struct.pack_into(">I", p, 66, int(when))
    p[70] = 0 if manual else 1  # start mode: 1 Immediately, 0 Manual
    p[71:77] = bytes(6)  # second time and records stored, read only
    p[93] = 0  # read only
    return bytes(p)


def decode_record(r):
    T = (r[2] & 0x0F) << 8 | r[0]
    RH = (r[2] >> 4) << 8 | r[1]
    le = lambda i: r[i] | r[i + 1] << 8
    return {
        "T": (T - 400) / 10,
        "RH": RH / 10,
        "CO2": le(3),
        "HCHO": le(5) / 100,
        "C6H6": le(7) / 1000,
        "PM2.5": le(9),
    }


def decode_block(r):
    assert r[0] == 8, r[0]
    return [decode_record(r[1 + k * RECORD_LEN:1 + (k + 1) * RECORD_LEN]) for k in range(RECORDS_PER_BLOCK)]


def download_csv(q, out):
    p = q.params()
    step = dt.timedelta(seconds=p["interval"] * UNIT_SECONDS[p["interval_unit"]])
    start = p["start"].replace(tzinfo=dt.UTC)
    records = q.download(q.status()["records"])
    w = csv.DictWriter(out, fieldnames=["index", "time_utc"] + list(records[0]) if records else ["index"])
    w.writeheader()
    for i, rec in enumerate(records):
        w.writerow({"index": i, "time_utc": (start + i * step).isoformat().replace("+00:00", "Z"), **rec})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["status", "params", "set-time", "download", "set-params"])
    ap.add_argument("-o", "--out", help="CSV file for download (default: stdout)")
    ap.add_argument("--serial", help="set-params: serial number, up to 10 letters or digits")
    ap.add_argument("--name", help="set-params: test name, up to 10 characters")
    ap.add_argument("--records", type=int, help="set-params: total records to take, 1 to 10000")
    ap.add_argument("--interval", type=int, help="set-params: interval value, 1 to 255")
    ap.add_argument("--unit", choices=["s", "min", "h"], help="set-params: interval unit")
    ap.add_argument("--threshold", action="append", default=[], metavar="NAME=LO,HI",
                    help=f"set-params: alarm thresholds, NAME one of {', '.join(THRESHOLD_SCALE)} (repeatable)")
    ap.add_argument("--manual", action="store_true",
                    help="set-params: start recording with a short LEFT button press, not immediately")
    ap.add_argument("--device", help="hidraw path (default: autodetect)")
    args = ap.parse_args()

    q = Quaelis(args.device)
    try:
        if args.command == "status":
            for k, v in q.status().items():
                print(f"{k:12} {v}")
        elif args.command == "params":
            for k, v in q.params().items():
                print(f"{k:14} {v}")
        elif args.command == "set-time":
            q.set_time()
            time.sleep(1.5)  # the monitor reports the old clock for about a second
            print("clock now", q.status()["clock"])
        elif args.command == "download":
            download_csv(q, open(args.out, "w", newline="") if args.out else sys.stdout)
        elif args.command == "set-params":
            th = {}
            for t in args.threshold:
                name, _, vals = t.partition("=")
                if name not in THRESHOLD_SCALE:
                    ap.error(f"unknown threshold {name}")
                th[name] = tuple(float(v) for v in vals.split(","))
            raw = encode_params(q.raw_params(), args.serial, args.name, args.records, args.interval,
                                {"s": 0, "min": 1, "h": 2}.get(args.unit), th, args.manual)
            backup = f"quaelis_backup_{dt.datetime.now(dt.UTC):%Y%m%dT%H%M%SZ}.csv"
            with open(backup, "w", newline="") as f:
                download_csv(q, f)
            print("stored records saved to", backup)
            q.set_params(raw)
            time.sleep(1.5)
            for k, v in q.params().items():
                print(f"{k:14} {v}")
    finally:
        q.close()


if __name__ == "__main__":
    main()
