"""
Standalone runner for the ירושלים sequential תיק-number sweep
(scrapers/jerusalem/api_scraper.py: JerusalemPermitsAPI.sweep_by_tik_number).

Reuses the already-scraped outputs/jerusalem_fresh.csv (7,927 permits from the
2026-07-16 parcel-scrape run) as known_tik_nums, so this does NOT re-run the
~35-minute parcel scrape -- it only walks תיק numbers looking for permits not
covered by any tracked (gush, helka) pair.

Run from project root (see CLAUDE.md for background-run pattern):
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_jerusalem_sweep.py
"""

import os
from datetime import datetime

import pandas as pd

from scrapers.jerusalem.api_scraper import JerusalemPermitsAPI
from transform.matcher import _compute_min_year

CITY = 'ירושלים'
projects_path = 'docs/all_projects.xlsx'
fresh_path = 'outputs/jerusalem_fresh.csv'

fresh_df = pd.read_csv(fresh_path, encoding='utf-8-sig')
known_tik_nums = set(fresh_df['request_number'].dropna()) if 'request_number' in fresh_df.columns else set()
print(f'[INFO] Loaded {len(known_tik_nums)} known תיק numbers from {fresh_path}')

projects_df = pd.read_excel(projects_path)
projects_df.columns = [c.strip() for c in projects_df.columns]
projects_df = projects_df[projects_df['עיר'] == CITY]

min_year = _compute_min_year(projects_df) or (datetime.now().year - 10)
years = list(range(min_year, datetime.now().year + 1))
print(f'[INFO] Sweeping תיק numbers for years {years[0]}-{years[-1]} (min_year={min_year})')

scraper = JerusalemPermitsAPI()
sweep_results = scraper.sweep_by_tik_number(years=years, known_tik_nums=known_tik_nums)

sweep_df = pd.DataFrame(sweep_results)
os.makedirs('outputs', exist_ok=True)
sweep_df.to_csv('outputs/jerusalem_sweep.csv', index=False, encoding='utf-8-sig')
print(f'[INFO] Sweep found {len(sweep_df)} תיק rows not covered by known gush/helka pairs '
      f'-> outputs/jerusalem_sweep.csv (partial data -- needs manual parcel lookup)')
