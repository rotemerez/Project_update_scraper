"""
Weekly-refresh watcher for the Madlan projects export.

The full pipeline (Looker export -> outputs/madlan_projects_fresh.csv) still needs a human
(or an interactive Claude Desktop session) to run the Looker MCP connector -- that step cannot
be scheduled/headless (interactive-auth MCP servers are unavailable in cron/headless runs).
This script automates everything AFTER the CSV lands:

  1. If outputs/madlan_projects_fresh.csv is newer than outputs/madlan_projects_fresh.xlsx (or the
     xlsx doesn't exist yet), convert it via fetch_projects.from_csv() -- same logic the manual
     workflow already used, no duplication.
  2. Compare the resulting xlsx against the CURRENT production projects file
     (docs/all_projects.xlsx) on project-ID overlap and city coverage, the same sanity
     check done manually on 2026-07-20 (that run found 42 cities missing from a fresh export,
     including קצרין -- see docs/NEXT_STEPS.md Session U). Flags loudly if something looks off.
  3. Appends a timestamped block to outputs/projects_refresh_check_log.txt so a scheduled/headless
     run leaves a readable trail -- this script prints nothing assuming a human is watching.

Auto-promotes the new export over docs/all_projects.xlsx (the stable production filename every
script in this project references) ONLY when the scope/grain sanity check passes cleanly --
if city coverage narrows meaningfully or the row-per-project grain looks off, promotion is
skipped and left for a human to investigate (see the 2026-07-20 precedent in docs/NEXT_STEPS.md
Session U, where a since-fixed Looker join bug doubled the row count and, separately, one export
was missing 42 cities). This is what makes the weekly refresh actually zero-touch: no script ever
needs its projects_path updated again, since the filename never changes -- only its contents do.

Run from project root (also the command a scheduled task should call):
  PYTHONPATH=c:\\R_PROJECTS\\Project_update_scraper ^
  C:\\Users\\Rotem\\AppData\\Local\\Programs\\Python\\Python313\\python.exe ^
  scripts\\check_projects_refresh.py
"""

import os
import shutil
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_projects import from_csv, OUTPUT_PATH  # noqa: E402

CSV_PATH = 'outputs/madlan_projects_fresh.csv'
PRODUCTION_PROJECTS_PATH = 'docs/all_projects.xlsx'
LOG_PATH = 'outputs/projects_refresh_check_log.txt'

# Alert thresholds -- tuned from the 2026-07-20 incident (42/162 cities silently missing,
# and separately a Looker LEFT JOIN bug that doubled rows/project).
MAX_ACCEPTABLE_MISSING_CITIES = 5
MAX_ACCEPTABLE_ID_DROP_PCT = 5.0
MAX_ACCEPTABLE_GRAIN_RATIO = 1.2  # new rows/project vs production's -- >20% higher is suspicious


def _log(f, msg: str):
    print(msg)
    f.write(msg + '\n')


def _compare_scope(f, new_path: str) -> bool:
    """Returns True if the new export is safe to promote over the production file."""
    old = pd.read_excel(PRODUCTION_PROJECTS_PATH)
    new = pd.read_excel(new_path)
    old.columns = [c.strip() for c in old.columns]
    new.columns = [c.strip() for c in new.columns]

    old_ids = set(old['מזהה פרויקט'].dropna())
    new_ids = set(new['מזהה פרויקט'].dropna())
    old_cities = set(old['עיר'].dropna())
    new_cities = set(new['עיר'].dropna())
    missing_cities = old_cities - new_cities
    id_drop_pct = 100.0 * len(old_ids - new_ids) / len(old_ids) if old_ids else 0.0
    old_rows_per_id = len(old) / len(old_ids) if old_ids else 0
    new_rows_per_id = len(new) / len(new_ids) if new_ids else 0

    _log(f, f'  Production file ({PRODUCTION_PROJECTS_PATH}): {len(old)} rows, '
            f'{len(old_ids)} unique IDs, {len(old_cities)} cities, '
            f'{old_rows_per_id:.2f} rows/project')
    _log(f, f'  New export ({new_path}): {len(new)} rows, {len(new_ids)} unique IDs, '
            f'{len(new_cities)} cities, {new_rows_per_id:.2f} rows/project')
    _log(f, f'  IDs: {len(old_ids - new_ids)} dropped, {len(new_ids - old_ids)} added, '
            f'{len(old_ids & new_ids)} shared ({id_drop_pct:.1f}% dropped)')

    alert = False
    if missing_cities:
        _log(f, f'  Cities in production but ABSENT from new export ({len(missing_cities)}): '
                f'{sorted(missing_cities)}')
        if len(missing_cities) > MAX_ACCEPTABLE_MISSING_CITIES:
            alert = True
    if id_drop_pct > MAX_ACCEPTABLE_ID_DROP_PCT:
        alert = True
    # Grain check -- catches a recurrence of the 2026-07-20 Looker LEFT JOIN artifact
    # (doubled rows/project) before it ever reaches the production file.
    if old_rows_per_id > 0 and new_rows_per_id > old_rows_per_id * MAX_ACCEPTABLE_GRAIN_RATIO:
        _log(f, f'  Rows/project ratio looks off: new export has {new_rows_per_id:.2f} vs '
                f'production\'s {old_rows_per_id:.2f} -- possible join/grain artifact.')
        alert = True

    if alert:
        _log(f, '  [ALERT] New export looks meaningfully different from the production file -- '
                'NOT auto-promoted. Investigate before manually replacing '
                f'{PRODUCTION_PROJECTS_PATH} (see docs/NEXT_STEPS.md Session U for the '
                '2026-07-20 precedent).')
    else:
        _log(f, '  [OK] Scope and grain look consistent with the production file.')
    return not alert


def main():
    os.makedirs('outputs', exist_ok=True)
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _log(f, f'\n=== {now} ===')

        if not os.path.exists(CSV_PATH):
            _log(f, f'  No {CSV_PATH} found -- nothing to do.')
            return

        csv_mtime = os.path.getmtime(CSV_PATH)
        xlsx_mtime = os.path.getmtime(OUTPUT_PATH) if os.path.exists(OUTPUT_PATH) else 0

        if csv_mtime <= xlsx_mtime:
            _log(f, f'  {CSV_PATH} is not newer than {OUTPUT_PATH} -- already processed, nothing to do.')
            return

        _log(f, f'  {CSV_PATH} is newer than {OUTPUT_PATH} -- converting...')
        from_csv(CSV_PATH)
        _log(f, f'  Converted -> {OUTPUT_PATH}')

        if not os.path.exists(PRODUCTION_PROJECTS_PATH):
            _log(f, f'  [WARN] {PRODUCTION_PROJECTS_PATH} not found -- skipping scope comparison.')
            return

        safe_to_promote = _compare_scope(f, OUTPUT_PATH)
        if safe_to_promote:
            shutil.copyfile(OUTPUT_PATH, PRODUCTION_PROJECTS_PATH)
            _log(f, f'  [PROMOTED] {OUTPUT_PATH} -> {PRODUCTION_PROJECTS_PATH}')


if __name__ == '__main__':
    main()
