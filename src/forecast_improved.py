"""
Improved 6-month forecast pipeline with walk-forward validation.

Enhancements vs src.forecast:
- Walk-forward validation (6-month horizon, 6-month step, >=24 months first train)
- Metrics per model and per (group_class, direction): RMSE, MAE, MAPE
- Improved linear regression with one-hot encoded month dummies
- Improved seasonal naive: average of same-month values across all prior years
- Holt-Winters fallback to heuristic initialization when estimated fails
- Writes forecast_numbers_improved.txt and validation_metrics.txt
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import OLS
from statsmodels.tsa.holtwinters import ExponentialSmoothing

try:
    from src.forecast import _monthly_totals, _plot_forecast_model
except ModuleNotFoundError:
    from forecast import _monthly_totals, _plot_forecast_model


ForecastFunc = Callable[[pd.Series, int, pd.DatetimeIndex], np.ndarray]


def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """MAPE (%) over non-zero actuals only; returns NaN when undefined."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = y_true != 0
    if not np.any(mask):
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute RMSE, MAE, MAPE for aligned arrays."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    mape = _safe_mape(y_true, y_pred)
    return {"rmse": rmse, "mae": mae, "mape": mape}


def _forecast_holtwinters_improved(
    ts: pd.Series, steps: int, fcast_index: pd.DatetimeIndex
) -> np.ndarray:
    """Holt-Winters with fallback from estimated init to heuristic init."""
    try:
        model = ExponentialSmoothing(
            ts,
            seasonal_periods=12,
            trend="add",
            seasonal="add",
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True)
    except Exception:
        model = ExponentialSmoothing(
            ts,
            seasonal_periods=12,
            trend="add",
            seasonal="add",
            initialization_method="heuristic",
        )
        fitted = model.fit(optimized=True)
    return np.maximum(fitted.forecast(steps).values, 0.0)


def _forecast_seasonal_naive_improved(
    ts: pd.Series, steps: int, fcast_index: pd.DatetimeIndex
) -> np.ndarray:
    """Seasonal naive using average of all historical same-month observations."""
    out = np.zeros(steps, dtype=float)
    for i, dt in enumerate(fcast_index):
        same_month = ts[ts.index.month == dt.month]
        if len(same_month) > 0:
            out[i] = max(0.0, float(same_month.mean()))
        elif len(ts) > 0:
            out[i] = max(0.0, float(ts.iloc[-1]))
        else:
            out[i] = 0.0
    return out


def _forecast_linear_improved(
    ts: pd.Series, steps: int, fcast_index: pd.DatetimeIndex
) -> np.ndarray:
    """
    Linear regression with proper seasonality encoding.

    Model: count ~ time + month_dummies (month treated as categorical).
    Falls back to improved seasonal naive if series is short.
    """
    if len(ts) < 24:
        return _forecast_seasonal_naive_improved(ts, steps, fcast_index)

    ts_df = ts.reset_index()
    ts_df.columns = ["period_dt", "count"]
    ts_df["time"] = np.arange(len(ts_df))
    ts_df["month"] = ts_df["period_dt"].dt.month.astype(int)

    month_cat = pd.Categorical(ts_df["month"], categories=list(range(1, 13)))
    month_dummies = pd.get_dummies(month_cat, prefix="m", drop_first=True, dtype=float)
    X = pd.concat([ts_df[["time"]], month_dummies], axis=1)
    X = sm.add_constant(X)
    y = ts_df["count"].astype(float).values
    res = OLS(y, X).fit()

    last_time = int(ts_df["time"].iloc[-1])
    pred_rows: list[dict[str, float]] = []
    for i, dt in enumerate(fcast_index):
        row: dict[str, float] = {"const": 1.0, "time": float(last_time + 1 + i)}
        for m in range(2, 13):
            row[f"m_{m}"] = 1.0 if dt.month == m else 0.0
        pred_rows.append(row)
    X_future = pd.DataFrame(pred_rows)[X.columns]
    pred = res.predict(X_future).values
    return np.maximum(pred, 0.0)


