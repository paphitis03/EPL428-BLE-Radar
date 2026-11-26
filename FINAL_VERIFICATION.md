# BLE Radar final verification

Audit date: 26 November 2026. Scope: the LilyGo T-Beam S3 Supreme firmware, USB serial collector, three archived measurements, analysis, and Streamlit dashboard in `examples/BLEScanner`.

## Software verification

| Check | Result | Evidence |
|---|---|---|
| Firmware compilation | Pass | PlatformIO 6.2.0 built `t-beams3-supreme-ble` from an empty build directory. ESP32 platform 8.0.0, Arduino core 3.3.12, NimBLE 2.3.9, U8g2 2.36.18 and XPowersLib 0.3.3. The build produced `firmware.bin`, using 35,632 bytes of RAM and 579,395 bytes of application flash. |
| BLE scan and count logic | Source reviewed | Firmware runs passive five-second scans, counts the completed NimBLE results and clears the list between windows. NimBLE 2.3.9 reuses result entries for the same advertiser address in the standard scan configuration. The firmware emits the count, RSSI summary, duration, status and completion reason. Physical RF reception and counting still require the controlled test below. |
| Timestamped collection | Pass with simulated serial input | Tested the full collector with fragmented records across a timeout, startup messages, malformed RSSI, a zero-count scan, a firmware error row and an incomplete final record. Verified 115200 baud configuration, millisecond UTC receive timestamps, blank RSSI for zero count and one header across two append sessions. The UTC timestamp comes from the host when a complete line is received. |
| Original data preservation | Pass | SHA-256 matched the prior analysis baseline before and after verification for all three archived CSVs. The collector now requires an explicit destination and refuses each archive before opening the serial port. |
| Moving recording gaps | Pass | Detected gaps of 123.836 and 257.065 seconds and backward timer jumps at source CSV lines 72 and 122. The analysis uses separate 70-, 50- and 60-scan segments. Correlations, differences, rolling windows and model states stay within segment boundaries. |
| Chronological splits | Pass | Verified strictly increasing timestamps within each segment and matched all forecast timestamps to the segment's final test partition. Train/test sizes were 143/36 for Stationary, 143/36 for Activity, and 56/14, 40/10 and 48/12 for Moving. |
| Training-only selection and forecast causality | Pass | Reviewed moving-average and smoothing tuning on the final quarter of training, and ARIMA order selection by training ADF, ACF/PACF and AIC. Checked each selected ARIMA AIC against converged candidates. Altering held-out targets from the first and middle test positions onward left selected parameters, candidate results and forecasts through each changed position unchanged for all four models across all five segments. Later forecasts may use prior observed test values, as intended for rolling one-step evaluation. |
| MAE and RMSE | Pass | Recomputed mean absolute error and the square root of mean squared error directly from actuals and predictions for all 20 model evaluations and 432 forecast rows. |
| Graphs and statistical results | Pass | Two runs into fresh output directories matched byte-for-byte across 103 files, including 90 valid PNGs at 2700 × 1200 and 300 dpi. Recomputed ADF p-values and all reported Ljung–Box statistics and p-values. Byte comparison was performed on the same Python installation and platform. |
| Dashboard | Pass with Streamlit AppTest | Verified Stationary, Activity and Moving selections, summary metrics, figures, gap warning behavior and both moving segment selectors. The dashboard loads saved analysis results. |
| Installation and execution instructions | Pass | The README now includes analysis and dashboard setup, PlatformIO build and upload, serial-port discovery, and a safe recording command. |
| Credentials and identifiers | No secrets detected in the checked files | Searched current source and configuration in the repository for common secret patterns. The Wi-Fi credential match in the separate RTC synchronization example consists of placeholders. The BLEScanner CSV schemas contain UTC times and scan aggregates, with no advertiser addresses, names or payloads. Ignored VS Code files contain workstation paths, and Git history metadata contains an author email. These identifiers are omitted from this report. The scan covered the current checkout and common patterns, with no exhaustive binary or Git history content audit. |

### Bugs fixed

