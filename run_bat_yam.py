"""
Live scrape runner for Bat Yam (Complot).

Scrapes permit requests submitted in YEARS and saves to outputs/bat_yam_fresh.xlsx.
Test mode: set max_requests to a small number first to verify.
Full mode:  set max_requests = None.
"""

from scrapers.complot.scraper import ComplotScraper
import pandas as pd
import os

YEARS = [2025, 2026]  # only scrape permits submitted in these years

scraper = ComplotScraper(
    city_name_hebrew='בת ים',
    url='https://batyam.complot.co.il/iturbakashot/#search/GetBakashotByNumber&siteid=81&grp=0&t=0&b=2025&l=false&arguments=siteId,grp,t,b,l',
    headless=False,
    year_filter=YEARS,
)
scraper.max_requests = 20  # set to None for full scrape

permits = scraper.scrape()

df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_excel('outputs/bat_yam_fresh.xlsx', index=False)

print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'permit_status', 'permit_status_date', 'request_type', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
