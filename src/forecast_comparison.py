"""
Compare original vs improved forecast outputs and visualize differences.

Inputs:
- outputs/forecast_numbers.txt
- outputs/forecast_numbers_improved.txt
- outputs/validation_metrics.txt

Outputs:
- outputs/forecast_comparison.txt
- outputs/forecast_comparison.png
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROW_PATTERN = re.compile(
    r"^\s*(\d{4}-\d{2})\s+(Schengen/EL/EMP/CH|3rd countries)\s+(inbound|outbound)\s+([\d,]+)\s*$"
)


def _parse_forecast_numbers(path: Path) -> pd.DataFrame:
    """Parse forecast_numbers(.txt) style file into a normalized table."""
    if not path.exists():
        return pd.DataFrame(columns=["model", "period", "country_group", "direction", "count"])

    current_model = ""
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("MODEL:"):
            current_model = line.split("MODEL:", 1)[1].strip()
            continue
        m = ROW_PATTERN.match(line)
        if not m or not current_model:
            continue
        period, group, direction, count_s = m.groups()
        rows.append(
            {
                "model": current_model,
                "period": period,
                "country_group": group,
                "direction": direction,
                "count": int(count_s.replace(",", "")),
            }
        )
    return pd.DataFrame(rows)


def _parse_validation_metrics(path: Path) -> pd.DataFrame:
    """Parse validation_metrics.txt rows into a DataFrame."""
    if not path.exists():
        return pd.DataFrame(
            columns=["model", "group_class", "direction", "rmse", "mae", "mape", "n_obs", "n_folds"]
        )

    pattern = re.compile(
        r"^(Holt-Winters|Seasonal naive|Linear regression)\s+"
        r"(Schengen/EL/EMP/CH|3rd countries|ALL)\s+"
        r"(inbound|outbound|ALL)\s+"
        r"RMSE=\s*([0-9.]+)\s+MAE=\s*([0-9.]+)\s+MAPE=\s*([0-9.a-zA-Z]+)\s+n=\s*(\d+)\s+folds=\s*(\d+)\s*$"
    )
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        model, group_class, direction, rmse, mae, mape, n_obs, n_folds = m.groups()
        rows.append(
            {
                "model": model,
                "group_class": group_class,
                "direction": direction,
                "rmse": float(rmse),
                "mae": float(mae),
                "mape": np.nan if mape.lower() == "nan" else float(mape),
                "n_obs": int(n_obs),
                "n_folds": int(n_folds),
            }
        )
    return pd.DataFrame(rows)


def _build_comparison(old_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Build row-wise old vs new comparison with absolute and percent differences."""
    merged = old_df.merge(
        new_df,
        on=["model", "period", "country_group", "direction"],
        how="outer",
        suffixes=("_old", "_new"),
    )
    merged["count_old"] = merged["count_old"].fillna(0).astype(float)
    merged["count_new"] = merged["count_new"].fillna(0).astype(float)
    merged["abs_diff"] = (merged["count_new"] - merged["count_old"]).abs()
    merged["pct_diff"] = np.where(
        merged["count_old"] != 0,
        (merged["count_new"] - merged["count_old"]) / merged["count_old"] * 100.0,
        np.nan,
    )
    return merged.sort_values(["model", "period", "country_group", "direction"]).reset_index(drop=True)


def _format_metrics_table(metrics_df: pd.DataFrame) -> list[str]:
    """Format validation metrics section for the text report."""
    lines = [
        "VALIDATION METRICS (improved pipeline only)",
        "-" * 90,
        "  model               group_class             direction       RMSE        MAE       MAPE(%)   n_obs  folds",
        "  " + "-" * 88,
    ]
    if metrics_df.empty:
        lines.append("  No validation metrics found.")
        return lines
    for _, r in metrics_df.sort_values(["model", "group_class", "direction"]).iterrows():
        mape_s = "nan" if pd.isna(r["mape"]) else f"{float(r['mape']):.2f}"
        lines.append(
            f"  {r['model']:<18}  {r['group_class']:<22}  {r['direction']:<10}  "
            f"{float(r['rmse']):>9.2f}  {float(r['mae']):>9.2f}  {mape_s:>9}  {int(r['n_obs']):>5}  {int(r['n_folds']):>5}"
        )
    return lines


def _best_model_summary(metrics_df: pd.DataFrame) -> str:
    """Pick best model based on overall lowest MAPE, then MAE."""
    overall = metrics_df[(metrics_df["group_class"] == "ALL") & (metrics_df["direction"] == "ALL")].copy()
    if overall.empty:
        return "No validation metrics were available to determine the best model."
    overall["mape_rank"] = overall["mape"].fillna(np.inf)
    overall = overall.sort_values(["mape_rank", "mae", "rmse"])
    best = overall.iloc[0]
    mape_s = "nan" if pd.isna(best["mape"]) else f"{float(best['mape']):.2f}%"
    return (
        f"Best model by validation is {best['model']} "
        f"(overall MAPE={mape_s}, MAE={float(best['mae']):.2f}, RMSE={float(best['rmse']):.2f})."
    )


