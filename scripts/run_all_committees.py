"""
Consolidated multi-committee report runner (V2).

Loops over committees with a verified matcher configuration and an existing
fresh scrape CSV, runs transform.matcher.run() for each, and merges the
results into one Excel file with a `committee` column, sorted by committee
then by flag priority (status_advanced -> new_permit -> untracked -> manual_review).

Committees without a fresh scrape yet are skipped (logged, not silently
dropped). Add a new committee by appending an entry to COMMITTEE_CONFIGS,
copied exactly from that committee's existing scripts/run_<name>_matcher.py --
do not guess projects_path / city_filter / permit_url_base for a committee
that hasn't been matched individually at least once.

Run from project root:
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\run_all_committees.py
"""

import os

import pandas as pd

from transform.matcher import run

# 'cities' is metadata for this script only (not passed to matcher.run()) --
# used to fill in the `city` column for report rows where no project matched
# (matcher.py only knows the real city for matched rows, via the project's
# own 'עיר' field). Only safe to backfill when the committee covers exactly
# one city; multi-city committees leave those rows blank rather than guess
# (permit addresses use inconsistent city spelling/hyphenation across
# scraped sites, so parsing the address back into a city name is unreliable).
COMMITTEE_CONFIGS = [
    dict(
        committee='חדרה',
        cities=['חדרה'],
        projects_path='docs/Hadera_Projects_08072026.xlsx',
        permits_path='outputs/hadera_fresh.csv',
        city_hebrew='חדרה',
        output_path='outputs/hadera_report.xlsx',
        matched_cache_path='outputs/hadera_matched_cache.json',
        permit_url_base='https://hadera.bartech-net.co.il/PermitApplicationDetails?Entity_Number=',
    ),
    dict(
        committee='הראל',
        cities=['מבשרת ציון'],
        projects_path='docs/all_projects_08072026.xlsx',
        permits_path='outputs/harel_fresh.csv',
        city_hebrew='מבשרת ציון',
        output_path='outputs/harel_report.xlsx',
        matched_cache_path='outputs/harel_matched_cache.json',
        permit_url_base='https://www.v-harel.co.il/PermitApplicationDetails?Entity_Number=',
        city_filter=['מבשרת ציון'],
    ),
    dict(
        committee='מיצפה אפק',
        cities=['באר יעקב'],
        projects_path='docs/all_projects_08072026.xlsx',
        permits_path='outputs/mitzpe_afek_fresh.csv',
        city_hebrew='באר יעקב',
        output_path='outputs/mitzpe_afek_report.xlsx',
        matched_cache_path='outputs/mitzpe_afek_matched_cache.json',
        permit_url_base='https://www.vmm.co.il/PermitApplicationDetails?Entity_Number=',
        city_filter=['באר יעקב'],
    ),
    dict(
        committee='זמורה',
        cities=['מזכרת בתיה'],
        projects_path='docs/all_projects_08072026.xlsx',
        permits_path='outputs/zmora_fresh.csv',
        city_hebrew='מזכרת בתיה',
        output_path='outputs/zmora_report.xlsx',
        matched_cache_path='outputs/zmora_matched_cache.json',
        permit_url_base='https://www.zmora.org.il/PermitApplicationDetails?Entity_Number=',
        city_filter=['מזכרת בתיה'],
    ),
    dict(
        committee='ישובי הברון',
        cities=['זכרון יעקב', 'אור עקיבא', 'בנימינה גבעת עדה', "ג'סר א זרקא"],
        projects_path='docs/all_projects_08072026.xlsx',
        permits_path='outputs/yishuvei_habaron_fresh.csv',
        city_hebrew='ישובי הברון',
        output_path='outputs/yishuvei_habaron_report.xlsx',
        matched_cache_path='outputs/yishuvei_habaron_matched_cache.json',
        city_filter=['זכרון יעקב', 'אור עקיבא', 'בנימינה גבעת עדה', "ג'סר א זרקא"],
    ),
    dict(
        committee='מורדות כרמל',
        cities=['טירת הכרמל', 'נשר'],
        projects_path='docs/all_projects_08072026.xlsx',
        permits_path='outputs/mordot_carmel_fresh.csv',
        city_hebrew='מורדות כרמל',
        output_path='outputs/mordot_carmel_report.xlsx',
        matched_cache_path='outputs/mordot_carmel_matched_cache.json',
        permit_url_base='https://mordotcarmel.org/iturbakashot/#request/',
        city_filter=['טירת הכרמל', 'נשר'],
    ),
]

FLAG_ORDER = ['status_advanced', 'new_permit', 'untracked', 'manual_review']

OUTPUT_PATH = 'outputs/consolidated_report.xlsx'


def main():
    reports = []
    skipped = []

    for cfg in COMMITTEE_CONFIGS:
        committee = cfg['committee']
        cities = cfg['cities']
        if not os.path.exists(cfg['permits_path']):
            skipped.append((committee, cfg['permits_path']))
            continue

        run_kwargs = {k: v for k, v in cfg.items() if k not in ('committee', 'cities')}
        print(f'\n=== {committee} ===')
        report_df = run(**run_kwargs)
        report_df = report_df.copy()

        # matcher.py only knows the real city for matched rows (from the project's
        # own 'עיר' field). Single-city committees can safely backfill the blanks
        # (untracked / unmatched manual_review rows); multi-city ones are left blank.
        if 'city' in report_df.columns and len(cities) == 1:
            report_df['city'] = report_df['city'].replace('', cities[0]).fillna(cities[0])

        report_df.insert(0, 'committee', committee)
        reports.append(report_df)

    if skipped:
        print('\n[SKIPPED] No fresh scrape CSV found for:')
        for committee, path in skipped:
            print(f'  {committee} -- expected {path}')

    if not reports:
        print('[ERROR] No committee reports produced -- nothing written.')
        return

    merged = pd.concat(reports, ignore_index=True)

    # Put committee/city up front -- these are the columns colleagues filter by first.
    lead_cols = [c for c in ('committee', 'city', 'flag') if c in merged.columns]
    merged = merged[lead_cols + [c for c in merged.columns if c not in lead_cols]]

    if 'flag' in merged.columns:
        merged['flag'] = pd.Categorical(merged['flag'], categories=FLAG_ORDER, ordered=True)
        merged = merged.sort_values(['committee', 'city', 'flag']).reset_index(drop=True)

    os.makedirs('outputs', exist_ok=True)
    merged.to_excel(OUTPUT_PATH, index=False)

    print(f'\n[OK] Consolidated report written to {OUTPUT_PATH} '
          f'({len(merged)} rows across {len(reports)} committees)')
    print('\n[Summary by committee]')
    if 'flag' in merged.columns:
        print(merged.groupby('committee', observed=True)['flag'].value_counts().unstack(fill_value=0))


if __name__ == '__main__':
    main()
