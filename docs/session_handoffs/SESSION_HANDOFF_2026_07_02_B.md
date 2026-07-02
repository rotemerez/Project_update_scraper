# Session Handoff — 2026-07-02 B

**Date:** 2026-07-02
**Session:** O
**Scope:** Kiryat Ata matcher; Krayot scrape started; Bartech scraper improvements

---

## What was accomplished

### 1. Kiryat Ata matcher — complete

- **Input**: `docs/Kiryat_Ata_Projects_30062026.xlsx` + `outputs/kiryat_ata_fresh.csv` (3,318 permits)
- **Output**: `outputs/kiryat_ata_report.xlsx` — **55 rows**: 14 `status_advanced`, 41 `untracked`, 0 `new_permit`
- **Cache**: `outputs/kiryat_ata_matched_cache.json` (704 matched permits)

**Known data quality caveat**: The Kiryat Ata scrape started before `הוצאת היתר בניה` → `היתר`
was applied (fix was in memory from session N's code change, but the running process loaded the
old module). Permits where `הוצאת היתר בניה` was the only milestone show empty `permit_status`.
This means `status_advanced` may be slightly under-counted. The fix is already in the code — a
re-scrape would produce accurate data, but is optional for now.

### 2. Complot scraper — 41 new _UNMAPPED_EVENTS

Added from Kiryat Ata log — admin/routing events, staff-name events, publication and
precondition stages. See `scrapers/complot/api_scraper.py` lines 143+.

### 3. Krayot scrape — running

- URL: `https://www.vkrayot.co.il` (Bartech)
- `city_name_hebrew='קריות'` — regional label; individual city names in scraped addresses
- `min_year=2009` (auto-computed from `docs/krayot_projects_30062026.xlsx`, 534 projects)
- **Type 51: 4,944 pages**; types 71: 343, 72: 228, 73: 3 → total ~5,518 list pages
- Runner: `scripts/run_krayot.py`
- Log: `outputs/scrape_log_krayot.txt`
- Started: ~08:58 2026-07-02 at page 82/4944 when last checked
- **Estimated completion: ~14:00–15:00 2026-07-02** (4-6 hours from start)

### 4. Bartech scraper — significant improvements

**`scrapers/bartech/api_scraper.py`** updated:

**List-phase min_year filter** (new): old permits are now excluded from `seen` during list
phase — they're never added to the output at all. Previously `min_year` only controlled detail
page fetching; old permits were still collected and output as rows without detail data.

**Runner scripts now auto-compute min_year** from the projects file using `_compute_min_year`:
- `scripts/run_krayot.py` — reads `docs/krayot_projects_30062026.xlsx`
- `scripts/run_holon.py` — reads `docs/holon_28062026.xlsx`
Pattern: `min_year = _compute_min_year(projects_df)` then passed to `BartechPermitsAPI`.
**Never hardcode min_year — always derive from the projects file.**

**New STATUS_MAP entries** (from Krayot list pages):
- `'היתר'` → `'היתר'`
- `'היתר/תחילת עבודות'` → `'היתר'`
- `'היתר/טופס 4'` → `'טופס 4'`
- `'הגשה'` → `'בקשה להיתר'`
- `'עמידה בתנאים מוקדמים'` → `'בקשה להיתר'`
- `'אי עמידה בתנאים מוקדמים'` → `'בקשה להיתר'`
- `'אי עמידה בתנאים מוקדמים לצורך פרסום'` → `'בקשה להיתר'`
- `'קבלת תוכנית מתוקנת'` → `'בקשה להיתר'`
- `'תשלום פקדון'` → `'בקשה להיתר'`
- `'הפקת אגרה'` → `'בקשה להיתר'`
- `'החלטה לאשר'` → `'היתר בתנאים'`
- `'החלטה לדחות'` → added to `_KNOWN_CLOSED`

**New STAGE_TO_STATUS entries** (from Krayot detail pages):
- `'הוצאת היתר בניה'` → `'היתר'`
- `'הפקת אישור לתחילת עבודות'` → `'היתר'`
- `'החלטה לאשר'` → `'היתר בתנאים'` (replaced old key `'החלטה לאשר הבקשה'` — shorter
  prefix so both `'החלטה לאשר'` and `'החלטה לאשר הבקשה'` now match via `in` check)