- The collector previously defaulted to appending to the original moving CSV. It now requires `--output` and rejects all three archived CSVs, including aliases that resolve to the same file.
- The collector previously accepted malformed numeric records such as non-finite average RSSI. It now rejects invalid durations, counts and inconsistent RSSI fields while retaining valid zero-count scans and firmware error records.
- A run with no forecast-eligible segments previously failed at concatenation. Empty forecast and boundary outputs now keep their headers. Experiment-wide metrics require each model to cover the same held-out scans. A short-recording software test confirmed that the empty outputs can be read.

### Archive SHA-256 baselines

| File | SHA-256 |
|---|---|
| `ble_measurements.csv` | `48f926abe36f82e766a9e34f0bb93c5497628199cc2c09505729d2f48ac6fa8f` |
| `ble_measurements_with_activity.csv` | `96b7e5ea25d54cbb765ce336fe0d42bdda10a152a3c03fd224bda45c41d2bf5f` |
| `ble_measurements_moving.csv` | `2365933fda23d75c608b99a15fef24086d72617cc9cfb4dc05d8ef905736c40a` |

## Current data transport and storage

The board receives ambient BLE advertisements, shows aggregate results on its display and sends text records to the computer over USB serial at 115200 baud. The Python collector adds the host UTC timestamp and appends to a CSV on the computer. The BLEScanner build has no measurement export over BLE, Wi-Fi or LoRa, and no SD or other onboard measurement logging. Without a connected collector, a scan can still appear on the display, but it leaves no saved measurement in this implementation.

Counts represent observed BLE advertisers per window. The current aggregates cannot establish per-device detection accuracy or enumerate physical devices or people. The moving holdouts have 10–14 scans per segment, which limits the precision of model rankings and residual tests.

## Exact commands

Run in PowerShell from `examples/BLEScanner` with Python 3.12.

```powershell
python --version
python -m pip install -r requirements.txt
python -m pip install platformio==6.2.0 pyserial==3.5
python -m platformio run -e t-beams3-supreme-ble
Get-FileHash -Algorithm SHA256 ble_measurements.csv,ble_measurements_with_activity.csv,ble_measurements_moving.csv
python analyze.py
python -m streamlit run dashboard.py
```

Open the local URL printed by Streamlit. Use the commands below in a separate terminal for the board.

## Live demonstration

The upload, display, RF and USB checks below require the physical LilyGo board. This audit did not upload firmware or open a physical serial connection.

1. Connect the T-Beam S3 Supreme with a USB data cable. Run `python -m serial.tools.list_ports`. If several ports appear, identify the board by comparing the list before and after reconnecting it.
2. Substitute the board's port for `COM4`, then upload. Check for an upload success message and the BLE scanning screen after boot.

   ```powershell
   python -m platformio run -e t-beams3-supreme-ble -t upload --upload-port COM4
   ```

3. Keep the board stationary. Close any serial monitor and start a new recording. Wait for at least three complete scan windows with the test advertiser disabled to establish a baseline.

   ```powershell
   $demoCsv = "ble_demo_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
   python collect_measurements.py COM4 --output $demoCsv
   ```

4. Enable a known BLE beacon with a stable address nearby and allow at least three complete windows. Disable it and repeat. In an RF-controlled setting, one stable advertiser should add one result per window in which it is received, even if it sends multiple packets. In a busy room, compare several windows and record the background variation. Compare the displayed count and RSSI fields with corresponding CSV rows.
5. Stop the collector with Ctrl+C and inspect the saved file. Expect one header, increasing UTC receive times during uninterrupted recording, scan durations around 5,000 ms, normal `ok` status with reason 0, and minimum RSSI ≤ average RSSI ≤ maximum RSSI for nonzero counts. A zero-count scan has blank RSSI fields.

   ```powershell
   Get-Content -LiteralPath $demoCsv -TotalCount 8
   Get-Content -LiteralPath $demoCsv -Tail 8
   ```

6. In the dashboard, select Stationary, Activity and Moving in turn. Confirm the totals are 179, 179 and 180. In Moving, point out both gap warnings and switch among forecast segments. The dashboard shows the archived runs, while the demonstration recording stays in its separate file.
7. Show the MAE and RMSE comparison. Stationary favored ARIMA by both metrics, Activity favored exponential smoothing by both, and Moving favored smoothing by MAE and ARIMA by RMSE. Rerun the SHA-256 command to confirm the three archives still match the baselines.
