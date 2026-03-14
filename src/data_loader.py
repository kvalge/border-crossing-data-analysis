"""
Load and combine Estonian border crossing CSV files from data/raw/.
Returns a single DataFrame with English column names, direction, and year.
"""

import re
from pathlib import Path

import pandas as pd

# Column name mapping: Estonian (as in CSV) -> English
COLUMN_MAP = {
    "Piiriületuse kpv": "crossing_date",
    "Piiripunkt": "border_point",
    "Piiripunkti tüüp": "border_point_type",
    "Kodakondsus": "citizenship",
    "Kodakondsus lühend": "citizenship_code",
    "Riikide grupp": "country_group",
    "Sugu": "gender",
    "Vanuserühm": "age_group",
}


def _detect_format(csv_path: Path) -> tuple[str, str]:
    """Inspect first line to infer delimiter and try common encodings."""
    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            with open(csv_path, encoding=encoding) as f:
                first = f.readline()
            if "\t" in first:
                return "\t", encoding
            if "," in first and first.count(",") > 1:
                return ",", encoding
            if ";" in first:
                return ";", encoding
        except UnicodeDecodeError:
            continue
    return "\t", "utf-8"


def _direction_and_year(filename: str) -> tuple[str, int]:
    """Extract direction from filename (sisse=inbound, valja=outbound) and year."""
    name = filename.lower()
    direction = "inbound" if "sisse" in name else "outbound"
    match = re.search(r"20(\d{2})\.csv", filename)
    year = int(match.group(1)) + 2000 if match else 0
    return direction, year


def load_border_crossings(data_dir: Path | None = None) -> pd.DataFrame:
    """
    Load all border crossing CSVs from data/raw/, rename columns to English,
    add direction and year. Returns one combined DataFrame.
    """
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data" / "raw"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {data_dir}")

    # Match both possible filename spellings (ü vs y)
    pattern = "*isikud_*_20*.csv"
    files = sorted(data_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No CSV files matching '{pattern}' in {data_dir}")

    frames = []
    for path in files:
        sep, encoding = _detect_format(path)
        direction, year = _direction_and_year(path.name)
        df = pd.read_csv(path, sep=sep, encoding=encoding, dtype=str)
        # Rename to English
        df = df.rename(columns=COLUMN_MAP)
        df["direction"] = direction
        df["year"] = year
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    combined["year"] = combined["year"].astype(int)
    return combined
