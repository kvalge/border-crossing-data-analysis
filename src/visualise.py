"""
Create stacked bar chart of border crossings by year and country group.
Two bars per year (Schengen/EL/EMP/CH, 3rd countries), each stacked by inbound/outbound.
Writes outputs/border_crossings.png.
"""

from pathlib import Path

import matplotlib.pyplot as plt
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
