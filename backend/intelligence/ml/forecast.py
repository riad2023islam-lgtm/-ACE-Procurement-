"""Demand forecasting (SRS FR9, FR14, NFR10).

Pure Python/NumPy/scikit-learn: no Django imports, so it can be unit tested
and reused from a notebook.

Approach
--------
* Input: a list of monthly consumption totals (oldest -> newest).
* Fewer than MIN_HISTORY months (cold start): simple average of the most recent
  months, labelled low confidence (SRS section 4.4, FR14).
* Otherwise two candidate models are compared with a rolling-origin backtest
  and the one with the lower MAE is used to predict the next month:
    - moving_average : mean of the last 3 months
    - linear_trend   : scikit-learn LinearRegression on the month index
* The error range is the backtest RMSE of the chosen model, scaled by Z_80 to
  give an approximate 80% interval (FR9: "display the forecast with an error range").
"""
from dataclasses import dataclass, asdict
from typing import Optional, Sequence

import numpy as np
from sklearn.linear_model import LinearRegression

MIN_HISTORY = 6          # months of history needed before the ML models are trusted
MA_WINDOW = 3            # window for the moving-average model
Z_80 = 1.28              # z-score for an ~80% interval


@dataclass
class ForecastResult:
    forecast: float
    lower: float
    upper: float
    model: str                 # moving_average | linear_trend | simple_average_fallback
    confidence: str            # "normal" | "low"
    mae: Optional[float]       # backtest MAE (None for the fallback)
    history_months: int

    def as_dict(self):
        return asdict(self)


def _moving_average(history: np.ndarray) -> float:
    return float(np.mean(history[-MA_WINDOW:]))


def _linear_trend(history: np.ndarray) -> float:
    x = np.arange(len(history)).reshape(-1, 1)
    model = LinearRegression().fit(x, history)
    return float(model.predict(np.array([[len(history)]]))[0])


_CANDIDATES = {
    "moving_average": _moving_average,
    "linear_trend": _linear_trend,
}


def backtest(series: Sequence[float]) -> dict:
    """Rolling-origin backtest: predict each month from the months before it.

    Returns {model_name: list_of_errors} where error = actual - predicted.
    """
    y = np.asarray(series, dtype=float)
    start = max(3, len(y) // 2)
    errors = {name: [] for name in _CANDIDATES}
    for t in range(start, len(y)):
        for name, fn in _CANDIDATES.items():
            errors[name].append(y[t] - fn(y[:t]))
    return errors


def forecast_next_month(series: Sequence[float]) -> ForecastResult:
    y = np.asarray(series, dtype=float)
    n = len(y)
    if n == 0:
        raise ValueError("At least one month of consumption history is required.")

    # Cold start / insufficient history -> simple average, low confidence.
    if n < MIN_HISTORY:
        recent = y[-MA_WINDOW:]
        value = float(recent.mean())
        spread = float(recent.std()) if len(recent) > 1 else 0.0
        return ForecastResult(
            forecast=round(value, 1),
            lower=round(max(value - spread, 0.0), 1),
            upper=round(value + spread, 1),
            model="simple_average_fallback",
            confidence="low",
            mae=None,
            history_months=n,
        )

    errors = backtest(y)
    mae = {k: float(np.mean(np.abs(v))) for k, v in errors.items()}
    best = min(mae, key=mae.get)
    rmse = float(np.sqrt(np.mean(np.square(errors[best]))))

    value = max(_CANDIDATES[best](y), 0.0)
    half_width = Z_80 * rmse
    return ForecastResult(
        forecast=round(value, 1),
        lower=round(max(value - half_width, 0.0), 1),
        upper=round(value + half_width, 1),
        model=best,
        confidence="normal",
        mae=round(mae[best], 1),
        history_months=n,
    )
