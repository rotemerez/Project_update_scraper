"""
Matcher runner for the ירושלים tik-number sweep (outputs/jerusalem_sweep.csv,
20,693 rows, enriched with block_lot/full_address in Session V -- see
scripts/enrich_jerusalem_sweep.py).

Separate from scripts/run_jerusalem_matcher.py (which runs against the
parcel-based outputs/jerusalem_fresh.csv, 7,927 rows). Zero overlap in
request_number between the two files -- the sweep covers a disjoint set of
permits not reachable via the tracked-parcel scrape -- so this runs as its
own pass with its own cache/output rather than merging into the fresh report.

Sweep-specific recency pre-filter (added Session X): the sweep's source
endpoint (fetchTikRushiData, see scrapers/jerusalem/api_scraper.py module
docstring) has no request/filing-date field at all -- confirmed via a live
call, its full schema is ID/tik_num/status_code/teurStatus/taarih_status/
sugbakasha_code/teurSugbakasha/mahut_bakasha. So request_date is blank for
every sweep row, which makes the matcher's normal 365-day _is_recent() check
(transform/matcher.py, keyed on request_date) a complete no-op here -- the
first unfiltered run surfaced 3,154 untracked rows spanning back to 2005,
97% of them with no status change in over 3 years.

Since there's no filing date to fall back on, this pre-filters on the one
real date the endpoint does provide -- permit_status_date (last known status
change, taarih_status) -- to a 3-year cutoff, before the file ever reaches
transform/matcher.py. This is scoped to this script only; the shared matcher
module and its request_date-based logic are unchanged for every other city.
Rows with no parseable permit_status_date are dropped too (rather than
defaulting to "assume recent"), since keeping them would defeat the point of
the filter -- this is a deliberate call, not a silent default.

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_jerusalem_sweep_matcher.py
"""

import pandas as pd

from transform.matcher import run

RECENCY_YEARS = 3
SWEEP_PATH = 'outputs/jerusalem_sweep.csv'
FILTERED_PATH = 'outputs/jerusalem_sweep_recent.csv'

df = pd.read_csv(SWEEP_PATH, encoding='utf-8-sig', dtype=str, keep_default_na=False)
status_date = pd.to_datetime(df['permit_status_date'], errors='coerce')
cutoff = pd.Timestamp.now() - pd.Timedelta(days=365 * RECENCY_YEARS)
recent = df[status_date >= cutoff]
print(f'[INFO] {SWEEP_PATH}: {len(df)} -> {len(recent)} rows '
      f'(permit_status_date within {RECENCY_YEARS} years, cutoff={cutoff.date()})')
recent.to_csv(FILTERED_PATH, index=False, encoding='utf-8-sig')

run(
    projects_path='docs/all_projects.xlsx',
    permits_path=FILTERED_PATH,
    city_hebrew='ירושלים',
    output_path='outputs/jerusalem_sweep_report.xlsx',
    matched_cache_path='outputs/jerusalem_sweep_matched_cache.json',
    permit_url_base='https://ykpubdata.jerusalem.muni.il/#/Rishui/ProcessInfo?SystemCode=26400046&TikNum=',
    city_filter=['ירושלים'],
)
