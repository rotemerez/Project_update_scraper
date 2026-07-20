"""
Scraper runner for תל אביב יפו -- GIS ArcGIS layer approach (see
scrapers/tel_aviv/gis_api_scraper.py). Plain requests, no browser, no
reCAPTCHA -- pulls the entire public "בקשות והיתרי בניה" layer (~10,500 rows)
in a handful of paginated requests, then resolves each permit's building to
its גוש/חלקה via the handasa.tel-aviv.gov.il WCF lookup.

This replaces the need for the Selenium/reCAPTCHA scraper
(scrapers/tel_aviv/scraper.py, run_tel_aviv.py) for permit discovery --
that scraper is left in place but paused (see session handoffs).

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_tel_aviv_gis.py
"""

import os

import pandas as pd

from scrapers.tel_aviv.gis_api_scraper import TelAvivGisAPI

FRESH_PATH = 'outputs/tel_aviv_gis_fresh.csv'

scraper = TelAvivGisAPI()
permits = scraper.scrape_all()
df = pd.DataFrame(permits)

print('\n--- request_type value counts (check for double-yod variants) ---')
if 'request_type' in df.columns and not df.empty:
    print(df['request_type'].value_counts().to_string())

print('\n--- permit_status value counts ---')
if 'permit_status' in df.columns and not df.empty:
    print(df['permit_status'].value_counts(dropna=False).to_string())

print('\n--- block_lot resolution rate ---')
if 'block_lot' in df.columns and not df.empty:
    resolved = (df['block_lot'].astype(str).str.strip() != '').sum()
    print(f'{resolved} / {len(df)} permits resolved a gush/helka via the WCF lookup')

os.makedirs('outputs', exist_ok=True)
df.to_csv(FRESH_PATH, index=False, encoding='utf-8-sig')
print(f'\n--- Results ({len(df)} permits) -> {FRESH_PATH} ---')
