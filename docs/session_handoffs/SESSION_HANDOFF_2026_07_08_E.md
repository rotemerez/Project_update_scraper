# Session Handoff — 2026-07-08 E

**Date:** 2026-07-08  
**Session:** E  
**Scope:** Hadera matcher finalized; nationwide scrape pipeline designed

---

## What was accomplished

### 1. Hadera matcher run — 53 rows

Scrape was complete at session start (2,788 permits in `outputs/hadera_fresh.csv`).
Matcher ran and produced `outputs/hadera_report.xlsx`: 8 `status_advanced`, 45 `untracked`.

Two bugs were found and fixed during this run:

**BUG-016** — `בנייה חדשה` (double-yod) not matched by `בניה חדשה` (single-yod).
Hadera Bartech uses the academically preferred double-yod spelling for 311 of its 902
new-construction permits. Fixed by adding both variants to `RELEVANT_TYPE_SUBSTRINGS`
in `transform/matcher.py`. A "New-City Checklist" section was added to `CLAUDE.md`
requiring `df['request_type'].value_counts()` inspection before running the matcher
on any new city.

**Unit minimum gap** — `status_advanced` and `new_permit` branches did not call
`_is_below_unit_minimum`. Single-unit residential permits (e.g. `בית פרטי דו משפחתי`,
`unit_count=1`) were surfacing as status updates for multi-unit projects. Fixed by
computing `waive_unit_min = 'תמ"א 38' in project_sug_bnia` and gating both branches
on `(waive_unit_min or not _is_below_unit_minimum(permit))`. תמ"א 38 projects are
always tracked regardless of unit count per נוהל הקמת פרויקטים.

### 2. Nationwide scrape pipeline designed

A nation-wide (all committees except Tel Aviv + Jerusalem) scrape pipeline was scoped.
Key architectural decisions, all documented in `docs/NEXT_STEPS.md` item 8:

- **Storage: SQLite** — `outputs/permits.db`. Nationwide scale (~1M+ permits across
  ~100 cities) makes per-city CSV files unmanageable for incremental updates.
  pandas reads/writes SQLite natively (`df.to_sql` / `pd.read_sql`); report output
  stays Excel.
- **Scraping: from the office** — fixed IP avoids Complot IP-blocking.
  Task Scheduler or a local cron job triggers runs.
- **Mode: incremental** — refresh cached-matched permits + recent-window scan per city.
  Full scrapes quarterly per city.
- **Projects file: nation-wide** — `docs/all_projects_08072026.xlsx` (24,886 projects,
  162 cities). Backoffice export may be automatable via API (still being investigated).
- **Report: single consolidated file** — all committees in one Excel, `committee` column,
  sorted by committee then flag priority.

---

## What to do in the next session — build the nationwide pipeline

This is a greenfield implementation. Read `docs/NEXT_STEPS.md` first, then proceed in
this order:

### Step 1 — Build the committee registry

**Goal:** A config file that maps every scrapeable city to its scraper type and parameters.

**Source:** `C:\R_PROJECTS\local_committee_scrapers\registry\dispatcher.py`
This file has site_ids for 130+ Complot municipalities. Read it to extract:
- The full city → site_id mapping for Complot cities
- Whether Bartech cities appear there too, or need a separate mapping

**What to build:** `config/committees.py` (or `config/committees.json`).
Each entry should have:
```python
{
    'city_hebrew': 'חדרה',
    'scraper': 'bartech',          # or 'complot' or None (skip)
    'base_url': 'https://hadera.bartech-net.co.il',  # Bartech only
    'site_id': None,               # Complot only
    'exclude': False,              # True for Tel Aviv, Jerusalem, unknown systems
}
```

**Known Bartech base_urls** (from existing runners):
- Holon: `https://www.itur.holon.muni.il`
- Krayot (Kiryat Motzkin / Kiryat Bialik / Kiryat Ata): `https://www.vkrayot.co.il`
- Hadera: `https://hadera.bartech-net.co.il`

**Known Complot site_ids** (from existing runners):
- Bat Yam: auto-detected via `b=` year param (not site_id)
- Kiryat Ata: site_id=32
- Ramat Gan: site_id=3

Cross-reference the 162 cities in `docs/all_projects_08072026.xlsx` against the
dispatcher to find which have known scrapers, which are Tel Aviv / Jerusalem (skip),
and which are unknown / proprietary.

**Exclude from scraping:**
- `תל אביב יפו` (4,817 projects) — proprietary system
- `ירושלים` (1,646 projects) — proprietary system
- Any city where the system is neither Complot nor Bartech

### Step 2 — Design and create the SQLite schema

**Goal:** A single `outputs/permits.db` SQLite database replacing per-city CSV files.

**Suggested schema** (one unified `permits` table):

