"""
Diagnostic: break down db_status for matched projects in the report,
and write a clean comparison table to outputs/bat_yam_matched_table.xlsx.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pandas as pd

REPORT_PATH   = 'outputs/bat_yam_report.xlsx'
OUT_TABLE     = 'outputs/bat_yam_matched_table.xlsx'

df = pd.read_excel(REPORT_PATH)

print(f'\nTotal rows in report: {len(df)}')

print('\n--- db_status distribution ---')
print(df['db_status'].value_counts(dropna=False).to_string())

print('\n--- scraped_status distribution ---')
print(df['scraped_status'].value_counts(dropna=False).to_string())

# Projects whose db_status is NOT טרום בקשה — these are candidates for status_advanced
non_pretarom = df[df['db_status'] != 'טרום בקשה']
print(f'\nProjects with db_status != "טרום בקשה": {len(non_pretarom)}')
if not non_pretarom.empty:
    print(non_pretarom[['project_id', 'project_name', 'db_status', 'scraped_status']].to_string())

# Write comparison table — columns useful for manual review
cols = [
    'project_id',
    'project_name',
    'project_gush_helka',
    'db_status',
    'scraped_status',
    'scraped_status_date',
    'full_address',
    'request_number',
    'request_date',
    'requestor',
    'permit_block_lot',
    'match_method',
]
table = df[[c for c in cols if c in df.columns]].copy()
table.to_excel(OUT_TABLE, index=False)
print(f'\n[OK] Comparison table written to {OUT_TABLE} ({len(table)} rows)')