IMPROVED_MODELS: list[tuple[str, str, ForecastFunc, str]] = [
    (
        "Holt-Winters",
        "Holt-Winters exponential smoothing (additive trend, additive seasonal, 12-month period) with heuristic fallback.",
        _forecast_holtwinters_improved,
        "forecast_holtwinters_improved",
    ),
    (
        "Seasonal naive",
        "Seasonal naive: forecast for month M = average of all historical values observed in month M.",
        _forecast_seasonal_naive_improved,
        "forecast_seasonal_naive_improved",
    ),
    (
        "Linear regression",
        "Linear regression: count ~ time + month dummies (categorical seasonality).",
        _forecast_linear_improved,
        "forecast_linear_regression_improved",
    ),
]


def _walk_forward_predictions(
    ts: pd.Series,
    model_name: str,
    forecast_func: ForecastFunc,
    steps: int = 6,
    min_train: int = 24,
    min_folds: int = 3,
) -> pd.DataFrame:
    """Run walk-forward validation and return fold-level predicted vs actual rows."""
    ts = ts.sort_index().astype(float)
    rows: list[dict] = []

    n = len(ts)
    if n < min_train + steps:
        return pd.DataFrame(rows)

    train_end = min_train
    fold = 1
    while train_end + steps <= n:
        train = ts.iloc[:train_end]
        test = ts.iloc[train_end : train_end + steps]
        fcast_index = test.index
        try:
            pred = forecast_func(train, steps, fcast_index)
        except Exception:
            pred = np.zeros(steps, dtype=float)
        pred = np.maximum(np.asarray(pred, dtype=float), 0.0)
        for dt, actual, predicted in zip(fcast_index, test.values, pred):
            rows.append(
                {
                    "model": model_name,
                    "fold": fold,
                    "period_dt": dt,
                    "actual": float(actual),
                    "predicted": float(predicted),
                }
            )
        fold += 1
        train_end += steps

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if df["fold"].nunique() < min_folds:
        return pd.DataFrame([])
    return df


