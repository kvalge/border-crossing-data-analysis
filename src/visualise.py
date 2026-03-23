"""
Create stacked bar chart of border crossings by year and country group.
Two bars per year (Schengen/EL/EMP/CH, 3rd countries), each stacked by inbound/outbound.
Writes outputs/border_crossings.png.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import ScalarFormatter


def _country_group_class(country_group: str) -> str:
    """Schengen/EL/EMP/CH if value contains those (case-insensitive), else 3rd countries."""
    if pd.isna(country_group):
        return "3rd countries"
    s = str(country_group).lower()
    if "schengen" in s or "el/emp/ch" in s:
        return "Schengen/EL/EMP/CH"
    return "3rd countries"


def _format_count(val: float) -> str:
    """Abbreviate count for display (e.g. 1.2M, 840K)."""
    if val >= 1e6:
        return f"{val / 1e6:.1f}M"
    if val >= 1e3:
        return f"{val / 1e3:.0f}K"
    return str(int(val))


def create_chart(df: pd.DataFrame, output_path: Path | None = None) -> None:
    """
    Produce stacked bar chart: two bars per year (Schengen/EL/EMP/CH, 3rd countries),
    each bar stacked with inbound (bottom) and outbound (top). Segment counts inside
    bars, total on top. No x-axis label.
    """
    if output_path is None:
        output_path = (
            Path(__file__).resolve().parent.parent / "outputs" / "border_crossings.png"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    df["group_class"] = df["country_group"].apply(_country_group_class)

    agg = (
        df.groupby(["year", "direction", "group_class"], dropna=False)
        .size()
        .reset_index(name="count")
    )

    years = sorted(agg["year"].unique())
    bar_labels = ["Schengen/EL/EMP/CH", "3rd countries"]
    n_years = len(years)
    n_bars_per_year = 2
    total_bars = n_years * n_bars_per_year
    # Wider bars; same-year bars close together, gap between years
    bar_spacing = 0.48   # horizontal distance between the two bars of one year
    year_gap = 1.0       # gap between the last bar of one year and first of next
    width = 0.42         # bar width (wider, but < bar_spacing so same-year bars don't overlap)
    # x: for year y, bars at y*(bar_spacing+year_gap) and y*(bar_spacing+year_gap)+bar_spacing
    x_pos = [
        (i // n_bars_per_year) * (bar_spacing + year_gap) + (i % n_bars_per_year) * bar_spacing
        for i in range(total_bars)
    ]

    fig, ax = plt.subplots(figsize=(14, 7), dpi=150)
    colors = {"inbound": "#1B2A4A", "outbound": "#FF8C00"}

    # Build arrays: for each bar position, inbound then outbound heights
    bottom_inbound = []
    height_inbound = []
    bottom_outbound = []
    height_outbound = []
    totals = []
    for yi, year in enumerate(years):
        for group in bar_labels:
            sub = agg[(agg["year"] == year) & (agg["group_class"] == group)]
            inbound = sub[sub["direction"] == "inbound"]["count"].sum()
            outbound = sub[sub["direction"] == "outbound"]["count"].sum()
            height_inbound.append(inbound)
            height_outbound.append(outbound)
            totals.append(inbound + outbound)

    y_max = max(totals)
    label_offset = y_max * 0.02

    # Draw stacked bars: inbound first (bottom), then outbound on top
    bars_in = ax.bar(
        x_pos,
        height_inbound,
        width=width,
        color=colors["inbound"],
        label="Inbound",
    )
    bars_out = ax.bar(
        x_pos,
        height_outbound,
        width=width,
        bottom=height_inbound,
        color=colors["outbound"],
        label="Outbound",
    )

    # Numbers inside bars (segment midpoints)
    for i, (xin, xout) in enumerate(zip(height_inbound, height_outbound)):
        # Inbound segment center
        if xin > 0:
            mid_in = xin / 2
            ax.annotate(
                _format_count(xin),
                xy=(x_pos[i], mid_in),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )
        # Outbound segment center
        if xout > 0:
            mid_out = xin + xout / 2
            ax.annotate(
                _format_count(xout),
                xy=(x_pos[i], mid_out),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )
        # Total on top of bar (above bar so it doesn't overlap)
        total = totals[i]
        ax.annotate(
            _format_count(total),
            xy=(x_pos[i], xin + xout + label_offset),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_ylabel("Number of Persons")
    ax.set_title("Estonia Border Crossings by Country Group and Direction (2021–2025)")
    # One tick per year, centered between the two bars (Schengen and 3rd countries)
    ax.set_xticks([i * (bar_spacing + year_gap) + bar_spacing / 2 for i in range(n_years)])
    ax.set_xticklabels(years, fontsize=10)
    ax.set_xlabel("")
    ax.legend(loc="upper right")
    ax.set_ylim(0, y_max + label_offset * 4)
    # Show y-axis as plain numbers (no scientific notation or offset like "1e6")
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax.ticklabel_format(style="plain", axis="y")
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def create_ukr_citizenship_year_share_chart(
    df: pd.DataFrame,
    output_path: Path | None = None,
    citizenship_code: str = "UKR",
) -> None:
    """
    One column per year: UKR (citizenship_code) crossings only, stacked by
    inbound vs outbound counts. Y-axis is number of persons; total per year on top.
    """
    if output_path is None:
        output_path = (
            Path(__file__).resolve().parent.parent
            / "outputs"
            / "border_crossings_ukr_inbound_outbound_share.png"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    code = citizenship_code.strip().upper()
    cc = df["citizenship_code"].astype(str).str.strip().str.upper()
    subset = df[cc == code].copy()

    if subset.empty:
        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        ax.text(0.5, 0.5, f"No rows with citizenship_code = {code}", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
        return

    counts = (
        subset.groupby(["year", "direction"], dropna=False)
        .size()
        .unstack(fill_value=0)
    )
    for col in ("inbound", "outbound"):
        if col not in counts.columns:
            counts[col] = 0

    years = sorted(counts.index.astype(int).tolist())
    inbound = np.array([counts.loc[y, "inbound"] for y in years], dtype=float)
    outbound = np.array([counts.loc[y, "outbound"] for y in years], dtype=float)
    totals = inbound + outbound
    y_max = float(np.max(totals)) if len(totals) else 0.0
    label_offset = y_max * 0.02 if y_max > 0 else 1.0
    # Only label inside a segment if it is a sizable fraction of the tallest column
    min_frac_for_inner = 0.08

    fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
    colors = {"inbound": "#1B2A4A", "outbound": "#FF8C00"}
    x = np.arange(len(years))
    width = 0.55

    ax.bar(x, inbound, width, label="Inbound", color=colors["inbound"])
    ax.bar(x, outbound, width, bottom=inbound, label="Outbound", color=colors["outbound"])

    for i, _y in enumerate(years):
        t = totals[i]
        inn, out = inbound[i], outbound[i]
        if t == 0:
            continue
        # Count labels inside segments when large enough
        if inn >= y_max * min_frac_for_inner and inn > 0:
            ax.annotate(
                f"{int(inn):,}",
                xy=(x[i], inn / 2),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )
        if out >= y_max * min_frac_for_inner and out > 0:
            ax.annotate(
                f"{int(out):,}",
                xy=(x[i], inn + out / 2),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )
        # Total on top of column
        ax.annotate(
            f"{int(t):,}",
            xy=(x[i], t + label_offset),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(years)
    ax.set_xlabel("")
    ax.set_ylabel("Number of persons")
    ax.set_ylim(0, y_max + label_offset * 4 if y_max > 0 else 1)
    ax.set_title(
        f"Estonia Border Crossings — Citizenship {code}: Inbound vs Outbound by Year"
    )
    ax.legend(loc="upper right")
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax.ticklabel_format(style="plain", axis="y")
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def create_2022_monthly_inbound_outbound_share_chart(
    df: pd.DataFrame,
    output_path: Path | None = None,
) -> None:
    """
    One stacked bar per month for year 2022: inbound/outbound share inside each bar,
    and total monthly crossings on top of each bar.
    """
    if output_path is None:
        output_path = (
            Path(__file__).resolve().parent.parent
            / "outputs"
            / "border_crossings_2022_monthly_share.png"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subset = df[df["year"] == 2022].copy()
    if subset.empty:
        fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
        ax.text(0.5, 0.5, "No rows for year 2022", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
        return

    # Parse month from crossing_date to keep true monthly grouping.
    parsed_dates = pd.to_datetime(subset["crossing_date"], errors="coerce", dayfirst=True)
    subset["month"] = parsed_dates.dt.month
    subset = subset[subset["month"].notna()].copy()
    subset["month"] = subset["month"].astype(int)

    if subset.empty:
        fig, ax = plt.subplots(figsize=(12, 7), dpi=150)
        ax.text(0.5, 0.5, "No valid crossing_date values for year 2022", ha="center", va="center")
        ax.set_axis_off()
        fig.savefig(output_path, bbox_inches="tight")
        plt.close(fig)
        return

    counts = (
        subset.groupby(["month", "direction"], dropna=False)
        .size()
        .unstack(fill_value=0)
        .reindex(range(1, 13), fill_value=0)
    )
    for col in ("inbound", "outbound"):
        if col not in counts.columns:
            counts[col] = 0

    inbound = counts["inbound"].to_numpy(dtype=float)
    outbound = counts["outbound"].to_numpy(dtype=float)
    totals = inbound + outbound

    y_max = float(np.max(totals)) if len(totals) else 0.0
    label_offset = y_max * 0.015 if y_max > 0 else 1.0

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    x = np.arange(12)

    fig, ax = plt.subplots(figsize=(13, 7), dpi=150)
    colors = {"inbound": "#1B2A4A", "outbound": "#FF8C00"}
    width = 0.65

    ax.bar(x, inbound, width, label="Inbound", color=colors["inbound"])
    ax.bar(x, outbound, width, bottom=inbound, label="Outbound", color=colors["outbound"])

    for i in range(12):
        t = totals[i]
        inn = inbound[i]
        out = outbound[i]
        if t <= 0:
            continue

        share_in = inn / t * 100.0
        share_out = out / t * 100.0

        if inn > 0:
            ax.annotate(
                f"{share_in:.1f}%",
                xy=(x[i], inn / 2),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )
        if out > 0:
            ax.annotate(
                f"{share_out:.1f}%",
                xy=(x[i], inn + out / 2),
                ha="center",
                va="center",
                fontsize=8,
                color="white",
                fontweight="bold",
            )

        ax.annotate(
            f"{int(t):,}",
            xy=(x[i], t + label_offset),
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_xticks(x)
    ax.set_xticklabels(month_labels)
    ax.set_xlabel("")
    ax.set_ylabel("Number of persons")
    ax.set_ylim(0, y_max + label_offset * 5 if y_max > 0 else 1)
    ax.set_title("Estonia Border Crossings in 2022 by Month (Inbound/Outbound Share)")
    ax.legend(loc="upper right")
    ax.yaxis.set_major_formatter(ScalarFormatter(useOffset=False))
    ax.ticklabel_format(style="plain", axis="y")
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
