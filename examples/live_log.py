#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Log live readings of a Quaelis 50 to CSV, from the computer, until Ctrl+C.

Usage (from the repository root):
    python3 examples/live_log.py [SECONDS] > live.csv

SECONDS is the time between readings (default 10). Unlike a recording on the monitor, this
needs the monitor connected for the whole session, but it has no 10000 record limit and does
not touch the monitor's stored records or a recording in progress.
"""
import csv
import datetime as dt
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from quaelis import Quaelis

FIELDS = ["T", "RH", "CO2", "HCHO", "C6H6", "PM2.5"]

interval = float(sys.argv[1]) if len(sys.argv) > 1 else 10
q = Quaelis()
w = csv.writer(sys.stdout)
w.writerow(["time_utc"] + FIELDS)
try:
    while True:
        s = q.status()
        now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        w.writerow([now] + [s[k] for k in FIELDS])
        sys.stdout.flush()
        time.sleep(interval)
except KeyboardInterrupt:
    pass
finally:
    q.close()
