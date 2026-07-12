"""
Live scrape runner for ישובי הברון (Complot, site_id=14).

Covers the regional planning committee vaada-habaron.org.il —
settlements include זכרון יעקב, בנימינה-גבעת עדה, עמיקם, מעגן מיכאל.

Output: outputs/yishuvei_habaron_fresh.csv
"""

from scrapers.complot.api_scraper import ComplotPermitsAPI
import pandas as pd
import os

scraper = ComplotPermitsAPI(
    site_id=14,
    city_name_hebrew='ישובי הברון',
    # b_params defaults to range(2011, 2027) — covers full permit history
)
scraper.max_requests = None  # set to int for testing

permits = scraper.scrape()

df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_csv('outputs/yishuvei_habaron_fresh.csv', index=False, encoding='utf-8-sig')

print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'permit_status', 'permit_status_date', 'request_type', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
