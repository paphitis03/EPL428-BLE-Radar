"""Generate the complete BLE Radar analysis from the three source CSVs."""
import numpy as np
import pandas as pd

from forecasting import MIN_FORECAST, adf, evaluate, rolling_predictions
from plots import compare, exploration, forecast_plots
from preprocessing import ROOT, TIMESTAMP, load_all

RESULTS = ROOT / "results"
PLOTS = RESULTS / "plots"
BOUNDARIES = ["recording_gap", "timer_reset", "clock_discontinuity", "invalid_scan_boundary"]


def analyze():
    PLOTS.mkdir(parents=True, exist_ok=True)
    quality, gaps, segments, tests, scores, forecasts, selection, summaries, excluded = (
        [] for _ in range(9))
    datasets = {}
    boundary_columns = ["segment", "source_line", TIMESTAMP, "interval_seconds",
                        "timer_interval_seconds", *BOUNDARIES]
    for name, (data, audit, rejected) in load_all().items():
        datasets[name] = data
        quality.append({"dataset": name, **audit})
        excluded.extend(rejected.assign(dataset=name).to_dict("records"))
        data.to_csv(RESULTS / f"{name}_preprocessed.csv", index=False)
        for field in ["devices", "avg_rssi", "max_rssi", "min_rssi", "scan_ms",
                      "interval_seconds", "timer_interval_seconds"]:
            values = data[field]
            if field.endswith("interval_seconds"):
                values = values.loc[~data[BOUNDARIES].any(axis=1)]
            summaries.append({"dataset": name, "variable": field, **values.describe().to_dict()})
        gaps.extend(data.loc[data[BOUNDARIES].any(axis=1), boundary_columns]
                    .assign(dataset=name).to_dict("records"))
        exploration(PLOTS, name, data)
        if data.segment.nunique() > 1:
            tests.append({"dataset": name, "segment": "pooled (legacy check only)",
                          "series": "level", **adf(data.devices.to_numpy())})
        for number, segment in data.groupby("segment"):
            values = segment.devices.to_numpy(dtype=float)
            keys = {"dataset": name, "segment": number}
            level = adf(values)
            tests.append({**keys, "series": "level", **level})
            if level["decision"] == "fail to reject unit root":
                tests.append({**keys, "series": "first difference", **adf(np.diff(values))})
            enough = len(values) >= MIN_FORECAST
            split = int(len(values) * .8)
            segments.append({**keys, "observations": len(values), "start": segment[TIMESTAMP].iloc[0],
                             "end": segment[TIMESTAMP].iloc[-1], "train": split if enough else 0,
                             "test": len(values) - split if enough else 0,
                             "forecast_status": "evaluated" if enough else
                             f"fewer than {MIN_FORECAST} continuous scans"})
            if not enough:
                continue
            actual = values[split:]
            models, candidates = rolling_predictions(values[:split], actual)
            selection.extend({**keys, **row} for row in candidates)
            model_rows, series_rows = [], []
            for model, (prediction, parameters) in models.items():
                prediction = np.asarray(prediction)
                model_rows.append({**keys, "model": model, "parameters": parameters,
                                   "test_n": len(actual), **evaluate(actual, prediction)})
                series_rows.append(pd.DataFrame({**keys, "model": model,
                    TIMESTAMP: segment[TIMESTAMP].iloc[split:].to_numpy(),
                    "actual": actual, "prediction": prediction, "error": actual - prediction}))
            performance = pd.DataFrame(model_rows)
            for metric in ("mae", "rmse"):
                performance[f"best_{metric}"] = performance[metric].eq(performance[metric].min())
            predictions = pd.concat(series_rows, ignore_index=True)
            scores.extend(performance.to_dict("records"))
            forecasts.append(predictions)
            forecast_plots(PLOTS, f"{name}_s{number}", predictions, performance)

    compare(PLOTS, datasets)
    for filename, rows in {
        "quality": quality, "recording_boundaries": gaps, "segments": segments,
        "descriptive_statistics": summaries, "stationarity": tests,
        "performance": scores, "arima_selection": selection, "excluded_rows": excluded,
    }.items():
        table = pd.DataFrame(rows)
        if filename == "excluded_rows" and table.empty:
            table = pd.DataFrame(columns=["dataset", "source_line", "duplicate", "usable"])
        if filename == "recording_boundaries" and table.empty:
            table = pd.DataFrame(columns=[*boundary_columns, "dataset"])
        if filename == "performance" and table.empty:
            table = pd.DataFrame(columns=["dataset", "segment", "model", "parameters",
                                          "test_n", "mae", "rmse", "ljung_box_lag",
                                          "ljung_box_statistic", "ljung_box_p",
                                          "best_mae", "best_rmse"])
        if filename == "arima_selection" and table.empty:
            table = pd.DataFrame(columns=["dataset", "segment", "p", "d", "q", "aic",
                                          "selected", "train_adf_p", "train_diff_adf_p",
                                          "acf_threshold", "train_pacf_at_p", "train_acf_at_q",
                                          "warnings", "status"])
        table.to_csv(RESULTS / f"{filename}.csv", index=False)
    prediction_columns = ["dataset", "segment", "model", TIMESTAMP, "actual",
                          "prediction", "error"]
    predictions = (pd.concat(forecasts, ignore_index=True) if forecasts
                   else pd.DataFrame(columns=prediction_columns))
    predictions.to_csv(RESULTS / "predictions.csv", index=False)
    dataset_scores = []
    for dataset, dataset_rows in predictions.groupby("dataset"):
        expected = dataset_rows[["segment", TIMESTAMP]].drop_duplicates().shape[0]
        for model, rows in dataset_rows.groupby("model"):
            if len(rows) == expected:
                dataset_scores.append({"dataset": dataset, "model": model, "test_n": len(rows),
                                       "mae": rows.error.abs().mean(),
                                       "rmse": np.sqrt(rows.error.pow(2).mean())})
    combined = pd.DataFrame(dataset_scores, columns=["dataset", "model", "test_n", "mae", "rmse"])
    for metric in ("mae", "rmse"):
        combined[f"best_{metric}"] = combined[metric].eq(
            combined.groupby("dataset")[metric].transform("min"))
    combined.to_csv(RESULTS / "dataset_performance.csv", index=False)
    print(pd.DataFrame(quality)[["dataset", "raw_observations", "usable_observations"]].to_string(index=False))
    print(pd.DataFrame(tests).to_string(index=False))
    print(pd.DataFrame(scores).to_string(index=False))


if __name__ == "__main__":
    analyze()