```sql
CREATE TABLE permits (
    city            TEXT NOT NULL,
    scraper         TEXT NOT NULL,   -- 'complot' or 'bartech'
    request_number  TEXT NOT NULL,
    request_date    TEXT,
    full_address    TEXT,
    block_lot       TEXT,
    request_type    TEXT,
    request_category TEXT,
    requestor       TEXT,
    applicant_name  TEXT,
    migrash         TEXT,
    bakasha_description TEXT,
    shimush_ikari   TEXT,
    unit_count      REAL,
    permit_status   TEXT,
    permit_status_date TEXT,
    manual_review_event TEXT,
    first_event_date TEXT,
    scrape_status   TEXT,
    last_scraped    TEXT,           -- ISO timestamp of last scrape touching this row
    PRIMARY KEY (city, request_number)
);
CREATE INDEX idx_permits_city ON permits(city);
CREATE INDEX idx_permits_status_date ON permits(permit_status_date);
```

**Migration helper:** Write `scripts/migrate_csvs_to_db.py` that loads each existing
city CSV (`outputs/hadera_fresh.csv`, `outputs/kiryat_ata_fresh.csv`, etc.) and
inserts into the DB — so existing scrape data isn't wasted.

### Step 3 — Adapt scrapers to write to SQLite

Each city runner currently does:
```python
df.to_csv('outputs/city_fresh.csv', ...)
```

Change to:
```python
import sqlite3
conn = sqlite3.connect('outputs/permits.db')
df['city'] = 'חדרה'
df['scraper'] = 'bartech'
df['last_scraped'] = datetime.now().isoformat()
df.to_sql('permits', conn, if_exists='replace', index=False,
          method='multi')   # use INSERT OR REPLACE via method param or upsert logic
conn.close()
```

For incremental runs, upsert by `(city, request_number)` rather than replacing the
whole city's data. A helper in `transform/db.py` is the right place for this logic.

### Step 4 — Build the nationwide runner

**Goal:** `scripts/run_all.py` — iterates the registry, runs each city's scraper
(incremental mode), then runs each city's matcher, concatenates results.

Skeleton:
```python
from config.committees import COMMITTEES
from transform.matcher import run as match, _compute_min_year
import pandas as pd, sqlite3

all_projects = pd.read_excel('docs/all_projects_08072026.xlsx')
all_projects.columns = [c.strip() for c in all_projects.columns]

report_frames = []
for entry in COMMITTEES:
    if entry['exclude']:
        continue
    city = entry['city_hebrew']
    city_projects = all_projects[all_projects['עיר'] == city].copy()
    if city_projects.empty:
        continue
    min_year = _compute_min_year(city_projects)
    # call scraper (incremental) → writes to DB
    # call matcher against DB slice for this city
    # append returned DataFrame to report_frames

consolidated = pd.concat(report_frames, ignore_index=True)
consolidated.insert(0, 'committee', consolidated['project_id'].map(...))  # or from city col
consolidated.sort_values(['committee', 'flag'], inplace=True)
consolidated.to_excel('outputs/nationwide_report.xlsx', index=False)
```

### Step 5 — Min-year extraction per city

No new code needed. `_compute_min_year(city_projects_df)` already works.
The nationwide runner slices `all_projects_df` by `עיר` for each city and passes
the slice to both the scraper (as `min_year`) and the matcher.

---

## Pending tasks not related to nationwide pipeline

These are still open from earlier sessions — do them when returning to per-city work:

### Classify Hadera unmapped stages (artifact)

Artifact: https://claude.ai/code/artifact/c0dae2d0-319e-4123-b580-332c90957984
Use search + bulk-ignore. After export, add to `scrapers/bartech/api_scraper.py`:
- `STAGE_TO_STATUS` entries → real milestones
- `_UNMAPPED_STAGES` entries → admin noise (silences `[NEW STAGE]` warnings)

### Kiryat Ata report review (59 `manual_review` rows)

`outputs/kiryat_ata_report.xlsx` (89 rows). Focus on:
- `manual_review_event = 'ביטול היתר'` — likely stalled project
- `manual_review_event = 'החלטת ועדת ערר'` — appeal committee, outcome unknown
- `manual_review_event = 'הפקת פרסום תמ"38'` — תמ"א 38 publication

### Request 20250178 — wrong-project match

Sub-permit for project 20250142 matched via shared parcel. Known issue, no fix yet.

---

## State of key files

| File | State |
|---|---|
| `transform/matcher.py` | Updated this session — BUG-016 fix + unit minimum on status_advanced/new_permit |
| `outputs/hadera_report.xlsx` | Final — 53 rows (8 status_advanced, 45 untracked) |
| `outputs/hadera_fresh.csv` | Complete — 2,788 permits |
| `outputs/hadera_matched_cache.json` | 374 permits |
| `outputs/kiryat_ata_report.xlsx` | Valid — 89 rows (59 manual_review pending review) |
| `docs/all_projects_08072026.xlsx` | Nation-wide projects file — 24,886 projects, 162 cities |
| `docs/BUG_REFERENCE.md` | Updated — BUG-016 added |
| `docs/NEXT_STEPS.md` | Updated — session E done, V2 architecture (item 8), unit 9 backoffice writes |
| `CLAUDE.md` | Updated — New-City Checklist section added |
| `config/` | Does not exist yet — create in next session |
| `outputs/permits.db` | Does not exist yet — create in next session |
| `scripts/diagnose_hadera.py` | Temporary diagnostic — can be deleted |
| `scripts/diagnose_hadera2.py` | Temporary diagnostic — can be deleted |
