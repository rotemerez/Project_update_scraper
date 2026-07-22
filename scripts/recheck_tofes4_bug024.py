"""
Targeted BUG-024 re-check — re-fetches GetBakashaFile (via scrape_targeted, no list-phase
rescrape) ONLY for permits currently flagged scraped_status=='טופס 4' in the Ashkelon and
Mordot Carmel matcher reports, to see if any were false positives from the now-fixed
'הרצת מערכות' event-mapping bug (BUG-024).

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\recheck_tofes4_bug024.py
"""

import pandas as pd
from scrapers.complot.api_scraper import ComplotPermitsAPI

CITIES = [
    {'key': 'ashkelon',      'site_id': 95, 'city_hebrew': 'אשקלון'},
    {'key': 'mordot_carmel', 'site_id': 61, 'city_hebrew': 'טירת הכרמל'},
]


def recheck_city(key: str, site_id: int, city_hebrew: str):
    report_path = f'outputs/{key}_report.xlsx'
    csv_path = f'outputs/{key}_fresh.csv'

    report = pd.read_excel(report_path, dtype=str)
    target_nums = set(report[report['scraped_status'] == 'טופס 4']['request_number'].astype(str))
    print(f'[{key}] {len(target_nums)} report rows at טופס 4 to re-check')

    df = pd.read_csv(csv_path, encoding='utf-8-sig', dtype=str)
    subset = df[df['request_number'].astype(str).isin(target_nums)]
    records = subset.to_dict('records')

    scraper = ComplotPermitsAPI(site_id=site_id, city_name_hebrew=city_hebrew)
    refreshed = scraper.scrape_targeted(records)

    refreshed_by_num = {r['request_number']: r for r in refreshed}
    changed = []
    for idx, row in subset.iterrows():
        num = str(row['request_number'])
        new = refreshed_by_num.get(num)
        if not new:
            continue
        old_status = row['permit_status']
        new_status = new['permit_status']
        old_date = row['permit_status_date']
        new_date = new['permit_status_date']
        if old_status != new_status or old_date != new_date:
            changed.append((num, old_status, new_status, old_date, new_date))
        df.loc[df['request_number'].astype(str) == num, 'permit_status'] = new_status
        df.loc[df['request_number'].astype(str) == num, 'permit_status_date'] = new_date

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'[{key}] DONE — {len(changed)} permits changed:')
    for num, os_, ns, od, nd in changed:
        print(f'    {num}: status {os_!r} -> {ns!r}, date {od!r} -> {nd!r}')
    return changed


if __name__ == '__main__':
    all_changed = {}
    for city in CITIES:
        all_changed[city['key']] = recheck_city(city['key'], city['site_id'], city['city_hebrew'])
        print()

    print('=== Summary ===')
    for key, changed in all_changed.items():
        print(f'  {key}: {len(changed)} permits changed')
