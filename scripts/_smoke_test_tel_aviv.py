"""Throwaway smoke test -- NOT part of the scraper build. Validates
scrape_parcels() and scan_license_range() against real known values before
wiring the full runner scripts."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.tel_aviv.scraper import TelAvivPermitsBrowserScraper

scraper = TelAvivPermitsBrowserScraper()
try:
    print('=== PARCEL MODE ===')
    pairs = [('6136', '26'), ('6136', '27'), ('7376', '37'), ('7016', '33'), ('6627', '1')]
    result = scraper.scrape_parcels(pairs)
    print(f'{len(result)} permits found across {len(pairs)} parcel pairs')
    for k, v in result.items():
        print(k, v)

    print('=== SCAN MODE (around confirmed ceiling) ===')
    scan_result = scraper.scan_license_range(start=20260618, consecutive_miss_limit=8, max_queries=15)
    print(f'{len(scan_result)} permits found in scan')
    for k, v in scan_result.items():
        print(k, v)
finally:
    scraper.close()
