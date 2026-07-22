"""
Targeted BUG-020 fix pass — re-fetches detail pages ONLY for permits whose permit_status is
היתר or טופס 4 (the only two statuses _parse_certificates() can override), across all 6
already-scraped Bartech cities. Skips the list phase entirely: request_number and the original
definement_type (recovered from the saved request_category, which is the type_label
BartechPermitsAPI._parse_page() wrote at scrape time) are read straight from each city's
existing *_fresh.csv.

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\reenrich_bartech_dates.py
"""

import os
import time
import pandas as pd

from scrapers.bartech.api_scraper import BartechPermitsAPI, PERMIT_TYPES, _parse_detail

LABEL_TO_TYPE_ID = {label: type_id for type_id, label in PERMIT_TYPES.items()}
DEFAULT_TYPE_ID = 51  # 'מסלול רישוי מלא' -- most common; used when request_category is blank/unrecognized

CITIES = [
    # holon, krayot already done (completed before an internet-connectivity pause, 2026-07-22)
    {'key': 'hadera',       'base_url': 'https://hadera.bartech-net.co.il', 'city_hebrew': 'חדרה'},
    {'key': 'harel',        'base_url': 'https://www.v-harel.co.il',       'city_hebrew': 'מבשרת ציון'},
    {'key': 'zmora',        'base_url': 'https://www.zmora.org.il',        'city_hebrew': 'מזכרת בתיה'},
    {'key': 'mitzpe_afek',  'base_url': 'https://www.vmm.co.il',           'city_hebrew': 'באר יעקב'},
]

AFFECTED_STATUSES = {'היתר', 'טופס 4'}


def reenrich_city(city_key: str, base_url: str, city_hebrew: str):
    csv_path = f'outputs/{city_key}_fresh.csv'
    backup_path = f'outputs/{city_key}_fresh_pre_bug020.csv'

    df = pd.read_csv(csv_path, encoding='utf-8-sig', dtype=str)
    if not os.path.exists(backup_path):
        df.to_csv(backup_path, index=False, encoding='utf-8-sig')
        print(f'[{city_key}] backup saved -> {backup_path}')

    mask = df['permit_status'].isin(AFFECTED_STATUSES)
    target_idx = df[mask].index.tolist()
    print(f'[{city_key}] {len(df)} total permits, {len(target_idx)} at risk (היתר/טופס 4)')

    scraper = BartechPermitsAPI(base_url=base_url, city_name_hebrew=city_hebrew)

    changed = 0
    fetch_failed = 0
    for i, idx in enumerate(target_idx):
        entity_num = df.at[idx, 'request_number']
        request_category = df.at[idx, 'request_category']
        type_id = LABEL_TO_TYPE_ID.get(request_category, DEFAULT_TYPE_ID)

        html = scraper._fetch_detail(entity_num, type_id)
        if not html:
            fetch_failed += 1
            time.sleep(0.2)
            continue

        detail = _parse_detail(html)
        new_date = detail.get('permit_status_date') or ''
        old_date = df.at[idx, 'permit_status_date'] or ''
        if new_date and new_date != old_date:
            df.at[idx, 'permit_status_date'] = new_date
            changed += 1

        if (i + 1) % 200 == 0:
            print(f'[{city_key}] [{i + 1}/{len(target_idx)}] fetched, {changed} dates corrected so far')
        time.sleep(0.2)

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'[{city_key}] DONE — {changed} permit_status_date values corrected, '
          f'{fetch_failed} detail fetches failed, saved -> {csv_path}')
    return changed, fetch_failed


if __name__ == '__main__':
    summary = []
    for city in CITIES:
        changed, failed = reenrich_city(city['key'], city['base_url'], city['city_hebrew'])
        summary.append((city['key'], changed, failed))
        print()

    print('=== Summary ===')
    for city_key, changed, failed in summary:
        print(f'  {city_key}: {changed} corrected, {failed} failed')