**New _UNMAPPED_STAGES** (Krayot Rishuy Zamin + committee workflow — 20 entries):
`הגשת בקשה להיתר במערכת רישוי זמין`, `קבלת בקשה (עמידה בתנאים מוקדמים)`,
`קבלת תיקונים מעורך הבקשה`, `העברה לתיקונים לעורך הבקשה`,
`דחיית הבקשה (אינה עומדת בתנאים מוקדמים)`, `העברת תוכנית לעיריה`, `קבלת תוכנית מהעיריה`,
`שיבוץ בקשה לישיבה`, `ישיבת הועדה המקומית לתכנון ולבניה`, `שליחת מכתבי החלטה`,
`פירסום הקלה`, `בקשה עומדת/אינה עומדת בתנאים מוקדמים לצורך הפקת נוסח פרסום`,
`בדיקת חבות היטל השבחה`, `אישור תשלום אגרות עירייה ותאגיד המים`,
`בקרת תכן אינה תקינה`, `בקרה מרחבית תקינה/אינה תקינה`, `הגשת בקשה לבקרת תכן`,
`הפקת טופס 2`, `הפקת מסמך לשחרור ערבות`, `בקשה לטופס תחילת עבודות`

---

## What to do next session

### 1. Run Krayot matcher (scrape expected done ~14:00–15:00)

```python
from transform.matcher import run as matcher_run
matcher_run(
    'docs/krayot_projects_30062026.xlsx',
    'outputs/krayot_fresh.csv',
    'קריות',
    'outputs/krayot_report.xlsx',
    matched_cache_path='outputs/krayot_matched_cache.json',
)
```

Watch for:
- `[NEW STATUS]` / `[NEW STAGE]` lines in the log — add to Bartech STATUS_MAP / _UNMAPPED_STAGES
- The address matcher uses `קריות` as city label; individual addresses say `קרית ביאליק`,
  `קרית מוצקין`, etc. — GH matching is the primary path (address fallback won't strip city)
- Large committee → expect more rows than Kiryat Ata

### 2. Run Holon matcher

Holon scrape is done: `outputs/holon_fresh.csv` (21,039 rows, 2026-07-02).

```python
from transform.matcher import run as matcher_run
matcher_run(
    'docs/holon_28062026.xlsx',
    'outputs/holon_fresh.csv',
    'חולון',
    'outputs/holon_report.xlsx',
    matched_cache_path='outputs/holon_matched_cache.json',
)
```

### 3. Re-scrape Ramat Gan (from office IP)

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
Start-Process -FilePath 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  -ArgumentList '-u', 'c:\R_PROJECTS\Project_update_scraper\scripts\run_ramat_gan.py' `
  -WorkingDirectory 'c:\R_PROJECTS\Project_update_scraper' `
  -RedirectStandardOutput 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_ramat_gan_B.txt' `
  -RedirectStandardError  'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_err_ramat_gan_B.txt' `
  -NoNewWindow
```

Then matcher with `matched_cache_path='outputs/ramat_gan_matched_cache.json'`.

---

## State of key files

| File | State |
|---|---|
| `scrapers/complot/api_scraper.py` | Updated — 41 new `_UNMAPPED_EVENTS` from Kiryat Ata |
| `scrapers/bartech/api_scraper.py` | Updated — list-phase min_year filter; new STATUS_MAP/STAGE entries |
| `scripts/run_krayot.py` | New — auto-computes min_year from projects file |
| `scripts/run_holon.py` | Updated — auto-computes min_year from projects file |
| `outputs/kiryat_ata_fresh.csv` | Complete — 3,318 permits; some `היתר` statuses missing |
| `outputs/kiryat_ata_report.xlsx` | Done — 14 status_advanced, 41 untracked |
| `outputs/holon_fresh.csv` | Complete — 21,039 permits (2026-07-02) |
| `outputs/krayot_fresh.csv` | Scraping — ~14:00-15:00 completion |
| `outputs/ramat_gan_fresh.csv` | Stale — scraped while IP-blocked; re-scrape from office needed |
| `docs/Kiryat_Ata_Projects_30062026.xlsx` | Used — 3,318 permits |
| `docs/krayot_projects_30062026.xlsx` | Ready — 534 projects, min_year=2009 |
| `docs/Ramat_Gan_Projects_30062026.xlsx` | Ready — waiting on re-scrape |
| `docs/holon_28062026.xlsx` | Ready — 500 projects |
