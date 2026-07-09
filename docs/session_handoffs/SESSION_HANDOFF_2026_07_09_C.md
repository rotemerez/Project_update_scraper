# Session Handoff — 2026-07-09 C

**Date:** 2026-07-09  
**Session:** H  
**Scope:** Doc trimming; 8 new city runner scripts; Bartech scraper updated from vmm.co.il smoke test

---

## What was accomplished

### 1. NEXT_STEPS.md + global CLAUDE.md trimmed

- `docs/NEXT_STEPS.md`: 724 → ~190 lines. Old Done history (sessions E and older) archived to
  `docs/session_handoffs/DONE_ARCHIVE.md`.
- `C:\Users\Rotem\.claude\CLAUDE.md`: 147 → ~90 lines. Removed: ILA-specific Python path (lines 21–22),
  "How to Specify Model" block, "Cost Reduction Best Practices" block, "Documentation Standards",
  "Auto-Documentation Triggers", "Documentation Review Checklist".

### 2. `transform/matcher.py` — `city_filter` parameter added

New optional param `city_filter: Optional[List[str]]`. When set, filters `projects_df` by
`'עיר'` column after loading. Also fixed address matching to use `proj_row.get('עיר', city_hebrew)`
per-project instead of the global `city_hebrew` string — needed for multi-city committees. Backward
compatible: all existing callers work unchanged.

### 3. 8 runner scripts created

All use `docs/all_projects_08072026.xlsx` as the projects source (filtered by city in-script).

**Scraper runners:**

| Script | System | Cities |
|---|---|---|
| `scripts/run_mordot_carmel.py` | Complot site_id=61 | טירת הכרמל, נשר |
| `scripts/run_mitzpe_afek.py` | Bartech vmm.co.il | באר יעקב |
| `scripts/run_zmora.py` | Bartech zmora.org.il | מזכרת בתיה |
| `scripts/run_harel.py` | Bartech v-harel.co.il | מבשרת ציון |

**Matcher runners** (same 4, `*_matcher.py` suffix):
- All use `docs/all_projects_08072026.xlsx` with `city_filter=[...]`
- `permit_url_base` set to each portal's `PermitApplicationDetails?Entity_Number=` URL
- מורדות כרמל uses `city_filter=['טירת הכרמל', 'נשר']` and `city_hebrew='מורדות כרמל'`

### 4. Bartech scraper updated — `scrapers/bartech/api_scraper.py`

From vmm.co.il (מיצפה אפק) 2-page smoke test. Zero `[NEW STATUS]` / `[NEW STAGE]` warnings after update.

**STATUS_MAP additions** (list-page statuses → `'בקשה להיתר'`):
- `ישיבה` (was missing despite Session P note — now confirmed added)
- `בקשה עומדת בתנאים מוקדמים`
- `לאחר פרסום אי עמידה בתנאים מוקדמים` (also in _UNMAPPED_STAGES as detail-stage)
- `בדיקה מרחבית אינה תקינה` (also in _UNMAPPED_STAGES)
- `בדיקה מרחבית תקינה` (also in _UNMAPPED_STAGES)
- `בקרת תכן אינה תקינה` (also in _UNMAPPED_STAGES)

**STAGE_TO_STATUS additions** (detail-page stages → `'היתר'`):
- `אישור לתחילת עבודות` — approval to start construction (post-permit milestone)
- `מתן אישור התחלת עבודה` — same meaning, different wording

**`_UNMAPPED_STAGES` additions** (~20 entries, tagged `# מיצפה אפק`):
`שיבוץ לישיבת רישוי מקומית`, `חישוב פקדון`, `בדיקת מפקח`, `מתן היתר בניה`,
`הפקת היתר בניה`, `בקרת תכן ע"י הוועדה תקינה - העברה לסיכום להפקת דרישות תשלום`,
`הפקת מכתב החלטה`, `שיחת טלפון עם מבקש הבקשה`, `הפקת ערבות`,
`העברת הבקשה לפיקוח`, `העברה לבודקת היתרים`,
`בקשה עומדת בבדיקת תנאים מוקדמים (קבלת הבקשה)`, `העברת בקשה לבודקות תוכניות`,
`בקרה מרחבית אינה תקינה נשלחו הערות לעורך`, `הגשת תיקונים רישוי זמין בשלב בקרה מרחבית`,
`אישור מהנדסת הוועדה לשיבוץ לישיבה`, `סיום טיפול היטל השבחה`,
`העברת הבקשה לשמאי לחישוב השבחה`, `לסרב`,
`בקרת תכן ע"י הוועדה אינה תקינה - נשלחו הערות לעורך`, `הגשת אישורים לביצוע בקרת תכן`,
`דו"ח מפקח`, `נשלח נוסח פרסום לעורך הבקשה במייל`

