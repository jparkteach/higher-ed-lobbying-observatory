# Higher Education Lobbying Observatory

[Open the public dashboard](https://jparkteach.github.io/higher-ed-lobbying-observatory/) · [Read the research report](https://jparkteach.github.io/higher-ed-lobbying-observatory/report.html)

Five interactive views explore higher education lobbying and reconstruct Matthew J. Camp’s quantitative dissertation models using the supplied 2015–2024 institution panel.

## Explore

1. Annual sector spending and lobbying participation.
2. Lobbying prevalence by institutional characteristics.
3. Pell dependence and lobbying among for-profit institutions.
4. Research dependence and lobbying among nonprofits.
5. Adjusted logistic and OLS estimates, including confidence intervals and sensitivity analyses.

The dashboard includes year, sector and institution-type filters; annual institution records; accessible chart tables; and CSV downloads. Its 24 precomputed models retain their labeled samples when exploration filters change.

## Interpret the results

Lobbying is observed for **2015–2022**. Records for **2023–2024 are pending**, not zero. The main models show a positive association between research dependence and lobbying; the for-profit Pell relationship is inconclusive. Annual spending results are less consistent.

This is a research reconstruction conditional on the supplied data. Reporting-group labels change for some campuses, and possible overlapping campus/system spending requires checking against original filings. Totals retain the supplied values. The report documents these issues, reconstruction conventions and sensitivity results. These are associations, not causal effects or estimates of lobbying returns.

## Repository contents

- `docs/`: the published dashboard, report, derived data tables and downloadable analysis package.
- `analysis/`: reproducible analysis, numerical verification and report/dashboard builders.
- `output/`: derived results, diagnostics, audit and a self-contained offline dashboard.

The original input CSV and dissertation PDF are **not redistributed**. Source citations and page references appear in the report. No license for the original source material is implied by this repository being public.

## Reproduce

Use Python 3.12 with the dependencies recorded in `analysis/requirements.txt`. Supply your own copy of the input CSV:

```sh
python -m pip install -r analysis/requirements.txt
python analysis/replicate.py "/path/to/DISAGG_PANEL_2015_2024 2026.10.01.csv"
python analysis/verify.py
python analysis/build_report.py
```

Open `output/higher-education-lobbying-dashboard.html` directly for the offline dashboard. Keep the other output files next to it for report and download links.

To preview the published layout locally:

```sh
python -m http.server 8765 --directory docs
```

Then open `http://localhost:8765/`.

## Update the public website

GitHub Pages publishes the `docs/` directory on the `main` branch. Commit and push changes to that directory to update the live dashboard. Rebuilding the report also refreshes the downloadable analysis package.

## Sources

- Matthew J. Camp (2021), *No Longer Exempt: Higher Education’s Entrée into Lobbying*, Columbia University. Supplied as a reference PDF; not included here.
- `DISAGG_PANEL_2015_2024 2026.10.01.csv`, supplied for this analysis; not included here.
- [U.S. Bureau of Labor Statistics annual CPI-U](https://www.bls.gov/regions/mid-atlantic/data/consumerpriceindexannualandsemiannual_table.htm), used to express assumed nominal amounts in 2022 dollars.

Prepared October 16, 2026. Consult the report’s source audit before using these results in scholarly work.
