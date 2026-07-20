"""
Scraper runner for תל אביב יפו (custom Angular SPA + reCAPTCHA Enterprise v3
-gated API, browser-automation scraper -- see scrapers/tel_aviv/scraper.py
and docs/tlv_permit_api_findings.md / docs/tlv_permit_api_findings2.md).

Tel Aviv has ~5,640 unique gush/helka pairs across its Madlan projects --
far more than any other committee scraped so far. At ~10-25s per successful
query (more with reCAPTCHA backoff) the full parcel pass alone is a
24h+ continuous run, and it needs a REAL, visible, non-headless Chrome
window the whole time (reCAPTCHA Enterprise rejects headless sessions) --
it cannot run unattended overnight like the requests-based scrapers.

Per Rotem (2026-07-15): start with `PARCEL_LIMIT` set to a small batch to
validate the scraper holds up over a longer real session before committing
to the full run -- raise/remove the limit once validated.

Three query phases, in order:
  1. Parcel mode  -- search by known gush/helka pairs for existing Madlan
     projects. Establishes the real license-number range actually in use.
  2. Gap-fill      -- scan every licenseId *between* the min/max found in
     phase 1 that phase 1 didn't already surface -- catches permits for
     projects not yet in Madlan whose number falls within the known range,
     without blindly scanning from year 0001 (which would re-check numbers
     phase 1 already covered).
  3. Sequential continue -- scan upward from (max found in phases 1+2) + 1
     to pick up new permits filed since, stopping after a consecutive-miss
     threshold (the sequence has real gaps -- confirmed in recon).

Run from project root (must be able to open a REAL, non-headless Chrome
window):
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_tel_aviv.py
"""
import os
import re

import pandas as pd

from scrapers.tel_aviv.scraper import TelAvivPermitsBrowserScraper

CITY = 'תל אביב יפו'
PROJECTS_PATH = 'docs/all_projects.xlsx'
FRESH_PATH = 'outputs/tel_aviv_fresh.csv'
PARCEL_LIMIT = 150  # validate at this scale first; raise/remove once confirmed stable

# -- load Tel Aviv projects, build the gush/helka pair list -----------------

projects_df = pd.read_excel(PROJECTS_PATH)
projects_df.columns = [c.strip() for c in projects_df.columns]
tlv_projects_all = projects_df[projects_df['עיר'] == CITY]
# Exclude already-occupied (אוכלס = Form 4 received, fully complete) projects
# from the scraper's query target -- they have no reason to show new permit
# activity. Cuts ~31% of query volume (5,640 -> 3,893 pairs, confirmed
# 2026-07-15). matcher.run() still gets the full unfiltered projects_path
# separately -- this only trims what the SCRAPER actively queries.
tlv_projects = tlv_projects_all[tlv_projects_all['סטטוס פרויקט'] != 'אוכלס']
print(f'[INFO] {len(tlv_projects_all)} Tel Aviv project rows total, '
      f'{len(tlv_projects)} non-occupied (scraper target)')

_PAIR_RE = re.compile(r'(\d+)\s*-\s*(\d+)')


def _parse_gush_helka_pairs(cell) -> list:
    if not isinstance(cell, str):
        return []
    return [(g, h) for g, h in _PAIR_RE.findall(cell)]


parcel_pairs = set()
for cell in tlv_projects.get('גוש-חלקה', pd.Series(dtype=str)).dropna():
    parcel_pairs.update(_parse_gush_helka_pairs(cell))
parcel_pairs = sorted(parcel_pairs)
print(f'[INFO] {len(parcel_pairs)} unique gush/helka pairs total')

if PARCEL_LIMIT and len(parcel_pairs) > PARCEL_LIMIT:
    print(f'[INFO] PARCEL_LIMIT={PARCEL_LIMIT} set -- only querying the first '
          f'{PARCEL_LIMIT} pairs this run, not all {len(parcel_pairs)}')
    parcel_pairs = parcel_pairs[:PARCEL_LIMIT]


def _license_number_to_id(license_number: str) -> int:
    # "26-0620" -> 20260620 (format confirmed in docs/tlv_permit_api_findings2.md)
    yy, seq = license_number.split('-')
    return int(f'20{yy}{seq}')


# -- scrape -------------------------------------------------------------------

scraper = TelAvivPermitsBrowserScraper(city_name_hebrew=CITY)
try:
    print(f'\n--- Phase 1: parcel mode ({len(parcel_pairs)} pairs) ---')
    parcel_results = scraper.scrape_parcels(parcel_pairs)
    print(f'[INFO] {len(parcel_results)} permits found via parcel search')

    found_license_ids = sorted({
        _license_number_to_id(r['request_number']) for r in parcel_results.values()
        if re.fullmatch(r'\d{2}-\d{4}', r.get('request_number', ''))
    })

    if found_license_ids:
        lo, hi = found_license_ids[0], found_license_ids[-1]
        gap_candidates = [lid for lid in range(lo, hi + 1) if lid not in set(found_license_ids)]
        print(f'\n--- Phase 2: gap-fill ({len(gap_candidates)} candidates in range {lo}-{hi}) ---')
        gap_results = scraper.scrape_license_ids(gap_candidates)
        print(f'[INFO] {len(gap_results)} additional permits found via gap-fill')

        scan_start = hi + 1
    else:
        print('\n[WARN] No license numbers found in phase 1 (batch limit too small, or '
              'genuinely no permits among these parcels) -- skipping gap-fill and '
              'sequential-continue; nothing to anchor them to.')
        gap_results = {}
        scan_start = None

    scan_results = {}
    if scan_start is not None:
        print(f'\n--- Phase 3: sequential continue from licenseId={scan_start} ---')
        scan_results = scraper.scan_license_range(start=scan_start)
        print(f'[INFO] {len(scan_results)} additional permits found via sequential continue')
finally:
    scraper.close()

# Parcel-mode records carry a real block_lot (the query key itself);
# gap-fill/scan records don't -- prefer parcel's version on overlap.
merged = dict(scan_results)
merged.update(gap_results)
for request_number, record in parcel_results.items():
    if request_number not in merged or not merged[request_number].get('block_lot'):
        merged[request_number] = record
df = pd.DataFrame(list(merged.values()))

print('\n--- request_type value counts (check for double-yod variants) ---')
if 'request_type' in df.columns and not df.empty:
    print(df['request_type'].value_counts().to_string())

os.makedirs('outputs', exist_ok=True)
df.to_csv(FRESH_PATH, index=False, encoding='utf-8-sig')

print(f'\n--- Results ({len(df)} permits) -> {FRESH_PATH} ---')
cols = ['request_number', 'full_address', 'request_type', 'permit_status', 'scrape_status']
if not df.empty:
    print(df[[c for c in cols if c in df.columns]].to_string())
