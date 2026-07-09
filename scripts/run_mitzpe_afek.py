"""
Scraper runner for מיצפה אפק (Bartech, www.vmm.co.il).
Covers: באר יעקב.

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_mitzpe_afek.py
"""

from scrapers.bartech.api_scraper import BartechPermitsAPI
from transform.matcher import _compute_min_year
import pandas as pd
import os

CITY = 'באר יעקב'
projects_path = 'docs/all_projects_08072026.xlsx'

projects_df = pd.read_excel(projects_path)
projects_df.columns = [c.strip() for c in projects_df.columns]
projects_df = projects_df[projects_df['עיר'] == CITY]
min_year = _compute_min_year(projects_df)
print(f'[INFO] min_year={min_year} (auto-computed from {projects_path}, city={CITY})')

scraper = BartechPermitsAPI(
    base_url='https://www.vmm.co.il',
    city_name_hebrew=CITY,
    min_year=min_year,
)
scraper.max_pages = None  # set to int for testing

permits = scraper.scrape()
df = pd.DataFrame(permits)

print('\n--- request_type value counts (check for double-yod variants) ---')
if 'request_type' in df.columns:
    print(df['request_type'].value_counts().to_string())

os.makedirs('outputs', exist_ok=True)
df.to_csv('outputs/mitzpe_afek_fresh.csv', index=False, encoding='utf-8-sig')

print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'request_type', 'permit_status', 'permit_status_date', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
