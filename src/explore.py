"""
Produce a plain-text exploration report for the border crossing dataset.
Writes outputs/exploration_report.txt.
"""

from pathlib import Path

import pandas as pd


def _is_schengen_or_el(country_group: str) -> bool:
    """True if value contains 'Schengen' or 'EL/EMP/CH' (case-insensitive)."""
    if pd.isna(country_group):
        return False
    s = str(country_group).lower()
    return "schengen" in s or "el/emp/ch" in s


def run_exploration(df: pd.DataFrame, output_path: Path | None = None) -> None:
    """
    Generate exploration_report.txt with dataset overview, dtypes,
    missing values, categorical uniques, and unclassified (3rd country) section.
    """
    if output_path is None:
        output_path = (
            Path(__file__).resolve().parent.parent / "outputs" / "exploration_report.txt"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    # --- Basic shape ---
    lines.append("=" * 60)
    lines.append("ESTONIA BORDER CROSSING DATA – EXPLORATION REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append("SHAPE")
    lines.append("-" * 40)
    lines.append(f"Total rows:    {len(df):,}")
    lines.append(f"Total columns: {len(df.columns)}")
    lines.append("")

    # --- Years and directions ---
    years = sorted(df["year"].dropna().unique().astype(int).tolist())
    dirs = df["direction"].dropna().unique().tolist()
    lines.append("YEARS AND DIRECTIONS")
    lines.append("-" * 40)
    lines.append(f"Years covered: {years}")
    lines.append(f"Directions:    {dirs}")
    lines.append("")

    # --- Columns and dtypes ---
    lines.append("COLUMNS AND DATA TYPES")
    lines.append("-" * 40)
    for col in df.columns:
        lines.append(f"  {col}: {df[col].dtype}")
    lines.append("")

    # --- Missing values (only columns that have any) ---
    missing = df.isna().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if len(missing) > 0:
        lines.append("MISSING VALUES (columns with at least one missing)")
        lines.append("-" * 40)
        for col in missing.index:
            lines.append(f"  {col}: {int(missing[col]):,}")
        lines.append("")
    else:
        lines.append("MISSING VALUES")
        lines.append("-" * 40)
        lines.append("  None.")
        lines.append("")

    # --- Unique values for key categorical columns ---
    key_cats = [
        "direction",
        "year",
        "country_group",
        "border_point_type",
        "gender",
        "age_group",
    ]
    for col in key_cats:
        if col not in df.columns:
            continue
        uniq = df[col].dropna().unique()
        if len(uniq) <= 30:
            vals = sorted(str(x) for x in uniq)
        else:
            vals = [f"{len(uniq)} unique values (first 10: {sorted(str(x) for x in uniq)[:10]})"]
        lines.append(f"UNIQUE VALUES: {col}")
        lines.append("-" * 40)
        for v in vals if isinstance(vals[0], str) and len(vals) > 1 else vals:
            lines.append(f"  {v}")
        lines.append("")

    # --- Row counts by year and direction ---
    lines.append("ROW COUNTS BY YEAR AND DIRECTION")
    lines.append("-" * 40)
    by_yd = df.groupby(["year", "direction"], dropna=False).size()
    for (y, d), count in by_yd.items():
        lines.append(f"  Year {y}, {d}: {int(count):,}")
    lines.append("")

    # --- Distribution of country_group ---
    lines.append("DISTRIBUTION OF country_group")
    lines.append("-" * 40)
    cg = df["country_group"].value_counts(dropna=False)
    for val, cnt in cg.items():
        disp = "(missing)" if pd.isna(val) else val
        lines.append(f"  {disp}: {int(cnt):,}")
    lines.append("")

    # --- Unclassified rows (3rd countries) ---
    lines.append("UNCLASSIFIED ROWS (3rd COUNTRIES)")
    lines.append("-" * 40)
    lines.append(
        "Rows whose country_group does NOT contain 'Schengen' or 'EL/EMP/CH' "
        "(case-insensitive), including missing, are treated as 3rd countries."
    )
    lines.append("")
    schengen_mask = df["country_group"].apply(_is_schengen_or_el)
    third = df[~schengen_mask]
    lines.append(f"Total rows classified as 3rd countries: {len(third):,}")
    lines.append("")
    third_cg = third["country_group"].value_counts(dropna=False)
    lines.append("Values and counts in this group:")
    for val, cnt in third_cg.items():
        disp = "(missing)" if pd.isna(val) else val
        lines.append(f"  {disp}: {int(cnt):,}")
    lines.append("")
    lines.append("=" * 60)

    text = "\n".join(lines)
    output_path.write_text(text, encoding="utf-8")
