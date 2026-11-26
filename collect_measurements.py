"""Record BLEScanner USB serial measurements. Requires pyserial and pandas."""

import argparse
import csv
import math
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd
import serial


COLUMNS = [
    "computer_timestamp_utc", "elapsed_ms", "devices", "avg_rssi",
    "max_rssi", "min_rssi", "scan_ms", "status", "ble_reason",
]
STATUSES = {"ok", "start_failed", "timeout", "scan_error"}
SOURCE_FILES = tuple(
    Path(__file__).resolve().with_name(name) for name in (
        "ble_measurements.csv", "ble_measurements_with_activity.csv",
        "ble_measurements_moving.csv",
    )
)


def parse_measurement(line):
    fields = line.strip().split(",")
    if len(fields) != 8 or fields[6] not in STATUSES:
        return None

    try:
        elapsed, devices, average, strongest, weakest, duration, status, reason = fields
        measurement = (
            int(elapsed),
            int(devices),
            float(average) if average else None,
            int(strongest) if strongest else None,
            int(weakest) if weakest else None,
            int(duration),
            status,
            int(reason),
        )
    except ValueError:
        return None

    elapsed, count, average, strongest, weakest, duration, status, reason = measurement
    if min(elapsed, count, duration) < 0:
        return None
    if status == "ok" and (duration == 0 or reason != 0):
        return None
    if count > 0:
        if any(value is None for value in (average, strongest, weakest)):
            return None
        if not math.isfinite(average) or not weakest <= average <= strongest:
            return None
    elif any(value is not None for value in (average, strongest, weakest)):
        return None
    return measurement


def record(port, output):
    output = output.resolve()
    if output in SOURCE_FILES or (
        output.exists() and any(source.exists() and output.samefile(source)
                                for source in SOURCE_FILES)
    ):
        raise ValueError(f"{output.name} is an original measurement file. Choose a new output.")
    with serial.Serial(port, baudrate=115200, timeout=1) as board:
        with output.open("a+", encoding="utf-8", newline="") as csv_file:
            csv_file.seek(0)
            header = next(csv.reader(csv_file), None)
            if header is not None and header != COLUMNS:
                raise ValueError(f"{output} has a different CSV header")

            if header is None:
                pd.DataFrame(columns=COLUMNS).to_csv(csv_file, index=False)
                csv_file.flush()

            print(f"Recording {port} to {output}. Press Ctrl+C to stop.", flush=True)
            pending = bytearray()
            while True:
                chunk = board.readline()
                pending.extend(chunk)
                if not chunk.endswith(b"\n"):
                    continue

                timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                measurement = parse_measurement(pending.decode("ascii", errors="replace"))
                pending.clear()
                if measurement is not None:
                    pd.DataFrame([(timestamp, *measurement)], columns=COLUMNS).to_csv(
                        csv_file, index=False, header=False
                    )
                    csv_file.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="LilyGo USB serial port (for example, COM5)")
    parser.add_argument("-o", "--output", type=Path, required=True,
                        help="Destination CSV for the new recording")
    args = parser.parse_args()

    try:
        record(args.port, args.output)
    except KeyboardInterrupt:
        print("\nRecording stopped.")
    except (OSError, ValueError) as error:
        print(f"Recording failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
