"""
Scraper runner for ירושלים (custom API, ykpubdata.jerusalem.muni.il).

Two phases:
  1. scrape_parcels -- iterates (gush, helka) pairs already tracked in the
     projects export. This is the primary source (full data: address,
     applicant, dates) since there's no citywide "recent permits" feed.
  2. sweep_by_tik_number -- walks תיק numbers sequentially per year to catch
     permits not yet in the projects export. Schema is necessarily partial
     (no gush/helka/address -- see scrapers/jerusalem/api_scraper.py
     docstring), written to a separate CSV for manual follow-up rather than
     merged into the main report.

Both phases were confirmed reachable without office-network restrictions on
2026-07-16 (an earlier transient WAF block cleared on its own) -- see
scrapers/jerusalem/api_scraper.py docstring. If a future run hits repeated
403s, that guidance may need revisiting.

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_jerusalem.py
"""

import os
from datetime import datetime

import pandas as pd

from scrapers.jerusalem.api_scraper import JerusalemPermitsAPI
from transform import gush_helka
from transform.matcher import _compute_min_year

CITY = 'ירושלים'
projects_path = 'docs/all_projects.xlsx'
RUN_SWEEP = True

projects_df = pd.read_excel(projects_path)
projects_df.columns = [c.strip() for c in projects_df.columns]
projects_df = projects_df[projects_df['עיר'] == CITY]

parcel_pairs = set()
for value in projects_df['גוש-חלקה'].dropna():
    parcel_pairs |= gush_helka.parse(value)
parcel_pairs = sorted(parcel_pairs)
print(f'[INFO] {len(parcel_pairs)} unique gush/helka pairs from {len(projects_df)} '
      f'{CITY} rows in {projects_path}')

scraper = JerusalemPermitsAPI()
scraper.max_parcels = None  # set to int for testing

pairs_to_run = parcel_pairs if scraper.max_parcels is None else parcel_pairs[:scraper.max_parcels]
permits = scraper.scrape_parcels(pairs_to_run)
df = pd.DataFrame(permits)

print('\n--- request_type value counts (check for double-yod variants) ---')
if 'request_type' in df.columns:
    print(df['request_type'].value_counts().to_string())

os.makedirs('outputs', exist_ok=True)
df.to_csv('outputs/jerusalem_fresh.csv', index=False, encoding='utf-8-sig')

print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'request_type', 'permit_status', 'permit_status_date', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())

if RUN_SWEEP:
    min_year = _compute_min_year(projects_df) or (datetime.now().year - 10)
    years = list(range(min_year, datetime.now().year + 1))
    print(f'\n[INFO] Sweeping תיק numbers for years {years[0]}-{years[-1]} '
          f'(min_year={min_year}, same convention as other cities\' min_year)')

    known_tik_nums = set(df['request_number']) if 'request_number' in df.columns else set()
    sweep_results = scraper.sweep_by_tik_number(years=years, known_tik_nums=known_tik_nums)
    sweep_df = pd.DataFrame(sweep_results)
    sweep_df.to_csv('outputs/jerusalem_sweep.csv', index=False, encoding='utf-8-sig')
    print(f'[INFO] Sweep found {len(sweep_df)} תיק rows not covered by known gush/helka pairs '
          f'-> outputs/jerusalem_sweep.csv (partial data -- needs manual parcel lookup)')
