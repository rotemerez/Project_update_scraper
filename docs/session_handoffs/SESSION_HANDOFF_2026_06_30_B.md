# Session Handoff — 2026-06-30 B

**Date:** 2026-06-30
**Session:** L
**Scope:** Ramat Gan second Complot city; Bartech scraper rebuilt with detail-page stage parsing

---

## What was accomplished

### 1. Ramat Gan — second Complot city

- `site_id=3`, `city_name_hebrew='רמת גן'`
- Site ID source: `C:\R_PROJECTS\local_committee_scrapers\unified_scraper\municipal_scraper\registry\dispatcher.py`
  — this file has site_ids for all ~130 Complot municipalities. Saved as a Claude memory reference.
- Created `scripts/run_ramat_gan.py` (copy of `run_bat_yam.py` with updated site_id + city name)
- Full scrape ran: **4,916 unique permits** (2011–2026), saved to `outputs/ramat_gan_fresh.csv`
- Backoffice export ready at `docs/Ramat_Gan_Projects_30062026.xlsx`
- **Matcher not yet run** — this is the first task next session

### 2. Bartech scraper rebuilt — two-phase, same design as Complot

**Problem:** `holon_report.xlsx` had 1,675 `status_advanced` rows (should be far fewer).
Root cause: Bartech scraper never populated `permit_status_date`, so `_scraped_date_is_actionable`
always returned True (no comparison possible), and multi-permit projects generated a row per permit.

**Solution:** Add a detail-page fetch phase, identical in design to Complot's `GetBakashaFile` phase.

**Detail page URL:** `{base_url}/PermitApplicationDetails?Definement_Entity_Type={type_id}&Entity_Type=P&Entity_Number={entity_num}`

**Page structure (confirmed from Holon):**
- Table 0: `<dt>/<dd>` cells — permit metadata (סטטוס בקשה, תאריך הגשה, מספר תיק בניין)
- Table 1: `<dt>/<dd>` cells — תאור הבקשה, מהות הבקשה (span+text pattern for the latter)
- Table 2: gush/helka table (header row uses `<td><span>`, not `<th>`)
- Table 3: address detail
- Table 4: stakeholders (סוג/שם — מבקש, בעל הנכס, עורך, etc.)
- Tables 5+: one per stage track — each has headers `[סטטוס שלב, תאור שלב, תאריך]`
  - `שלבי הבקשה: מסלול רישוי בניה` — main licensing workflow (30-60+ stages for mature permits)
  - `שלבי הבקשה: שלבי בניה` — construction stages (appears after permit issued)
  - Other tracks may exist per city

**`STAGE_TO_STATUS` map (priority-ranked, same logic as `EVENT_TO_STATUS` in Complot):**
```python
'גמר בניה'               → 'טופס 4'
'מסירת היתר'             → 'היתר'
'הפקת היתר'              → 'היתר'
'הוצא היתר'              → 'היתר'
'סגירת בקשה להיתר שנמסר' → 'היתר'
'החלטה לאשר הבקשה'       → 'היתר בתנאים'
'ישיבת רשות רישוי'       → 'בקשה להיתר'
'שיבוץ לועדה'            → 'בקשה להיתר'
'פתיחת בקשה'             → 'בקשה להיתר'
```
All stage tables are scanned; `STATUS_ORDER` ranking picks the highest-significance status.

**Additional fields now extracted from detail page:**
- `request_type` (תאור הבקשה) — overrides list-page `Label14` value
- `bakasha_description` (מהות הבקשה) — new field, used as relevance signal in matcher
- `block_lot` — gush/helka from detail page overrides list-page tooltip value

**`min_year` parameter added:**
- Holon Bartech data goes back to **1944** (26,869 total permits, ~18,130 pre-2011)
- `min_year=2011` skips detail fetches for pre-2011 permits (still in output, matcher drops them)
- Reduces detail fetches: 26,869 → **~8,739** — saves ~60 min
- Set in `run_holon.py`: `min_year=2011`

---

## What to do next session

### 1. Run Ramat Gan matcher (immediate)

```python
from transform.matcher import run as matcher_run

matcher_run(
    'docs/Ramat_Gan_Projects_30062026.xlsx',
    'outputs/ramat_gan_fresh.csv',
    'רמת גן',
    'outputs/ramat_gan_report.xlsx',
    matched_cache_path='outputs/ramat_gan_matched_cache.json',
)
```

Watch for:
- New unmapped events (log as `[NEW EVENT] Unmapped: [...]`)
- Address matching issues specific to Ramat Gan street names
- Permit number format — regex `r'(20\d{6})'` should be fine but verify

### 2. Run Holon re-scrape

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
Start-Process -FilePath 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  -ArgumentList '-u', 'c:\R_PROJECTS\Project_update_scraper\scripts\run_holon.py' `
  -WorkingDirectory 'c:\R_PROJECTS\Project_update_scraper' `
  -RedirectStandardOutput 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_holon_B.txt' `
  -RedirectStandardError  'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_err_holon_B.txt' `
  -NoNewWindow
```

Expected time: list phase ~30 min (26,869 rows across 6 permit types) + detail phase ~29 min
(8,739 permits × 0.2s) = ~60 min total.

After scrape, run matcher and verify `status_advanced` count has dropped from 1,675.
Watch for `[NEW STAGE] Unmapped: [...]` log lines — add them to `_UNMAPPED_STAGES` in the scraper.

### 3. If Ramat Gan report looks clean

Consider running a third Complot city. Look up site_id in `dispatcher.py`.
Cities in Tel Aviv district with Complot: Or Yehuda (73), Ramat Hasharon (118) — check dispatcher
for others.

---

## State of key files

| File | State |
|---|---|
| `scrapers/bartech/api_scraper.py` | Rebuilt — two-phase, STAGE_TO_STATUS, min_year param |
| `scripts/run_ramat_gan.py` | New — site_id=3 |
| `scripts/run_holon.py` | Updated — min_year=2011, bakasha_description in output cols |
| `outputs/ramat_gan_fresh.csv` | Current — 4,916 permits (2026-06-30) |
| `outputs/holon_fresh.csv` | Stale — pre-detail-page fix; re-scrape needed |
| `docs/Ramat_Gan_Projects_30062026.xlsx` | Ready — backoffice export for Ramat Gan |
| `outputs/bat_yam_fresh.csv` | Current — 9,639 permits (scrape D, 2026-06-28) |
| `outputs/bat_yam_report.xlsx` | Current — 5 rows (clean) |
