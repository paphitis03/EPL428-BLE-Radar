"""Browse the generated BLE Radar analysis with Streamlit."""
import pandas as pd
import streamlit as st

from preprocessing import ROOT

RESULTS = ROOT / "results"
st.set_page_config(page_title="BLE Radar", layout="wide")
st.title("BLE Radar")
if not (RESULTS / "quality.csv").exists():
    st.info("Run python analyze.py to generate the dashboard data.")
    st.stop()


def read(name):
    return pd.read_csv(RESULTS / f"{name}.csv")


def show_plot(key):
    path = RESULTS / "plots" / f"{key}.png"
    if path.exists():
        st.image(str(path))


quality = read("quality")
name = st.sidebar.selectbox("Experiment", quality.dataset, format_func=str.title)
audit = quality.set_index("dataset").loc[name]
data = read(f"{name}_preprocessed")
columns = st.columns(5)
for column, label, value in zip(columns,
    ["Total observations", "Average count", "Minimum count", "Maximum count", "Average RSSI"],
    [audit.raw_observations, f"{data.devices.mean():.2f}", data.devices.min(),
     data.devices.max(), f"{data.avg_rssi.mean():.2f} dBm"]):
    column.metric(label, value)
st.caption(f"{audit.usable_observations} usable scans. Counts represent observed BLE advertisers.")
boundaries = read("recording_boundaries").query("dataset == @name")
if not boundaries.empty:
    gaps = boundaries.loc[boundaries.recording_gap, "interval_seconds"]
    st.warning(f"{len(boundaries)} recording boundaries. Gap durations (seconds) " +
               (", ".join(f"{value:.2f}" for value in gaps) if len(gaps) else "none"))
    st.dataframe(boundaries, hide_index=True)

overview, stationarity, forecasts, comparison = st.tabs(
    ["Measurements", "Stationarity", "Forecasts", "Compare experiments"])
segments = read("segments").query("dataset == @name")
with overview:
    left, right = st.columns(2)
    with left:
        show_plot(f"{name}_devices")
    with right:
        show_plot(f"{name}_rssi")
    st.dataframe(segments, hide_index=True)
with stationarity:
    st.dataframe(read("stationarity").query("dataset == @name"), hide_index=True)
    show_plot(f"{name}_differenced")
    segment = st.selectbox("Continuous segment", segments.segment)
    left, right = st.columns(2)
    with left:
        show_plot(f"{name}_s{segment}_acf")
    with right:
        show_plot(f"{name}_s{segment}_pacf")
with forecasts:
    metrics = read("performance").query("dataset == @name")
    if metrics.empty:
        st.info("No segment has enough observations for forecasting.")
    else:
        st.subheader("Experiment-wide forecast accuracy")
        st.dataframe(read("dataset_performance").query("dataset == @name"), hide_index=True)
        number = st.selectbox("Evaluated segment", metrics.segment.unique())
        st.dataframe(metrics.query("segment == @number"), hide_index=True)
        for plot in ("predictions", "errors", "mae", "rmse"):
            show_plot(f"{name}_s{number}_{plot}")
with comparison:
    st.dataframe(read("descriptive_statistics").query("variable in ['devices', 'avg_rssi']"),
                 hide_index=True)
    left, right = st.columns(2)
    with left:
        show_plot("compare_devices")
    with right:
        show_plot("compare_avg_rssi")
