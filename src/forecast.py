"""
6-month forecast (April–September of current year) for border crossings
by country group and direction. Uses multiple models; writes forecast chart
and forecast_numbers.txt with results from each model.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import statsmodels.api as sm


def _country_group_class(country_group: str) -> str:
    if pd.isna(country_group):
        return "3rd countries"
    s = str(country_group).lower()
    if "schengen" in s or "el/emp/ch" in s:
        return "Schengen/EL/EMP/CH"
    return "3rd countries"


def _monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to monthly counts per (year, month, direction, group_class)."""
    df = df.copy()
    df["group_class"] = df["country_group"].apply(_country_group_class)
    df["crossing_date"] = pd.to_datetime(df["crossing_date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["crossing_date"])
    df["year"] = df["crossing_date"].dt.year
    df["month"] = df["crossing_date"].dt.month
    agg = (
        df.groupby(["year", "month", "direction", "group_class"])
        .size()
        .reset_index(name="count")
    )
    agg["period"] = agg["year"].astype(str) + "-" + agg["month"].astype(str).str.zfill(2)
    agg["period_dt"] = pd.to_datetime(agg["year"].astype(str) + "-" + agg["month"].astype(str).str.zfill(2) + "-01")
    return agg


def _forecast_holtwinters(
    ts: pd.Series, steps: int, fcast_index: pd.DatetimeIndex
) -> np.ndarray:
    """Holt-Winters exponential smoothing (additive trend + additive seasonal, 12 months)."""
    model = ExponentialSmoothing(
        ts,
        seasonal_periods=12,
        trend="add",
        seasonal="add",
        initialization_method="estimated",
    )
    fitted = model.fit(optimized=True)
    return np.maximum(fitted.forecast(steps).values, 0.0)


def _forecast_seasonal_naive(
    ts: pd.Series, steps: int, fcast_index: pd.DatetimeIndex
) -> np.ndarray:
    """Seasonal naive: forecast = same month from previous year (or last available)."""
    out = np.zeros(steps)
    for i, dt in enumerate(fcast_index):
        month = dt.month
        # Same month in prior years (most recent first)
        same_month = ts[ts.index.month == month]
        if len(same_month) > 0:
            out[i] = max(0, same_month.iloc[-1])
        else:
            out[i] = max(0, ts.iloc[-1]) if len(ts) > 0 else 0
    return out


def _forecast_linear(
    ts: pd.Series, steps: int, fcast_index: pd.DatetimeIndex
) -> np.ndarray:
    """Linear regression: count ~ time + month (1–12) for trend and seasonality."""
    if len(ts) < 24:
        return _forecast_seasonal_naive(ts, steps, fcast_index)
    ts_df = ts.reset_index()
    ts_df.columns = ["period_dt", "count"]
    ts_df["time"] = np.arange(len(ts_df))
    ts_df["month"] = ts_df["period_dt"].dt.month
    y = ts_df["count"].values
    X = ts_df[["time", "month"]]
    X = sm.add_constant(X)
    res = OLS(y, X).fit()
    # Predict: time continues, month from fcast_index
    last_time = ts_df["time"].iloc[-1]
    out = np.zeros(steps)
    for i, dt in enumerate(fcast_index):
        row = np.array([[1, last_time + 1 + i, dt.month]])
        out[i] = max(0, res.predict(row)[0])
    return out


# Model name -> (description, forecast function, filename stem for PNG)
FORECAST_MODELS = [
    (
        "Holt-Winters",
        "Holt-Winters exponential smoothing (additive trend, additive seasonal, 12-month period).",
        _forecast_holtwinters,
        "forecast_holtwinters",
    ),
    (
        "Seasonal naive",
        "Seasonal naive: forecast for month M = observed value for month M from previous year.",
        _forecast_seasonal_naive,
        "forecast_seasonal_naive",
    ),
    (
        "Linear regression",
        "Linear regression: count ~ time + month (trend + seasonal).",
        _forecast_linear,
        "forecast_linear_regression",
    ),
]


def _plot_forecast_model(
    res_df: pd.DataFrame,
    model_name: str,
    current_year: int,
    output_path: Path,
) -> None:
    """Draw one chart: historical + forecast for one model; title includes model name."""
    fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
    colors = {"inbound": "#1B2A4A", "outbound": "#FF8C00"}

    for (group_class, direction), sub in res_df.groupby(["group_class", "direction"]):
        sub = sub.sort_values("period_dt")
        hist = sub[~sub["is_forecast"]]
        fcast = sub[sub["is_forecast"]]
        label = f"{group_class} – {direction.capitalize()}"
        c = colors[direction]
        ax.plot(hist["period_dt"], hist["count"], color=c, label=label, linewidth=2)
        if len(fcast) > 0:
            ax.plot(
                fcast["period_dt"],
                fcast["count"],
                color=c,
                linestyle="--",
                linewidth=2,
                label=f"{label} (forecast)",
            )

    ax.axvspan(
        pd.Timestamp(current_year, 4, 1),
        pd.Timestamp(current_year, 9, 30),
        alpha=0.1,
        color="gray",
        label="Forecast period",
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Persons (monthly)")
    ax.set_title(
        f"Estonia Border Crossings – 6-Month Forecast (Apr–Sep {current_year}) — Model: {model_name}"
    )
    ax.legend(loc="upper right", fontsize=8)
    ax.set_ylim(0, None)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def run_forecast(
    df: pd.DataFrame,
    output_dir: Path | None = None,
    forecast_txt_path: Path | None = None,
) -> list[Path]:
    """
    Build 6-month forecast (Apr–Sep of current year) per (group_class, direction)
    with multiple models. Writes forecast_numbers.txt and one PNG per model.
    Returns paths to the written PNG files.
    """
    base = Path(__file__).resolve().parent.parent / "outputs"
    if output_dir is None:
        output_dir = base
    if forecast_txt_path is None:
        forecast_txt_path = base / "forecast_numbers.txt"
    output_dir.mkdir(parents=True, exist_ok=True)

    monthly = _monthly_totals(df)
    current_year = pd.Timestamp.now().year
    steps = 6
    fcast_index = pd.date_range(
        start=pd.Timestamp(current_year, 4, 1),
        periods=steps,
        freq="MS",
    )

    # Run all models; collect forecast rows (for txt) and full series (for charts) per model
    forecasts_by_model: dict[str, list[dict]] = {}
    results_by_model: dict[str, list[dict]] = {}
    for name, _d, _f, _stem in FORECAST_MODELS:
        forecasts_by_model[name] = []
        results_by_model[name] = []

    for (group_class, direction), sub in monthly.groupby(["group_class", "direction"]):
        sub = sub.sort_values("period_dt")
        ts = sub.set_index("period_dt")["count"].resample("MS").sum()
        if len(ts) < 12:
            continue

        for model_name, _desc, forecast_func, _stem in FORECAST_MODELS:
            try:
                fcast_vals = forecast_func(ts, steps, fcast_index)
            except Exception:
                fcast_vals = np.zeros(steps)
            for dt, val in zip(fcast_index, fcast_vals):
                count_val = max(0, val)
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
                        "count": val,
                        "is_forecast": False,
                    }
                )

    # Write forecast numbers to text file (all models)
    _write_forecast_txt(forecasts_by_model, current_year, forecast_txt_path)

    # One PNG per model, with model name in the chart title
    written_paths = []
    for model_name, _desc, _func, stem in FORECAST_MODELS:
        res_df = pd.DataFrame(results_by_model[model_name])
        if res_df.empty:
            continue
        png_path = output_dir / f"{stem}.png"
        _plot_forecast_model(res_df, model_name, current_year, png_path)
        written_paths.append(png_path)

    return written_paths


def _write_forecast_txt(
    forecasts_by_model: dict[str, list[dict]],
    current_year: int,
    txt_path: Path,
) -> None:
    """Write forecast numbers for each model to a plain-text file."""
    lines = [
        "Estonia Border Crossings – 6-Month Forecast (April–September " + str(current_year) + ")",
        "=" * 70,
        "",
        "Several forecasting models are used; results are shown separately below so you",
        "can compare different methods.",
        "",
    ]
    for model_name, description, _, _ in FORECAST_MODELS:
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

