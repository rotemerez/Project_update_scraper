# Session Handoff — 2026-07-02 A

**Date:** 2026-07-02
**Session:** N
**Scope:** Complot IP block diagnosis; Kiryat Ata scrape started; Holon re-scrape completed

---

## What was accomplished

### 1. Complot IP block diagnosed and resolved

The Ramat Gan scrape (session L) made 4,916 GetBakashaFile calls and triggered an IP-level
block on `handasi.complot.co.il` that affected ALL Complot cities — including the web frontend.
The "city-level restriction" we thought Ramat Gan had was the same block.

**Resolution:** From the office IP the block is lifted. All Complot cities (including Ramat Gan)
should be accessible from the office network.

**Ramat Gan status:** `outputs/ramat_gan_fresh.csv` was scraped while blocked — all detail
fields are empty. A re-scrape from the office IP is needed before the matcher can run.

### 2. Kiryat Ata scrape — running

- `site_id=32`, `city_name_hebrew='קרית אתא'`
- Runner: `scripts/run_kiryat_ata.py` (created this session)
- Projects file: `docs/Kiryat_Ata_Projects_30062026.xlsx`
- List phase complete: **3,318 unique permits** (b=2011–2026)
- Detail phase: started ~07:26 at 0.5s/permit → expected completion ~08:00

**New Complot event mappings added this session:**
- `הוצאת היתר בניה` → `היתר` (added to `EVENT_TO_STATUS` — was producing `[NEW EVENT]` noise)
- `החלטת ועדת ערר` → `_UNMAPPED_EVENTS` (appeals committee decision, outcome unknown)
- 12 new admin/processing events added to `_UNMAPPED_EVENTS`:
  `הפקת מכתבי החלטה`, `בדיקת פיקוח כללית בשטח`, `בטיפול אתי`, `בטיפול צחי`,
  `העברת הבקשה לפיקוח`, `הסכמת השותפים במגרש לבניה`, `חישוב פיקדון`,
  `הוכחת בעלות על הנכס`, `אישור בעלי הנכס + תז`, `ישיבת רשות רישוי מקומית`,
  `מפת קווי בנין`, `מפת מודד מוסמך מעודכנת`

**Kiryat Ata detail page structure** — confirmed same as Bat Yam; parser extracts all fields
correctly. `סוג הבקשה`, `תיאור הבקשה`, events table, applicant, gush/helka all working.

### 3. Holon re-scrape — COMPLETE

Started end of previous session (~17:00 2026-06-30), completed during this session.
Output: `outputs/holon_fresh.csv` — 21,039 rows.

New Bartech unmapped stage added: `אישור לת. גמר, פיקוח בניה` → `_UNMAPPED_STAGES`.

---

## What to do next session

### 1. Run Kiryat Ata matcher (immediate — scrape completing ~08:00)

```python
from transform.matcher import run as matcher_run

matcher_run(
    'docs/Kiryat_Ata_Projects_30062026.xlsx',
    'outputs/kiryat_ata_fresh.csv',
    'קרית אתא',
    'outputs/kiryat_ata_report.xlsx',
    matched_cache_path='outputs/kiryat_ata_matched_cache.json',
)
```

Watch for:
- `[NEW EVENT] Unmapped` lines — add any new ones to `_UNMAPPED_EVENTS`
- `[NEW STATUS] Unmapped` lines — add any new ones to Bartech `_UNMAPPED_STAGES`
- Address matching issues specific to Kiryat Ata street names
- Permit number format: Kiryat Ata uses `YYYYXXXX` (8 digits), regex `r'(20\d{6})'` applies

### 2. Run Holon matcher

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

Expect `status_advanced` to drop sharply from 1,675 — `permit_status_date` is now populated
from the detail-page stage parsing, so `_scraped_date_is_actionable()` will filter correctly.

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

After scrape completes, run matcher:
```python
matcher_run(
    'docs/Ramat_Gan_Projects_30062026.xlsx',
    'outputs/ramat_gan_fresh.csv',
    'רמת גן',
    'outputs/ramat_gan_report.xlsx',
    matched_cache_path='outputs/ramat_gan_matched_cache.json',
)
```

---

## State of key files

| File | State |
|---|---|
| `scrapers/complot/api_scraper.py` | Updated — `הוצאת היתר בניה` → `היתר`; 14 new `_UNMAPPED_EVENTS` |
| `scrapers/bartech/api_scraper.py` | Updated — `אישור לת. גמר, פיקוח בניה` → `_UNMAPPED_STAGES` |
| `scripts/run_kiryat_ata.py` | New — site_id=32 |
| `outputs/kiryat_ata_fresh.csv` | Scraping now — 3,318 permits, detail phase ~08:00 completion |
| `outputs/holon_fresh.csv` | Complete — 21,039 permits (2026-07-02) |
| `outputs/ramat_gan_fresh.csv` | Stale — scraped while IP-blocked; all detail fields empty |
| `docs/Kiryat_Ata_Projects_30062026.xlsx` | Ready — backoffice export for Kiryat Ata |
| `docs/Ramat_Gan_Projects_30062026.xlsx` | Ready — backoffice export for Ramat Gan |
| `docs/holon_28062026.xlsx` | Ready — backoffice export for Holon (500 projects) |
