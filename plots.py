"""Save publication-resolution analysis figures."""
import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.dates import DateFormatter
from scipy.stats import norm
from statsmodels.tsa.stattools import acf, pacf

from forecasting import correlation_lags
from preprocessing import TIMESTAMP


def save(directory, key, title, xlabel, ylabel, draw):
    fig, ax = plt.subplots(figsize=(9, 4))
    try:
        draw(ax)
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
        ax.grid(alpha=0.2)
        if xlabel == "Time (UTC)":
            ax.xaxis.set_major_formatter(DateFormatter("%H:%M:%S"))
        fig.tight_layout()
        fig.savefig(directory / f"{key}.png", dpi=300)
    finally:
        plt.close(fig)


def correlation(ax, values, partial=False):
    lags = correlation_lags(values)
    if lags < 1 or not np.ptp(values):
        ax.text(.5, .5, "Insufficient variation or observations", ha="center",
                transform=ax.transAxes)
        return
    coefficients = (pacf(values, nlags=lags, method="ywm") if partial
                    else acf(values, nlags=lags, fft=False))
    bound = norm.ppf(.975) / np.sqrt(len(values))
    ax.axhspan(-bound, bound, alpha=.15)
    ax.axhline(0, color="gray", linewidth=.8)
    ax.stem(np.arange(1, lags + 1), coefficients[1:])


def lines(ax, data, field, relative=False):
    for _, segment in data.groupby("segment"):
        x = segment[TIMESTAMP]
        if relative:
            x = (x - data[TIMESTAMP].iloc[0]).dt.total_seconds() / 60
        ax.plot(x, segment[field], marker=".", markersize=2)


def exploration(directory, name, data):
    def rolling(ax):
        for number, segment in data.groupby("segment"):
            values = segment.devices.rolling(12)
            ax.plot(segment[TIMESTAMP], values.mean(), color="C0",
                    label="Mean" if number == 1 else "_nolegend_")
            ax.plot(segment[TIMESTAMP], values.std(), color="C1",
                    label="Standard deviation" if number == 1 else "_nolegend_")
        ax.legend()

    def render(key, title, x, y, draw):
        save(directory, f"{name}_{key}", f"{name.title()} · {title}", x, y, draw)

    render("devices", "Observed advertisers", "Time (UTC)", "Count",
           lambda ax: lines(ax, data, "devices"))
    render("rssi", "Scan-average RSSI", "Time (UTC)", "dBm",
           lambda ax: lines(ax, data, "avg_rssi"))
    render("histogram", "Device count distribution", "Count", "Scans",
           lambda ax: ax.hist(data.devices, bins="auto"))
    render("boxplot", "Device count spread", "Experiment", "Count",
           lambda ax: ax.boxplot(data.devices))
    render("rolling", "12-scan rolling statistics", "Time (UTC)", "Count", rolling)
    changes = data.assign(change=data.groupby("segment").devices.diff())
    render("differenced", "First differences within segments", "Time (UTC)",
           "Change in count", lambda ax: lines(ax, changes, "change"))
    for number, segment in data.groupby("segment"):
        for kind in ("acf", "pacf"):
            render(f"s{number}_{kind}", f"Segment {number} {kind.upper()}",
                   "Lag (scans)", "Correlation",
                   lambda ax: correlation(ax, segment.devices.to_numpy(), kind == "pacf"))


def compare(directory, datasets):
    names = list(datasets)
    for field, label in [("devices", "Count"), ("avg_rssi", "dBm")]:
        def box(ax):
            ax.boxplot([data[field].dropna() for data in datasets.values()])
            ax.set_xticks(range(1, len(names) + 1), names)
        save(directory, f"compare_{field}", f"{field} by experiment", "Experiment", label, box)


def forecast_plots(directory, key, predictions, metrics):
    groups = list(predictions.groupby("model", sort=False))
    def actual(ax):
        first = groups[0][1]
        ax.plot(first[TIMESTAMP], first.actual, color="black", label="Actual")
        for model, data in groups:
            ax.plot(data[TIMESTAMP], data.prediction, label=model)
        ax.legend(fontsize=8)

    def errors(ax):
        for model, data in groups:
            ax.plot(data[TIMESTAMP], data.error, label=model)
        ax.axhline(0, color="black", linewidth=.8)
        ax.legend(fontsize=8)

    save(directory, f"{key}_predictions", f"{key} · Actual and predicted counts",
         "Time (UTC)", "Count", actual)
    save(directory, f"{key}_errors", f"{key} · One-step errors",
         "Time (UTC)", "Actual minus predicted", errors)
    for model, data in groups:
        slug = model.lower().replace(" ", "_")
        save(directory, f"{key}_{slug}_residual_histogram", f"{key} · {model}",
             "Residual", "Test scans", lambda ax: ax.hist(data.error, bins="auto"))
        save(directory, f"{key}_{slug}_residual_acf", f"{key} · {model} residual ACF",
             "Lag (scans)", "Correlation", lambda ax: correlation(ax, data.error.to_numpy()))
    for metric in ("mae", "rmse"):
        ordered = metrics.sort_values(metric)
        save(directory, f"{key}_{metric}", f"{key} · {metric.upper()}",
             metric.upper(), "Model", lambda ax: ax.barh(ordered.model, ordered[metric]))
