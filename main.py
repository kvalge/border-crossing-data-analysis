"""
Estonia Border Crossing Analysis – main entry point.
Runs: load data, exploration report, bar chart, forecast.
"""

from pathlib import Path

from src.data_loader import load_border_crossings
from src.explore import run_exploration
from src.forecast import run_forecast
from src.visualise import create_chart


def main() -> None:
    base = Path(__file__).resolve().parent
    outputs = base / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)

    print("Loading border crossing data...")
    df = load_border_crossings(base / "data" / "raw")
    print(f"  Loaded {len(df):,} rows.")

    print("Running exploration and writing report...")
    run_exploration(df, outputs / "exploration_report.txt")
    print("  Written outputs/exploration_report.txt")

    print("Creating bar chart...")
    create_chart(df, outputs / "border_crossings.png")
    print("  Written outputs/border_crossings.png")

    print("Running 6-month forecast and saving charts and numbers...")
    forecast_pngs = run_forecast(df, outputs, outputs / "forecast_numbers.txt")
    for p in forecast_pngs:
        print(f"  Written outputs/{p.name}")
    print("  Written outputs/forecast_numbers.txt")

    print("Done.")


if __name__ == "__main__":
    main()
