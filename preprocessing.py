"""Read measurements without modifying the source files."""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCES = {
    "stationary": "ble_measurements.csv",
    "activity": "ble_measurements_with_activity.csv",
    "moving": "ble_measurements_moving.csv",
}
NUMERIC = ["elapsed_ms", "devices", "avg_rssi", "max_rssi", "min_rssi",
           "scan_ms", "ble_reason"]
TIMESTAMP = "computer_timestamp_utc"


def load_all():
    return {name: preprocess(ROOT / filename) for name, filename in SOURCES.items()}


def preprocess(path):
    raw = pd.read_csv(path)
    data = raw.copy()
    data[TIMESTAMP] = pd.to_datetime(data[TIMESTAMP], utc=True, errors="coerce")
    for col in NUMERIC:
        data[col] = pd.to_numeric(data[col], errors="coerce").replace(
            [np.inf, -np.inf], np.nan)
    duplicate = raw.duplicated()
    status_ok = data["status"].str.strip().str.lower().eq("ok")
    valid = (status_ok & data[TIMESTAMP].notna() & data["elapsed_ms"].ge(0)
             & data["devices"].ge(0) & data["devices"].mod(1).eq(0)
             & data["scan_ms"].gt(0))
    # Keep file order so backwards clocks and timer resets remain visible.
    data["source_line"] = np.arange(len(data)) + 2
    data["duplicate"] = duplicate
    data["usable"] = valid & ~duplicate
    measurements = data.loc[data["usable"]].copy()
    measurements["interval_seconds"] = measurements[TIMESTAMP].diff().dt.total_seconds()
    measurements["timer_interval_seconds"] = measurements["elapsed_ms"].diff() / 1000
    typical = measurements["interval_seconds"].where(
        measurements["interval_seconds"].gt(0)).median()
    measurements["recording_gap"] = measurements["interval_seconds"].gt(1.5 * typical)
    measurements["timer_reset"] = measurements["timer_interval_seconds"].le(0)
    measurements["clock_discontinuity"] = measurements["interval_seconds"].le(0)
    skipped = (~data["usable"] & ~data["duplicate"]).cumsum()
    measurements["invalid_scan_boundary"] = skipped.loc[measurements.index].diff().gt(0)
    flags = ["recording_gap", "timer_reset", "clock_discontinuity", "invalid_scan_boundary"]
    measurements["segment"] = 1 + measurements[flags].any(axis=1).cumsum()
    quality = {"raw_observations": len(raw), "usable_observations": len(measurements),
               "duplicates": int(duplicate.sum()), "invalid_scans": int((~status_ok).sum()),
               "excluded_rows": int((~data["usable"]).sum()),
               "median_interval_seconds": typical,
               **{f"missing_{col}": int(data[col].isna().sum()) for col in raw.columns}}
    return measurements, quality, data.loc[~data["usable"]]
