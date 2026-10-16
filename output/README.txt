Camp dissertation replication, 2015–2024 panel

Open output/higher-education-lobbying-dashboard.html directly in a browser. It is self-contained and requires no server or network. Keep the other output files next to it for report and download links.
The separate docs/index.html version uses a local HTTP server and fetches data.json.
Read output/camp_replication_report.html for sources, conventions, findings and limitations.
Input CSV and dissertation are not redistributed. Supply the original CSV to analysis/replicate.py.
Do not treat as-supplied totals as deduplicated filings. See the Michigan overlap and reporting-group audit.

Run:
  python -m pip install -r analysis/requirements.txt
  python analysis/replicate.py "/path/to/input.csv"
  python analysis/verify.py
  python analysis/build_report.py

Source SHA256: cabe717640649ad653d28768c0d8d3e4f70a22dde95c3350cd0d596100d4371d
