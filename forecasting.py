"""Training-only model selection and rolling one-step evaluation."""
from itertools import product
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.stattools import acf, adfuller, pacf

ALPHA = 0.05
MIN_ADF = 20
MIN_FORECAST = 50


def adf(values):
    if len(values) < MIN_ADF or np.ptp(values) == 0:
        return {"n": len(values), "statistic": np.nan, "p_value": np.nan,
                "lags": np.nan, "decision": "insufficient data or constant series"}
    statistic, p_value, lags, *_ = adfuller(values, regression="c", autolag="AIC", result_object=False)
    return {"n": len(values), "statistic": statistic, "p_value": p_value,
            "lags": lags, "decision": "reject unit root" if p_value < ALPHA
            else "fail to reject unit root"}


def smooth(history, alpha):
    level = history[0]
    for value in history[1:]:
        level = alpha * value + (1 - alpha) * level
    return level


def correlation_lags(values):
    return min(24, len(values) // 2 - 1)


def rolling_predictions(train, test):
    history = np.r_[train, test]
    start = len(train)
    # Tune simple models against the final 25% of the training partition.
    tune = range(int(start * 0.75), start)
    window = min([2, 3, 5, 8, 12], key=lambda w: np.mean(
        [abs(train[i] - train[i-w:i].mean()) for i in tune]))
    alpha = min(np.arange(0.1, 1.0, 0.1), key=lambda a: np.mean(
        [abs(train[i] - smooth(train[:i], a)) for i in tune]))
    positions = range(start, len(history))
    predictions = {
        "Persistence": (history[start-1:-1], "lag 1"),
        "Moving average": ([history[i-window:i].mean() for i in positions], f"window={window}"),
        "Simple exponential smoothing": ([smooth(history[:i], alpha) for i in positions],
                                         f"alpha={alpha:.1f}"),
    }

    level_test = adf(train)
    diff_test = adf(np.diff(train))
    d = int(level_test["decision"] == "fail to reject unit root"
            and diff_test["decision"] == "reject unit root")
    working = np.diff(train) if d else train
    bound = 1.96 / np.sqrt(len(working))
    if np.ptp(working):
        ar_lags = pacf(working, nlags=3, method="ywm")
        ma_lags = acf(working, nlags=3, fft=False)
    else:
        ar_lags = ma_lags = np.zeros(4)
    p_orders = sorted({0, 1, *(i for i in range(1, 4) if abs(ar_lags[i]) > bound)})
    q_orders = sorted({0, 1, *(i for i in range(1, 4) if abs(ma_lags[i]) > bound)})
    candidates = []
    best = None
    for p, q in product(p_orders, q_orders):
        order = (p, d, q)
        row = {"p": p, "d": d, "q": q, "aic": np.nan, "selected": False,
               "train_adf_p": level_test["p_value"], "train_diff_adf_p": diff_test["p_value"],
               "acf_threshold": bound, "train_pacf_at_p": ar_lags[p] if p else np.nan,
               "train_acf_at_q": ma_lags[q] if q else np.nan}
        candidates.append(row)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                fitted = ARIMA(train, order=order).fit()
            row["warnings"] = " | ".join(str(w.message) for w in caught)
            if not fitted.mle_retvals.get("converged", False) or not np.isfinite(fitted.aic):
                row["status"] = "nonconvergent or nonfinite AIC"
                continue
            row.update(aic=fitted.aic, status="ok")
            if best is None or fitted.aic < best[0].aic:
                best = fitted, row
        except (ValueError, np.linalg.LinAlgError) as error:
            row["status"] = str(error)

    if best is not None:
        state, row = best
        row["selected"] = True
        try:
            forecasts = []
            for actual in test:
                prediction = float(state.forecast()[0])
                if not np.isfinite(prediction):
                    raise ValueError("nonfinite prediction")
                forecasts.append(prediction)
                state = state.extend([actual])
            order = (row["p"], row["d"], row["q"])
            predictions["ARIMA"] = (forecasts, f"order={order}")
        except (ValueError, np.linalg.LinAlgError) as error:
            row["status"] = f"forecast failed: {error}"
    return predictions, candidates


def evaluate(actual, predicted):
    errors = actual - predicted
    lag = min(10, len(errors) // 5)
    p_value = statistic = np.nan
    if lag and np.ptp(errors) > 0:
        result = acorr_ljungbox(errors, lags=[lag], return_df=True).iloc[0]
        statistic, p_value = result["lb_stat"], result["lb_pvalue"]
    return {"mae": mean_absolute_error(actual, predicted),
            "rmse": np.sqrt(mean_squared_error(actual, predicted)),
            "ljung_box_lag": lag, "ljung_box_statistic": statistic,
            "ljung_box_p": p_value}
