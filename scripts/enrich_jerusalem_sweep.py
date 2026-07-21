"""
Enriches the existing outputs/jerusalem_sweep.csv (20,693 rows from the
2026-07-20 sweep, all scrape_status='partial') with block_lot/full_address by
calling JerusalemPermitsAPI.resolve_parcel() per request_number
(getGushimContentData + getKtovetContentData) -- the fix that removes the
"manual parcel lookup" gap noted in sweep_by_tik_number()'s original design.

Resumable: writes a checkpoint to outputs/jerusalem_sweep_enrich_checkpoint.csv
every CHECKPOINT_EVERY rows. If that checkpoint exists on startup, resumes
from it instead of outputs/jerusalem_sweep.csv, so an interrupted run doesn't
re-enrich rows it already finished. Only rows still scrape_status='partial'
are processed -- already-'success' rows (from a live sweep run, if any) are
left untouched.

Run from project root (see CLAUDE.md for background-run pattern):
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\enrich_jerusalem_sweep.py
"""

import os
import time

import pandas as pd

from scrapers.jerusalem.api_scraper import JerusalemPermitsAPI, _log

SWEEP_PATH = 'outputs/jerusalem_sweep.csv'
CHECKPOINT_PATH = 'outputs/jerusalem_sweep_enrich_checkpoint.csv'
CHECKPOINT_EVERY = 200

if os.path.exists(CHECKPOINT_PATH):
    df = pd.read_csv(CHECKPOINT_PATH, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    _log(f'[INFO] Resuming from checkpoint {CHECKPOINT_PATH}')
else:
    df = pd.read_csv(SWEEP_PATH, encoding='utf-8-sig', dtype=str, keep_default_na=False)
    _log(f'[INFO] Starting fresh from {SWEEP_PATH}')

todo_idx = df.index[df['scrape_status'] == 'partial'].tolist()
total = len(todo_idx)
_log(f'[INFO] {total} partial rows to enrich ({len(df) - total} already resolved)')

scraper = JerusalemPermitsAPI()

for i, idx in enumerate(todo_idx):
    tik_num = df.at[idx, 'request_number']
    block_lot, full_address = scraper.resolve_parcel(tik_num)
    if block_lot:
        df.at[idx, 'block_lot'] = block_lot
    if full_address:
        df.at[idx, 'full_address'] = full_address
    if block_lot or full_address:
        df.at[idx, 'scrape_status'] = 'success'
    time.sleep(0.3)

    if (i + 1) % CHECKPOINT_EVERY == 0 or (i + 1) == total:
        df.to_csv(CHECKPOINT_PATH, index=False, encoding='utf-8-sig')
        _log(f'  [{i + 1}/{total}] checkpoint saved')

df.to_csv(SWEEP_PATH, index=False, encoding='utf-8-sig')
resolved = (df['scrape_status'] == 'success').sum()
_log(f'[DONE] {resolved}/{len(df)} rows now have block_lot/full_address -> {SWEEP_PATH}')

if os.path.exists(CHECKPOINT_PATH):
    os.remove(CHECKPOINT_PATH)
    _log(f'[INFO] Removed checkpoint {CHECKPOINT_PATH}')
