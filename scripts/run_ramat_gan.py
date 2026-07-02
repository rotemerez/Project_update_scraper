"""
Live scrape runner for Ramat Gan (Complot).

Scrapes permit requests and saves to outputs/ramat_gan_fresh.csv.
Test mode: set max_requests to a small number first to verify.
Full mode:  set max_requests = None.
"""

from scrapers.complot.api_scraper import ComplotPermitsAPI
import pandas as pd
import os

scraper = ComplotPermitsAPI(
    site_id=3,
    city_name_hebrew='רמת גן',
    # b_params defaults to range(2011, 2027) — covers full permit history
)
scraper.max_requests = None  # set to int for testing

permits = scraper.scrape()

df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_csv('outputs/ramat_gan_fresh.csv', index=False, encoding='utf-8-sig')

print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'permit_status', 'permit_status_date', 'request_type', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
