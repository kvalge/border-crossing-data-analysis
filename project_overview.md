# Project overview – Estonia Border Crossing Analysis

This document describes what each part of the project does and what it produces, in plain English and without code.

---

## Data and folder layout

**data/raw/**  
Contains the original CSV files from the Police and Border Guard Board: inbound and outbound border crossing counts per year (2021–2025). These files must never be changed; all processing uses copies in memory.

**outputs/**  
All generated results go here: the exploration report (text), the main bar chart (PNG), and the forecast chart (PNG).

---

## main.py

The main script runs the full pipeline. It loads the raw data, runs the exploration step, creates the main bar chart, and then produces the 6‑month forecast chart. Before each step it prints a short status message so you can follow progress.

---

## src/data_loader.py

The data loader reads every CSV in `data/raw/` that matches the expected naming pattern (inbound and outbound, all years). It detects each file’s delimiter and encoding instead of assuming them. Column headers are renamed from Estonian to English as defined in the project spec. It adds a `direction` column (inbound or outbound, from the filename) and a `year` column (from the filename), then concatenates everything into one combined table. Nothing is written to disk; it only returns the combined data for use by the rest of the project.

---

## src/explore.py

The exploration step takes the combined dataset and writes a single text report to `outputs/exploration_report.txt`. The report describes the dataset in plain language: number of rows and columns, which years and directions are present, column names and types, missing value counts where relevant, and unique values for the main categorical columns. It also includes row counts by year and direction, the distribution of country groups, and a dedicated section on “unclassified” rows—those that will be treated as third countries (i.e. where the country group does not contain “Schengen” or “EL/EMP/CH”). That section lists those values and their counts so it is clear what is grouped as third countries.

---

## src/visualise.py

The visualisation step produces `outputs/border_crossings.png`, a stacked bar chart by year and country group (Schengen/EL/EMP/CH vs third countries), with inbound and outbound stacked in each bar. It also produces `outputs/border_crossings_ukr_inbound_outbound_share.png`: one column per year for rows where `citizenship_code` is UKR (Ukraine), with **stacked counts** for inbound vs outbound (y-axis = number of persons), **total per year** on top of each column, and segment counts inside the bars when readable. Navy and orange colours match inbound and outbound elsewhere in the project.

---

## src/forecast.py

The forecast step produces a 6‑month forecast for April–September of the current year, split by the same country groups (Schengen/EL/EMP/CH vs third countries) and direction (inbound vs outbound). It uses the combined dataset’s historical monthly totals and a standard time‑series method (Holt–Winters exponential smoothing) that captures trend and seasonality. The output is a chart saved to `outputs/border_crossings_forecast.png`. The chart clearly separates history from forecast (e.g. solid vs dashed lines and a shaded forecast period) and uses the same navy and orange colour scheme as the main bar chart.

---

## requirements.txt

Lists the Python packages needed to run the project: pandas for data loading and manipulation, matplotlib for charts, and statsmodels for the forecast model. Versions are pinned so that the same environment can be reproduced.

---

## README.md

The README gives a short overview of the project and points to the data source. It is the first place to look for a quick summary and setup instructions.

---

## .cursor/RULES.md

The Cursor rules file defines the project structure, column mappings, and requirements for each script and output. It is the single source of truth for how the project should behave and what it must produce.
