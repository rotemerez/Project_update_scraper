# Session Handoff — 2026-07-02 C

**Date:** 2026-07-02
**Session:** P
**Scope:** Holon matcher; הסתיים fix; status reference artifact; Krayot scrape detail phase

---

## What was accomplished

### 1. Holon matcher — first run complete

- **Input**: `docs/holon_28062026.xlsx` (500 projects) + `outputs/holon_fresh.csv` (21,039 rows)
- **Output**: `outputs/holon_report.xlsx` — **197 rows**: 0 `new_permit`, 194 `status_advanced`, 3 `untracked`
- **Cache**: `outputs/holon_matched_cache.json` (2,487 permits)
- This was run BEFORE the `הסתיים` fix (see below). A second run was started at ~13:18.

### 2. Matcher fix — `הסתיים` projects (`transform/matcher.py`)

**Bug**: `'הסתיים'` was missing from `DB_STATUS_NORM`. It fell through as `''`, making
`_is_upgrade('', X)` return True for any scraped status — so every permit matched to a
finished project was flagged as `status_advanced`. Discovered via project חסדאי21 in Holon
report (permit 20240552 = minor alterations on a completed building).

**Fix** (lines ~416–435): added a guard block before the status comparison logic:
```python
if db_status_raw == 'הסתיים':
    if (_is_relevant_type(request_type) or _is_relevant_type(bakasha_description)) \
            and _is_recent(permit.get('request_date')):
        report_rows.append(_make_row(flag='untracked', proj=None, ...))
    continue
```
- Minor alteration permit on finished project → silently dropped
- Genuine new construction (relevant type + recent) → surfaces as `untracked` for new BO entry

**Holon re-run** with this fix started at 13:18 — still running at session end (PID 28880,
CPU ~1788s). Result not yet available.

### 3. Bartech STATUS_MAP — two new entries

From Krayot list-phase log (`[NEW STATUS]` entries, scrape running with old code):
- `'ישיבה'` → `'בקשה להיתר'` (committee session)
- `'בדיקה גליון דרישות'` → `'בקשה להיתר'` (requirements sheet check)

### 4. Bartech STAGE_TO_STATUS / _UNMAPPED_STAGES — Krayot detail phase

Krayot entered detail phase ~14:00. New entries spotted:
- `STAGE_TO_STATUS`: `'טופס 4'` → `'טופס 4'` (direct Form 4 as stage description)
- `_UNMAPPED_STAGES`: `'ישיבת ועדת משנה לתכנון'` (planning subcommittee session — admin step)

### 5. Status reference artifact

Compiled all status/event strings per scraper (mapped, ignored, new) for user annotation.
URL: https://claude.ai/code/artifact/f89237fb-c5a1-40e8-8155-e14c1d698f32

Key pending decisions for user:
- **Krayot construction milestones** (list-page NEW): `יסודות`, `גמר שלד`, `מהלך בנית השלד`,
  `עבודות גמרים`, `מקלט`, `הודעה על תחילת עבודה` — likely → `'היתר'`
- **Krayot Form 4 variants**: `טופס 4`, `היתר/תעודת גמר`, `הפקת תעודת גמר`, `בקשה לתעודת גמר`,
  `טופס 4 להרצת מערכות`, `טופס איכלוס`, `תנאים לטופס איכלוס`, `בדיקת המבנה לטופס 4`
- **Krayot closed?**: `ביטול היתר`, `החלטה להשהות`, `צו הפסקה מנהלי`
- **Ramat Gan unclassified Complot events**: `אושר בועדה`, `החלטה לאשר בתנאי`, `מאשרים בתנאים`,
  `העברה להוצאת היתר`, `מסירת היתר בניה !`

---

## What to do next session

### 1. Check if Holon re-matcher finished

```powershell
Get-Process -Id 28880 -ErrorAction SilentlyContinue
# if gone:
Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\holon_matcher_log.txt'
```

Expected: `status_advanced` count lower than 194 (הסתיים projects removed).

### 2. Check if Krayot scrape finished

```powershell
Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_krayot.txt' -Tail 5
```

Watch for any additional `[NEW STATUS]` or `[NEW STAGE]` lines not yet in the code.
Then run matcher:
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

### 3. Apply user status annotations

User is annotating the status reference artifact. When annotations arrive:
- `scrapers/bartech/api_scraper.py` — STATUS_MAP / STAGE_TO_STATUS / _KNOWN_CLOSED / _UNMAPPED_STAGES
- `scrapers/complot/api_scraper.py` — EVENT_TO_STATUS / _UNMAPPED_EVENTS
Apply all confirmed mappings before re-running any matchers.

### 4. Re-scrape Ramat Gan (from office IP)

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
Start-Process -FilePath 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  -ArgumentList '-u', 'c:\R_PROJECTS\Project_update_scraper\scripts\run_ramat_gan.py' `
  -WorkingDirectory 'c:\R_PROJECTS\Project_update_scraper' `
  -RedirectStandardOutput 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_ramat_gan_B.txt' `
  -RedirectStandardError  'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_err_ramat_gan_B.txt' `
  -NoNewWindow
```

### 5. Re-scrape Kiryat Ata (optional)

Existing `outputs/kiryat_ata_fresh.csv` has missing `היתר` statuses (old code in memory at scrape time).
If report quality matters, re-scrape with `scripts/run_kiryat_ata.py` from office IP.

---

## State of key files

| File | State |
|---|---|
| `transform/matcher.py` | Updated — `הסתיים` guard block added |
| `scrapers/bartech/api_scraper.py` | Updated — `ישיבה`, `בדיקה גליון דרישות` in STATUS_MAP; `טופס 4` in STAGE_TO_STATUS; `ישיבת ועדת משנה לתכנון` in _UNMAPPED_STAGES |
| `outputs/holon_fresh.csv` | Complete — 21,039 permits |
| `outputs/holon_report.xlsx` | First run: 194 status_advanced, 3 untracked (pre-fix); re-run pending |
| `outputs/holon_matched_cache.json` | 2,487 permits (first run) |
| `outputs/krayot_fresh.csv` | Detail phase running — started ~14:00 2026-07-02 |
| `outputs/kiryat_ata_report.xlsx` | Done — 14 status_advanced, 41 untracked (some statuses missing) |
| `outputs/ramat_gan_fresh.csv` | Stale — scraped while IP-blocked; re-scrape from office needed |
| `docs/Ramat_Gan_Projects_30062026.xlsx` | Ready — waiting on re-scrape |
