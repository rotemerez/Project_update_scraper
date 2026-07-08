"""Runner for Hadera (Bartech, https://hadera.bartech-net.co.il). Run from project root.

min_year is auto-computed from the projects file — earliest permit date on an
in-progress project without Form 4. Do not hardcode it.
"""
import os
import pandas as pd
from scrapers.bartech.api_scraper import BartechPermitsAPI
from transform.matcher import _compute_min_year

projects_path = 'docs/Hadera_Projects_08072026.xlsx'
projects_df = pd.read_excel(projects_path)
projects_df.columns = [c.strip() for c in projects_df.columns]
min_year = _compute_min_year(projects_df)
print(f'[INFO] min_year={min_year} (auto-computed from {projects_path})')

scraper = BartechPermitsAPI(
    base_url='https://hadera.bartech-net.co.il',
    city_name_hebrew='חדרה',
    min_year=min_year,
)
scraper.max_pages = None  # set to int for testing

permits = scraper.scrape()
df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_csv('outputs/hadera_fresh.csv', index=False, encoding='utf-8-sig')
print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'request_type', 'shimush_ikari', 'unit_count',
        'bakasha_description', 'permit_status', 'permit_status_date', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].head(10).to_string())
