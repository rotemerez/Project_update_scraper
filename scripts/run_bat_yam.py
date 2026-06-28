"""
Live scrape runner for Bat Yam (Complot).

Scrapes permit requests submitted in YEARS and saves to outputs/bat_yam_fresh.xlsx.
Test mode: set max_requests to a small number first to verify.
Full mode:  set max_requests = None.
"""

from scrapers.complot.api_scraper import ComplotPermitsAPI
import pandas as pd
import os

scraper = ComplotPermitsAPI(
    site_id=81,
    city_name_hebrew='בת ים',
    # b_params defaults to range(2011, 2027) — covers full permit history
    # year_filter=None means keep all dates; set e.g. [2020,2021,...] to narrow output
)
scraper.max_requests = None  # set to int for testing

permits = scraper.scrape()

df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_excel('outputs/bat_yam_fresh.xlsx', index=False)

print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'permit_status', 'permit_status_date', 'request_type', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