def _build_validation_and_metrics(
    monthly: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build all validation rows and metrics for improved models."""
    validation_rows: list[pd.DataFrame] = []

    for (group_class, direction), sub in monthly.groupby(["group_class", "direction"]):
        sub = sub.sort_values("period_dt")
        ts = sub.set_index("period_dt")["count"].resample("MS").sum()
        if len(ts) < 30:
            continue

        for model_name, _desc, model_func, _stem in IMPROVED_MODELS:
            wfv = _walk_forward_predictions(ts, model_name, model_func)
            if wfv.empty:
                continue
            wfv["group_class"] = group_class
            wfv["direction"] = direction
            validation_rows.append(wfv)

    validation_df = pd.concat(validation_rows, ignore_index=True) if validation_rows else pd.DataFrame()
    if validation_df.empty:
        return validation_df, pd.DataFrame()

    metric_rows: list[dict] = []
    for (model_name, group_class, direction), sub in validation_df.groupby(
        ["model", "group_class", "direction"]
    ):
        vals = _metrics(sub["actual"].values, sub["predicted"].values)
        metric_rows.append(
            {
                "model": model_name,
                "group_class": group_class,
                "direction": direction,
                "rmse": vals["rmse"],
                "mae": vals["mae"],
                "mape": vals["mape"],
                "n_obs": int(len(sub)),
                "n_folds": int(sub["fold"].nunique()),
            }
        )

    metrics_df = pd.DataFrame(metric_rows).sort_values(["model", "group_class", "direction"]).reset_index(drop=True)
    overall_rows: list[dict] = []
    for model_name, sub in validation_df.groupby("model"):
        vals = _metrics(sub["actual"].values, sub["predicted"].values)
        overall_rows.append(
            {
                "model": model_name,
                "group_class": "ALL",
                "direction": "ALL",
                "rmse": vals["rmse"],
                "mae": vals["mae"],
                "mape": vals["mape"],
                "n_obs": int(len(sub)),
                "n_folds": int(sub["fold"].nunique()),
            }
        )
    metrics_df = pd.concat([metrics_df, pd.DataFrame(overall_rows)], ignore_index=True)
    return validation_df, metrics_df


def _write_validation_metrics_txt(metrics_df: pd.DataFrame, output_path: Path) -> None:
    """Write validation metrics table to validation_metrics.txt."""
    lines = [
        "Walk-forward validation metrics (6-month horizon, 6-month step)",
        "=" * 78,
        "",
        "Columns: model, group_class, direction, RMSE, MAE, MAPE(%), n_obs, n_folds",
        "",
    ]
    if metrics_df.empty:
        lines.append("No validation metrics available.")
    else:
        for _, r in metrics_df.sort_values(["model", "group_class", "direction"]).iterrows():
            mape_s = "nan" if pd.isna(r["mape"]) else f"{float(r['mape']):.2f}"
            lines.append(
                f"{r['model']:<18}  {r['group_class']:<22}  {r['direction']:<8}  "
                f"RMSE={float(r['rmse']):>10.2f}  MAE={float(r['mae']):>10.2f}  "
                f"MAPE={mape_s:>8}  n={int(r['n_obs']):>3}  folds={int(r['n_folds']):>2}"
            )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_forecast_txt_improved(
    forecasts_by_model: dict[str, list[dict]],
    current_year: int,
    txt_path: Path,
    metrics_df: pd.DataFrame,
) -> None:
    """Write improved forecast text with validation summary section at top."""
    lines = [
        "Estonia Border Crossings – 6-Month Forecast (April–September " + str(current_year) + ")",
        "=" * 70,
        "",
        "Validation summary (walk-forward, 6-month horizon):",
        "-" * 70,
    ]

    if metrics_df.empty:
        lines.append("  No validation metrics available.")
    else:
        overall = metrics_df[(metrics_df["group_class"] == "ALL") & (metrics_df["direction"] == "ALL")]
        for model_name, *_rest in IMPROVED_MODELS:
            sub = overall[overall["model"] == model_name]
            if sub.empty:
                lines.append(f"  {model_name:<18}  RMSE=NA  MAE=NA  MAPE=NA")
                continue
            r = sub.iloc[0]
            mape_s = "nan" if pd.isna(r["mape"]) else f"{float(r['mape']):.2f}%"
            lines.append(
                f"  {model_name:<18}  RMSE={float(r['rmse']):.2f}  "
                f"MAE={float(r['mae']):.2f}  MAPE={mape_s}"
            )

    lines.extend(
        [
            "",
            "Several forecasting models are used; results are shown separately below so you",
            "can compare different methods.",
            "",
        ]
    )

    for model_name, description, _func, _stem in IMPROVED_MODELS:
        forecast_rows = forecasts_by_model.get(model_name, [])
        lines.append("")
        lines.append("MODEL: " + model_name)
        lines.append("-" * 70)
        lines.append(description)
        lines.append("")
        if not forecast_rows:
            lines.append("  (No forecast rows generated.)")
        else:
            lines.append("FORECAST NUMBERS (monthly persons):")
            lines.append("-" * 70)
            for r in forecast_rows:
                lines.append(
                    f"  {r['period']}  {r['country_group']:<22}  {r['direction']:<8}  {r['count']:>10,}"
                )
            total_inbound = sum(r["count"] for r in forecast_rows if r["direction"] == "inbound")
            total_outbound = sum(r["count"] for r in forecast_rows if r["direction"] == "outbound")
            total_both = total_inbound + total_outbound
            lines.append("")
            lines.append("TOTALS (April–September " + str(current_year) + ", all country groups):")
            lines.append("-" * 70)
            lines.append(f"  Inbound:   {int(total_inbound):>12,}")
            lines.append(f"  Outbound: {int(total_outbound):>12,}")
            lines.append(f"  Total:    {int(total_both):>12,}")
        lines.append("")

    lines.append("=" * 70)
    txt_path.write_text("\n".join(lines), encoding="utf-8")


def run_forecast_improved(
    df: pd.DataFrame,
    output_dir: Path | None = None,
    forecast_txt_path: Path | None = None,
    validation_txt_path: Path | None = None,
) -> list[Path]:
    """
    Run improved walk-forward validated pipeline and final 6-month forecast.

    Writes:
    - forecast_numbers_improved.txt
    - validation_metrics.txt
    - one improved PNG per model
    """
    base = Path(__file__).resolve().parent.parent / "outputs"
    if output_dir is None:
        output_dir = base
    if forecast_txt_path is None:
        forecast_txt_path = base / "forecast_numbers_improved.txt"
    if validation_txt_path is None:
        validation_txt_path = base / "validation_metrics.txt"
    output_dir.mkdir(parents=True, exist_ok=True)

    monthly = _monthly_totals(df)
    _validation_df, metrics_df = _build_validation_and_metrics(monthly)
    _write_validation_metrics_txt(metrics_df, validation_txt_path)

    current_year = pd.Timestamp.now().year
    steps = 6
    fcast_index = pd.date_range(
        start=pd.Timestamp(current_year, 4, 1),
        periods=steps,
        freq="MS",
    )

    forecasts_by_model: dict[str, list[dict]] = {name: [] for name, *_ in IMPROVED_MODELS}
    results_by_model: dict[str, list[dict]] = {name: [] for name, *_ in IMPROVED_MODELS}

    for (group_class, direction), sub in monthly.groupby(["group_class", "direction"]):
        sub = sub.sort_values("period_dt")
        ts = sub.set_index("period_dt")["count"].resample("MS").sum()
        if len(ts) < 12:
            continue

        for model_name, _desc, forecast_func, _stem in IMPROVED_MODELS:
            try:
                fcast_vals = forecast_func(ts, steps, fcast_index)
            except Exception:
                fcast_vals = np.zeros(steps)
            for dt, val in zip(fcast_index, fcast_vals):
                count_val = max(0.0, float(val))
                forecasts_by_model[model_name].append(
                    {
                        "period": dt.strftime("%Y-%m"),
                        "country_group": group_class,
                        "direction": direction,
                        "count": int(round(count_val)),
                    }
                )
                results_by_model[model_name].append(
                    {
                        "group_class": group_class,
                        "direction": direction,
                        "period_dt": dt,
                        "count": count_val,
                        "is_forecast": True,
                    }
                )
            for dt, val in ts.items():
                results_by_model[model_name].append(
                    {
                        "group_class": group_class,
                        "direction": direction,
                        "period_dt": dt,
                        "count": float(val),
                        "is_forecast": False,
                    }
                )

    _write_forecast_txt_improved(forecasts_by_model, current_year, forecast_txt_path, metrics_df)

    written_paths: list[Path] = []
    for model_name, _desc, _func, stem in IMPROVED_MODELS:
        res_df = pd.DataFrame(results_by_model[model_name])
        if res_df.empty:
            continue
        png_path = output_dir / f"{stem}.png"
        _plot_forecast_model(res_df, model_name, current_year, png_path)
        written_paths.append(png_path)
    return written_paths


if __name__ == "__main__":
    try:
        from src.data_loader import load_border_crossings
    except ModuleNotFoundError:
        from data_loader import load_border_crossings

    base = Path(__file__).resolve().parent.parent
    outputs = base / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    data = load_border_crossings(base / "data" / "raw")
    pngs = run_forecast_improved(
        data,
        output_dir=outputs,
        forecast_txt_path=outputs / "forecast_numbers_improved.txt",
        validation_txt_path=outputs / "validation_metrics.txt",
    )
    for p in pngs:
        print(f"Written {p}")
    print(f"Written {outputs / 'forecast_numbers_improved.txt'}")
    print(f"Written {outputs / 'validation_metrics.txt'}")
