"""Runner for Holon (Bartech). Run from project root."""
import os
import pandas as pd
from scrapers.bartech.api_scraper import BartechPermitsAPI

scraper = BartechPermitsAPI(
    base_url='https://hln.bartech-net.co.il',
    city_name_hebrew='חולון',
)
scraper.max_pages = None  # set to int for testing

permits = scraper.scrape()
df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_csv('outputs/holon_fresh.csv', index=False, encoding='utf-8-sig')
print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'request_type', 'permit_status', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