### 5. API reachability confirmed

- **vmm.co.il** (מיצפה אפק): HTTP 200, 5,627 pages type 51, working from home.
- **zmora.org.il** (זמורה): HTTP 200, accessible from home — **not yet smoke-tested**.
- **v-harel.co.il** (הראל): HTTP 200, accessible from home — **not yet smoke-tested**.
- **handasi.complot.co.il** (מורדות כרמל): WAF blocks from home IP. Needs office network.

---

## Open questions / caveats

**zmora.org.il and v-harel.co.il not smoke-tested.** Only confirmed HTTP 200 with 5 permit links on
page 1 of type 51. Before launching a full scrape, run `scraper.max_pages = 2` to check for any
new `[NEW STATUS]` / `[NEW STAGE]` entries specific to those portals. They likely share many stages
with vmm.co.il, but confirm.

**מורדות כרמל — Complot API untested.** The API at `handasi.complot.co.il/handasi2016/api/BakashotHandasa/GetBakashotByNumber/61`
was WAF-blocked from home. Cannot confirm whether site_id=61 actually returns data until tested from
the office network.

---

## What to do in the next session

### Priority 1 — Run the 3 Bartech scrapers (from home or office)

**Before each full scrape, do a 2-page smoke test:**
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
$env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' -c "
from scrapers.bartech.api_scraper import BartechPermitsAPI
scraper = BartechPermitsAPI(base_url='https://www.zmora.org.il', city_name_hebrew='מזכרת בתיה', min_year=2015)
scraper.max_pages = 2
permits = scraper.scrape()
print(f'{len(permits)} permits')
"
```
Then do the same for v-harel.co.il. If zero new warnings, launch the full scrape with `Start-Process`.

**Full scrape launch template:**
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
$env:PYTHONUTF8 = '1'
Start-Process `
  -FilePath 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  -ArgumentList 'c:\R_PROJECTS\Project_update_scraper\scripts\run_mitzpe_afek.py' `
  -WorkingDirectory 'c:\R_PROJECTS\Project_update_scraper' `
  -RedirectStandardOutput 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_mitzpe_afek.txt' `
  -RedirectStandardError  'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_err_mitzpe_afek.txt' `
  -NoNewWindow
```
Repeat with `run_zmora.py` and `run_harel.py`.

### Priority 2 — Run מורדות כרמל (Complot) from office

1. Test: `GET https://handasi.complot.co.il/handasi2016/api/BakashotHandasa/GetBakashotByNumber/61`
   — confirm JSON array response (not HTML).
2. Launch `scripts/run_mordot_carmel.py` from office with `Start-Process`.

### Priority 3 — Run matchers after each scrape completes

For each city, once `*_fresh.csv` exists, run the corresponding `*_matcher.py`:
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
$env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  scripts\run_mitzpe_afek_matcher.py
```
Check the `request_type` value counts printed by the scraper — look for double-yod spelling variants
not yet in `RELEVANT_TYPE_SUBSTRINGS` in `transform/matcher.py`.

---

## State of key files

| File | State |
|---|---|
| `docs/NEXT_STEPS.md` | Updated — session H done; Immediate updated with run instructions |
| `transform/matcher.py` | Updated — `city_filter` param added |
| `scrapers/bartech/api_scraper.py` | Updated — 6 STATUS_MAP + 2 STAGE_TO_STATUS + ~20 _UNMAPPED_STAGES from vmm.co.il |
| `scripts/run_mordot_carmel.py` | New — ready, needs office IP |
| `scripts/run_mitzpe_afek.py` | New — ready, smoke-tested OK |
| `scripts/run_zmora.py` | New — ready, not yet smoke-tested |
| `scripts/run_harel.py` | New — ready, not yet smoke-tested |
| `scripts/run_*_matcher.py` (×4) | New — all 4 matcher runners ready |
| `outputs/mordot_carmel_fresh.csv` | Does not exist yet |
| `outputs/mitzpe_afek_fresh.csv` | Does not exist yet |
| `outputs/zmora_fresh.csv` | Does not exist yet |
| `outputs/harel_fresh.csv` | Does not exist yet |
| `outputs/kiryat_ata_report.xlsx` | 89 rows — still awaiting manual review |
| `outputs/hadera_report.xlsx` | 53 rows — still awaiting Hadera stage classification |
