# Session Handoff — 2026-07-07 A

**Date:** 2026-07-07
**Session:** V
**Scope:** Kiryat Ata report quality — matcher filter fixes, temporal plausibility, permit URL

---

## What was accomplished

### 1. Confirmed project-definition criteria (from נוהל הקמת פרויקטים מאי 2023)

Before touching code, aligned on the criteria that should govern whether a scraped permit
is surfaced in the report:
- Construction type must be trackable (in `RELEVANT_TYPE_SUBSTRINGS`)
- Unit minimum: ≥3 for `בניה חדשה`/`הריסה ובניה` (non-תמ"א); ≥4 for `צמודי קרקע`; no minimum for `תמ"א 38`
- Not a public institution (schools, synagogues, community centres, etc.)
- Not a preliminary category (`בקשה מקדמית`, etc.)
- Within 10-year timeframe, not yet occupied

Confirmed that these criteria were applied to **unmatched** permits but NOT to matched permits
before generating `manual_review` rows — root cause of 40 noise rows.

### 2. Applied project-criteria filters to matched `manual_review` branch

`transform/matcher.py` — before emitting a `manual_review` row for a matched permit:
1. `_is_relevant_type(request_type)` guard added
2. `_is_public_use(permit)` guard added
3. `_is_below_unit_minimum(permit)` guard added
   - Exception: if matched project's `סוג בנייה` contains `תמ"א 38`, unit minimum is waived.
     Complot classifies תמ"א 38 permits as `בניה חדשה` in `request_type`; the project-level
     type is the authoritative source.

### 3. Added temporal plausibility check

New function `_is_temporally_plausible(permit, proj, max_days_before=365)`:
- Returns False if `permit.request_date < proj.תאריך_בקשה_להיתר - 365 days`
- Permits filed AFTER the project's date are always allowed
- Returns True if either date is missing

Applied at both match paths:
- **Gush-helka**: candidates filtered to `plausible` list before `_pick_best_candidate()`;
  if empty, falls through to address match
- **Address fallback**: plausibility check inline — if it fails, no match is set

Confirmed cases:
- 20130414 (2013 permit → 2021 project, 8-year gap): **removed** ✓
- 20140330 (2014 permit → 2020 project, 6-year gap): **removed** ✓
- 20130371 (2013 permit → 2013 project): **kept** ✓
- 20150178, 20220176 (contemporaneous): **kept** ✓

### 4. Added `request_url` column to report

New optional `permit_url_base` parameter on `matcher.run()`. When provided, each row gets a
`request_url` column = `{permit_url_base}{permit_number}`.

For Kiryat Ata: `permit_url_base='https://handasa.kiryat-ata.org.il/iturbakashot/#request/'`

The earlier `complot_site_id` approach (which built the backend API URL) was replaced —
the correct URL is the city's public frontend.

### 5. Complot scraper: `הוצאת היתר בניה` removed from `EVENT_TO_STATUS`

Was in both `EVENT_TO_STATUS` (mapping to `'היתר'`) AND `_MANUAL_REVIEW_EVENTS` simultaneously.
Session U intended to remove it from `EVENT_TO_STATUS`; the removal didn't persist.
Now removed — the event lives only in `_MANUAL_REVIEW_EVENTS`.

### 6. Complot scraper: `תאריך הפקת היתר` extracted as authoritative `היתר` status source

`_parse_bakasha_file()` now extracts this header field.
`_merge_permit()` applies it as an override: if `תאריך הפקת היתר` is present and its rank
(`היתר` = 2) > current event-derived status rank, `permit_status` and `permit_status_date`
are set from this field. `טופס 4` events (rank 3) still win.

Requires re-scrape to take effect — current `kiryat_ata_fresh.csv` predates the change.

### 7. Final report stats

`outputs/kiryat_ata_report.xlsx` — 179 rows:
- `new_permit`: 0
- `status_advanced`: 7
- `untracked`: 29
- `manual_review`: 143 (was 177 before this session's fixes)

---

## What's still pending

### Immediate: Kiryat Ata re-scrape E

Two scraper changes need a fresh scrape:
1. `הוצאת היתר בניה` removed from `EVENT_TO_STATUS`
2. `תאריך הפקת היתר` field now extracted

Run:
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
$env:PYTHONUTF8 = '1'
Start-Process `
  -FilePath 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  -ArgumentList 'c:\R_PROJECTS\Project_update_scraper\scripts\run_kiryat_ata.py' `
  -WorkingDirectory 'c:\R_PROJECTS\Project_update_scraper' `
  -RedirectStandardOutput 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_kiryat_ata_E.txt' `
  -RedirectStandardError  'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_err_kiryat_ata_E.txt' `
  -NoNewWindow
```

Then run matcher:
```powershell
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' -c @"
from transform.matcher import run
run(
    projects_path='docs/Kiryat_Ata_Projects_30062026.xlsx',
    permits_path='outputs/kiryat_ata_fresh.csv',
    city_hebrew=u'קרית אתא',
    output_path='outputs/kiryat_ata_report.xlsx',
    matched_cache_path='outputs/kiryat_ata_matched_cache.json',
    permit_url_base='https://handasa.kiryat-ata.org.il/iturbakashot/#request/',
)
"@
```

### Review the 143 `manual_review` rows

Open `outputs/kiryat_ata_report.xlsx` and go through the `manual_review` section.
Each row has a `request_url` link to the Complot permit page.
Key events to look for:
- `ביטול היתר` — permit cancelled, project likely stalled
- `החלטת ועדת ערר` — appeals committee decision, outcome unknown
- `הפקת פרסום תמ"38` — תמ"א 38 publication event

### Request 20250178 (known wrong-project match)

Sub-permit for project 20250142 matched to open project 11051-3 via shared parcel.
Complot list-page date bug: shows 2024-02-07, actual 13/07/2025.
Decision pending: accept as manual-review or add a sub-permit filter.

### New cities

All test cities (Bat Yam, Holon, Kiryat Ata, Krayot) are at the report-review stage.
Ready to add new Bartech or Complot cities when decided.

---

## State of key files

| File | State |
|---|---|
| `transform/matcher.py` | Updated — temporal plausibility, `manual_review` filters, `permit_url_base` |
| `scrapers/complot/api_scraper.py` | Updated — `הוצאת היתר בניה` removed from `EVENT_TO_STATUS`, `תאריך הפקת היתר` extracted |
| `outputs/kiryat_ata_report.xlsx` | Current — 179 rows with `request_url` column |
| `outputs/kiryat_ata_fresh.csv` | Stale for new scraper fields — re-scrape needed |
| `docs/NEXT_STEPS.md` | Updated |
| `docs/BUG_REFERENCE.md` | Updated — BUG-010, BUG-011, BUG-012, BUG-013 added |
