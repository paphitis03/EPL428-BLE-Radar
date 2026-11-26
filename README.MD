# BLE Radar — EPL428 Internet of Things

The project studies how the number and signal strength of observed BLE advertisers change across stationary, nearby-activity, and moving experiments. It compares one-scan-ahead forecasts of advertiser counts on held-out measurements.

## Hardware and data collection

A LilyGo T-Beam S3 Supreme (ESP32-S3) runs the Arduino firmware in `main.cpp` under PlatformIO. NimBLE performs passive five-second scans. The firmware displays summaries on the board and sends scan aggregates over USB serial at 115200 baud. The Python collector adds a UTC computer timestamp and appends each record to a CSV.

| Experiment | CSV | Observations |
|---|---|---:|
| Stationary | `ble_measurements.csv` | 179 |
| With activity | `ble_measurements_with_activity.csv` | 179 |
| Moving | `ble_measurements_moving.csv` | 180 |

Each row records the computer timestamp, device elapsed time in milliseconds, observed advertiser count, average/maximum/minimum RSSI in dBm, scan duration in milliseconds, scan status, and BLE completion reason. The primary series is `devices`.

## Preprocessing and analysis

The analysis validates UTC timestamps, numeric fields, and scan status, audits missing values and exact duplicate rows, and excludes duplicates and invalid scans from modeling. It retains file order so clock regressions and device timer resets remain visible. A new segment begins after a host interval exceeding 1.5 times the experiment's median positive interval, a nonpositive host or timer interval, or an intervening invalid scan. Sampling statistics exclude boundary intervals. Time plots preserve elapsed gaps, and rolling statistics, differences, ACF and PACF are computed within segments. The rolling window is 12 scans.

The ADF test uses an intercept, AIC lag selection, and a 0.05 significance level. It tests levels and repeats the test on first differences when the level test fails to reject a unit root. Segments need at least 20 values for ADF. The pooled moving test is included solely to reproduce the preliminary calculation. Seasonal terms were omitted because the experiments provide limited evidence about repeated cycles.

Segments of at least 50 scans use the first 80% (rounded down) for training and the remainder for rolling one-step evaluation. Persistence carries forward the previous count. The moving-average window and exponential-smoothing coefficient minimize one-step MAE on the final quarter of the training partition. ARIMA chooses first differencing when training ADF supports it. The order search includes zero, one, and lags through three that cross the pointwise 95% white-noise bound in the training PACF (AR) or ACF (MA). It selects the converged fit with the lowest training AIC. Test observations update model state only after their forecasts, with parameters held fixed.

MAE and RMSE are in advertiser counts. Residuals are actual minus predicted. Ljung–Box tests use up to ten held-out residual lags, capped at one fifth of the test size and with no fitted-parameter degrees-of-freedom adjustment for these out-of-sample forecast errors. Interpret those p-values cautiously on small test sets. Separate best-model flags capture ties and differences between the two metrics.

## Actual results

All 538 rows passed the checks, with zero missing values, duplicates or failed scans. The mean within-segment host interval was about 5.035 seconds in each experiment. Moving had gaps of 123.836 and 257.065 seconds, both accompanied by a backward device timer jump. The gaps divided the recording into 70, 50 and 60 scans. The corresponding test sets contained 14, 10 and 12 scans, so their model rankings are sensitive to individual errors.

| Experiment | Mean count | Min–max count | Mean scan RSSI (dBm) |
|---|---:|---:|---:|
| Stationary | 74.96 | 67–91 | -89.11 |
| With activity | 76.33 | 36–96 | -90.82 |
| Moving | 31.20 | 7–69 | -90.68 |

| Series | Level ADF p | First-difference ADF p |
|---|---:|---:|
| Stationary | 0.0001365 | — |
| With activity | 0.928876 | 0.004189 |
| Moving segment 1 | 0.964456 | 2.05e-10 |
| Moving segment 2 | 0.463294 | 5.82e-20 |
| Moving segment 3 | 0.029387 | — |

The stationary run and moving segment 3 reject the unit-root null at the level. The activity run and moving segments 1 and 2 reject it after first differencing. The preliminary pooled moving p-value of 0.364734 was reproduced by deliberately concatenating scans for that check alone.

| Evaluation | Best MAE (counts) | Best RMSE (counts) |
|---|---|---|
| Stationary | ARIMA(1,0,2), 2.601 | ARIMA(1,0,2), 3.141 |
| With activity | Exponential smoothing, 2.919 | Exponential smoothing, 3.485 |
| Moving, experiment-wide | Exponential smoothing, 2.583 | ARIMA, 3.885 |
| Moving segment 1 | Persistence, 2.571 | Persistence, 4.766 |
| Moving segment 2 | ARIMA(0,1,1), 2.577 | Exponential smoothing, 3.203 |
| Moving segment 3 | Exponential smoothing, 1.997 | Exponential smoothing, 2.671 |

Experiment-wide moving scores combine held-out errors from independently fitted segments. ARIMA's Ljung–Box p-value in moving segment 3 was 0.0493 at lag 2. Persistence on that segment also showed evidence of residual autocorrelation (p = 0.0074). Full metrics and residual tests are in [performance.csv](results/performance.csv), and [arima_selection.csv](results/arima_selection.csv) records training ADF results, ACF and PACF values, AIC, and convergence warnings.

## Limitations

Counts represent BLE advertiser addresses observed within each scan. Address rotation, multiple advertisers per physical device, and intermittent advertising can change the count. It does not establish the number of unique physical devices or people. The aggregate datasets do not establish detection accuracy for individual test devices. RSSI is a scan aggregate affected by the mix of advertisers, distance, obstruction, and radio conditions. The experiments cover a narrow set of conditions, and performance on a single chronological test partition per eligible segment may not generalize.

## Reproduce locally

From this directory with Python 3.12:

```powershell
python -m pip install -r requirements.txt
python analyze.py
python -m streamlit run dashboard.py
```

The analysis reads the three original CSV files and writes preprocessed datasets, quality checks, segment boundaries, summary statistics, stationarity tests, ARIMA candidate fits, forecasts and performance tables to [results/](results/). Figures are saved as 300 dpi PNGs under [results/plots/](results/plots/).

To build the firmware and make a separate recording, connect the board with a USB data cable. Run these commands from this directory and replace `COM4` with the port listed for the board. Close any serial monitor before starting the collector. The output argument is required, and the collector refuses to append to the three archived datasets.

```powershell
python -m pip install platformio==6.2.0 pyserial==3.5
python -m platformio run -e t-beams3-supreme-ble
python -m serial.tools.list_ports
python -m platformio run -e t-beams3-supreme-ble -t upload --upload-port COM4
python collect_measurements.py COM4 --output ble_new_recording.csv
```

The collector timestamps each complete serial record using the computer's UTC clock. Press Ctrl+C to stop. The firmware uses passive BLE reception and USB serial output; it does not transmit measurements wirelessly or write them to an SD card. See [FINAL_VERIFICATION.md](FINAL_VERIFICATION.md) for the live demonstration and audit.
