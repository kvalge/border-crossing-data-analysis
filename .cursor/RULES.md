# Cursor Spec – Estonia Border Crossing Analysis

## Project context

This project analyses Estonian border crossing data for the years 2021–2025.
The raw data is split across ten CSV files:

- `piiriületused_isikud_sisse_2021.csv` … `piiriületused_isikud_sisse_2025.csv` (inbound crossings)
- `piiriületused_isikud_valja_2021.csv`  … `piiriületused_isikud_valja_2025.csv` (outbound crossings)

The raw files live in `data/raw/` and must **never be modified**.

---

## Project structure

```
border_crossing_analysis/
│
├── data/
│   └── raw/                  # original source files – do not touch
│
├── outputs/                  # all generated outputs go here
│
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── explore.py
│   └── visualise.py
│
├── main.py
├── project_overview.md
├── requirements.txt
└── README.md
```

---

## Setup

Create `requirements.txt`

---

## Column name mapping (Estonian → English)

The CSV files have Estonian column headers. Rename all columns to English immediately after loading.

| Original (Estonian)   | English name       |
|-----------------------|--------------------|
| Piiriületuse kpv      | crossing_date      |
| Piiripunkt            | border_point       |
| Piiripunkti tüüp      | border_point_type  |
| Kodakondsus           | citizenship        |
| Kodakondsus lühend    | citizenship_code   |
| Riikide grupp         | country_group      |
| Sugu                  | gender             |
| Vanuserühm            | age_group          |

> Before loading, inspect the raw files to determine the correct delimiter and encoding. Do not assume.

---

## data_loader.py

**What it must produce:** a single combined `DataFrame` containing all years and both directions, with:
- English column names as above
- A `direction` column: `"inbound"` for files with `_sisse_` in the filename, `"outbound"` for `_valja_`
- A `year` column (integer) extracted from the filename

Code must follow Python best practices and PEP 8. Include short, clear English inline comments where they aid understanding.

---

## explore.py

**What it must produce:** a plain-text file `outputs/exploration_report.txt` that makes it immediately clear to any reader what the dataset contains. The report must include:

- Total number of rows and columns
- Years covered and directions present
- All column names with their data types
- Missing value counts per column (only columns that have missing values)
- Unique values for key categorical columns: `direction`, `year`, `country_group`, `border_point_type`, `gender`, `age_group`
- Row counts broken down by year and direction
- Distribution of `country_group` values with counts
- **A dedicated section on unclassified rows:** how many rows have a `country_group` value that does not contain `"Schengen"` or `"EL/EMP/CH"` (case-insensitive) — meaning they will be treated as 3rd countries. List those values and their counts so it is clear what is being grouped there.

The report must be easy to read — structured sections, plain text, no code.

Code must follow Python best practices and PEP 8. Include short, clear English inline comments.

---

## visualise.py

**What it must produce:** a PNG file `outputs/border_crossings.png` — a grouped bar chart showing inbound and outbound border crossings by year, split into two country groups.

### Country group classification

Rows where `country_group` contains `"Schengen"` or `"EL/EMP/CH"` (case-insensitive) → **Schengen / EL/EMP/CH**.
All other rows, including those with missing `country_group` values → **3rd countries**.

### Chart requirements

- **Chart type:** grouped bar chart — 4 side-by-side bars per year
- **Title:** `Estonia Border Crossings by Country Group and Direction (2021–2025)`
- **X-axis label:** `Year`
- **Y-axis label:** `Number of Persons`
- **Colours:**
  - Inbound bars: `#1B2A4A` (navy blue)
  - Outbound bars: `#FF8C00` (orange)
- **Distinguishing Schengen vs 3rd countries:** use alpha transparency
  - Schengen / EL/EMP/CH: `alpha=1.0`
  - 3rd countries: `alpha=0.65`
- **Legend entries:** `Schengen/EL/EMP/CH – Inbound`, `Schengen/EL/EMP/CH – Outbound`, `3rd Countries – Inbound`, `3rd Countries – Outbound`
- **Bar labels:** display the count on top of each bar (choose the most readable format — full number or abbreviated, e.g. `840K`)
- **Figure size:** `figsize=(14, 7)`, DPI 150

Code must follow Python best practices and PEP 8. Include short, clear English inline comments.

---

## main.py

**What it must do:** run all steps in order — load data, run exploration, create chart — with a short status print before each step.

---

## forecast.py

**What it must do:** a 6-month forecast for April–September of the current year, split by country group (Schengen / EL/EMP/CH and 3rd countries) and direction (inbound / outbound).
The forecast must be based on the historical monthly totals from the combined dataset. Use a simple, well-established forecasting approach — for example seasonal decomposition or linear regression with month and year as features. The choice of method should be justified in a short comment in the code.
The chart must make it visually clear which values are historical and which are forecasted — for example using a dashed line or shading for the forecast period. Use the same navy blue and orange colour scheme as the main chart.
Code must follow Python best practices and PEP 8. Add scikit-learn or statsmodels to requirements.txt depending on which library is used.

---

## project_overview.md

**What it must do:** a plain-English description of the project — what each file does and what it produces. Written for someone who is new to the project and wants to understand it quickly without reading any code.
The overview must cover every file in the project. One short paragraph per file is enough. No code snippets.

---

## Rules

1. Raw files in `data/raw/` are never modified.
2. All column names are in English immediately after loading.
3. All outputs (text report and PNG) are written to `outputs/`.
4. All code — variable names, comments, docstrings — is in English.
5. Code follows PEP 8 and general Python best practices.
6. Comments in code should be short and plain English, only where they genuinely help.