def _difference_summary(cmp_df: pd.DataFrame) -> str:
    """Summarize how much improved forecasts differ from original."""
    if cmp_df.empty:
        return "No comparable forecast rows were found between old and new files."
    mean_abs = float(cmp_df["abs_diff"].mean())
    mean_pct = float(cmp_df["pct_diff"].abs().dropna().mean()) if cmp_df["pct_diff"].notna().any() else float("nan")
    max_abs_row = cmp_df.loc[cmp_df["abs_diff"].idxmax()]
    mean_pct_s = "nan" if np.isnan(mean_pct) else f"{mean_pct:.2f}%"
    return (
        f"Across {len(cmp_df)} rows, the average absolute change is {mean_abs:.2f} persons "
        f"and average absolute percent change is {mean_pct_s}. Largest row change is "
        f"{int(max_abs_row['abs_diff']):,} persons for {max_abs_row['model']} / "
        f"{max_abs_row['country_group']} / {max_abs_row['direction']} / {max_abs_row['period']}."
    )


def _write_comparison_report(cmp_df: pd.DataFrame, metrics_df: pd.DataFrame, output_path: Path) -> None:
    """Write plain-text comparison report."""
    lines = [
        "Forecast comparison report: original vs improved",
        "=" * 90,
        "",
        "SIDE-BY-SIDE FORECAST NUMBERS",
        "-" * 90,
        "  model               period   country_group            direction   old        new        abs_diff     pct_diff",
        "  " + "-" * 88,
    ]
    if cmp_df.empty:
        lines.append("  No comparable rows.")
    else:
        for _, r in cmp_df.iterrows():
            pct_s = "nan" if pd.isna(r["pct_diff"]) else f"{float(r['pct_diff']):.2f}%"
            lines.append(
                f"  {r['model']:<18}  {r['period']:<7}  {r['country_group']:<22}  {r['direction']:<8}  "
                f"{int(r['count_old']):>8,}  {int(r['count_new']):>8,}  {int(r['abs_diff']):>10,}  {pct_s:>10}"
            )

    lines.extend(["", ""] + _format_metrics_table(metrics_df))
    lines.extend(
        [
            "",
            "",
            "PLAIN-LANGUAGE SUMMARY",
            "-" * 90,
            _best_model_summary(metrics_df),
            _difference_summary(cmp_df),
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _plot_comparison(cmp_df: pd.DataFrame, output_path: Path) -> None:
    """Create side-by-side old vs new line chart per model/group/direction."""
    if cmp_df.empty:
        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
        ax.text(0.5, 0.5, "No comparison rows available", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
        return

    periods = sorted(cmp_df["period"].unique())
    combos = sorted({(g, d) for g, d in cmp_df[["country_group", "direction"]].itertuples(index=False, name=None)})
    models = ["Holt-Winters", "Seasonal naive", "Linear regression"]

    fig, axes = plt.subplots(len(models), len(combos), figsize=(20, 12), dpi=150, sharex=True)
    if len(models) == 1 and len(combos) == 1:
        axes = np.array([[axes]])
    elif len(models) == 1:
        axes = np.array([axes])
    elif len(combos) == 1:
        axes = np.array([[a] for a in axes])

    x = np.arange(len(periods))
    for i, model in enumerate(models):
        for j, (group, direction) in enumerate(combos):
            ax = axes[i, j]
            sub = cmp_df[
                (cmp_df["model"] == model)
                & (cmp_df["country_group"] == group)
                & (cmp_df["direction"] == direction)
            ].copy()
            sub = sub.set_index("period").reindex(periods)
            ax.plot(x, sub["count_old"].values, marker="o", linewidth=1.8, label="Original")
            ax.plot(x, sub["count_new"].values, marker="o", linewidth=1.8, linestyle="--", label="Improved")
            ax.set_title(f"{model}\n{group} - {direction}", fontsize=9)
            ax.grid(alpha=0.25)
            if i == len(models) - 1:
                ax.set_xticks(x)
                ax.set_xticklabels(periods, rotation=45, ha="right", fontsize=8)
            else:
                ax.set_xticks(x)
                ax.set_xticklabels([])
            if j == 0:
                ax.set_ylabel("Persons")
            if i == 0 and j == 0:
                ax.legend(fontsize=8)

    fig.suptitle("Forecast comparison: Original vs Improved (Apr-Sep)", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def run_forecast_comparison(
    output_dir: Path | None = None,
    old_forecast_path: Path | None = None,
    new_forecast_path: Path | None = None,
    validation_metrics_path: Path | None = None,
    report_path: Path | None = None,
    chart_path: Path | None = None,
) -> tuple[Path, Path]:
    """Run full comparison workflow and return report/chart paths."""
    base = Path(__file__).resolve().parent.parent / "outputs"
    if output_dir is None:
        output_dir = base
    if old_forecast_path is None:
        old_forecast_path = output_dir / "forecast_numbers.txt"
    if new_forecast_path is None:
        new_forecast_path = output_dir / "forecast_numbers_improved.txt"
    if validation_metrics_path is None:
        validation_metrics_path = output_dir / "validation_metrics.txt"
    if report_path is None:
        report_path = output_dir / "forecast_comparison.txt"
    if chart_path is None:
        chart_path = output_dir / "forecast_comparison.png"

    output_dir.mkdir(parents=True, exist_ok=True)

    old_df = _parse_forecast_numbers(old_forecast_path)
    new_df = _parse_forecast_numbers(new_forecast_path)
    metrics_df = _parse_validation_metrics(validation_metrics_path)
    cmp_df = _build_comparison(old_df, new_df)

    _write_comparison_report(cmp_df, metrics_df, report_path)
    _plot_comparison(cmp_df, chart_path)
    return report_path, chart_path


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    out = base / "outputs"
    report, chart = run_forecast_comparison(output_dir=out)
    print(f"Written {report}")
    print(f"Written {chart}")
