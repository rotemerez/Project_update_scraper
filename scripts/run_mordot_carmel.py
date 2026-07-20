"""
Scraper runner for מורדות כרמל (Complot, site_id=61).
Covers: טירת הכרמל, נשר.

NOTE: Must be run from office network — handasi.complot.co.il blocks home IPs.
Also note: the portal frontend (mordotcarmel.org) returns 403, but the Complot
API (handasi.complot.co.il) is independent and should still work.

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_mordot_carmel.py
"""

from scrapers.complot.api_scraper import ComplotPermitsAPI
from transform.matcher import _compute_min_year
import pandas as pd
import os

CITIES = ['טירת הכרמל', 'נשר']
projects_path = 'docs/all_projects.xlsx'

projects_df = pd.read_excel(projects_path)
projects_df.columns = [c.strip() for c in projects_df.columns]
projects_df = projects_df[projects_df['עיר'].isin(CITIES)]
min_year = _compute_min_year(projects_df)
print(f'[INFO] min_year={min_year} (auto-computed from {projects_path}, cities={CITIES})')

scraper = ComplotPermitsAPI(
    site_id=61,
    city_name_hebrew='מורדות כרמל',
    min_year=min_year,
)
scraper.max_requests = None  # set to int for testing

# Print request_type value counts before saving (BUG-016 checklist)
permits = scraper.scrape()
df = pd.DataFrame(permits)

print('\n--- request_type value counts (check for double-yod variants) ---')
if 'request_type' in df.columns:
    print(df['request_type'].value_counts().to_string())

os.makedirs('outputs', exist_ok=True)
df.to_csv('outputs/mordot_carmel_fresh.csv', index=False, encoding='utf-8-sig')

print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'permit_status', 'permit_status_date', 'request_type', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
