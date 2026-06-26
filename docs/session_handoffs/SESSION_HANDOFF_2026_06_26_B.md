# Session Handoff — 2026-06-26 B

## What was accomplished

### Anti-detection improvements to `scrapers/complot/scraper.py`
Ported logic from `local_committee_scrapers/base/browser_utils.py`:
- **Viewport randomization** — `_init_driver()` now picks randomly from 6 common resolutions each run
- **Hebrew language prefs** — `intl.accept_languages: he-IL,he,en-US,en` via `ChromeOptions.add_experimental_option`
- **Page load timeout** — `set_page_load_timeout(30)` prevents hanging on blocked pages
- **`_handle_privacy_dialog()`** — new method: Strategy 1 = `cap-banner` / `button.cap-popup-accept`;
  Strategy 2 = `אשר וסגור` XPath variations. Called after initial page load and after each browser restart.
- **Initial sleep 10s → 20s** and **browser restart now warms up via `base_url`** before hitting detail pages

### Discovery: Selenium is not viable, API approach confirmed

During testing, the CAPTCHA appeared repeatedly and reappeared even after manual solving.
This triggered an investigation into the `handasi.complot.co.il` backend API.

**Key finding** (from `plans_api.py` and `_routes.min.js`):
> The `handasi.complot.co.il` backend has **no Cloudflare protection**. The CAPTCHA only lives on
> the `batyam.complot.co.il` frontend. Direct HTTP requests to the backend work without a browser.

### API endpoint discovery (all via direct HTTP, no browser)

| Endpoint | `prgname` | Params | Status |
|---|---|---|---|
| Permit list | `GetBakashotByNumber` | `siteid, grp, t, b, l, arguments` | **Works — 521 rows** |
| Permit detail | `GetBakashaFile` | `siteid, b` | **Blocked for all permits** |
| Building file | `GetTikFile` | `siteid, t` | **Works — full data** |

**How we found this:** Read `_routes.min.js` from `handasi.complot.co.il/handasi2016/Scripts/Complot/request/min/` 
— the Backbone.js router file that maps URL hashes to backend API calls.

### Complete field mapping confirmed

**List table** (`GetBakashotByNumber`) columns:
- `מספר בקשה(רישוי זמין)` — permit display number (e.g. `20250`)
- `תיק בניין` — internal building ID (e.g. `943`) — key for `GetTikFile`
- `תאריך הגשה` — submission date
- `שם המבקש` — requestor name
- `כתובת` — address
- `גוש` — block
- `חלקה` — parcel

**Building file** (`GetTikFile`) `table-requests` columns:
- `מספר בקשה` — permit number
- `תאריך הגשה` — submission date
- **`ארוע אחרון להצגה`** — latest event (= `permit_status` — maps directly to `EVENT_TO_STATUS`)
- `שם המבקש` — requestor
- `היתר` — permit number if issued (e.g. `20090317`)
- `תאריך היתר` — permit issue date (useful!)

### Permit status values seen in the wild (from `ארוע אחרון להצגה`):
- `הפקת תעודת גמר` → `טופס 4` (already in EVENT_TO_STATUS)
- `פתיחת בקשה להיתר` → `בקשה להיתר` (already in EVENT_TO_STATUS)
- `הפקת היתר בניה לחתימות` → probably maps to `היתר`
- `בקשה ללא היתר` — not in EVENT_TO_STATUS yet
- `היתר היסטורי` — not in EVENT_TO_STATUS yet
- `פתיחת בקשה היסטורית` — not in EVENT_TO_STATUS yet
- `סיום טיפול בבקשה להיתר ללא הוצאת היתר` — rejected/closed
- `העברת תיק המידע למערכת רישוי זמין` — migration artifact, not a real status

---

## Current state of the codebase

- `scrapers/complot/scraper.py` — anti-detection improvements committed, but **the Selenium scraper 
  is now known to be unviable** due to persistent CAPTCHA on permit detail pages
- **No API scraper exists yet** — needs to be built in the next session

---

## Immediate next steps

### 1. Build `scrapers/complot/api_scraper.py`

The complete no-Selenium scraper. Architecture:

```
Step 1: GET GetBakashotByNumber → full permit list (one call, ~520 rows)
         Filter by year_filter if set

Step 2: Collect unique building_ids from the list
         For each unique building_id: GET GetTikFile
         Extract table-requests → build dict: permit_num → (latest_event, date)

Step 3: Merge list + building data → emit permit records
```

Key implementation notes:
- `API_BASE = "https://handasi.complot.co.il/magicscripts/mgrqispi.dll"`
- Bat Yam `site_id = 81`
- List params: `appname=cixpa, prgname=GetBakashotByNumber, siteid=81, grp=0, t=0, b=2025, l=false, arguments=siteId,grp,t,b,l`
- Building params: `appname=cixpa, prgname=GetTikFile, siteid=81, t=<building_id>, arguments=siteid,t`
- `EVENT_TO_STATUS` logic same as in `scraper.py` — apply to `ארוע אחרון להצגה`
- Rate-limit to ~1 req/sec to be polite
- Output schema: same as Selenium scraper so matcher works unchanged

### 2. Update `run_bat_yam.py` to use `ComplotPermitsAPI`

Replace `ComplotScraper` import with `ComplotPermitsAPI`.
No Selenium dependency needed for the runner.

### 3. Run and validate

Spot-check that permit 20250 comes out with `permit_status=טופס 4` (from `הפקת תעודת גמר`).
Compare row count against expected ~520 total / ~N after year filter.

### 4. Expand `EVENT_TO_STATUS` in `api_scraper.py`

After seeing the full data, add:
- `הפקת היתר בניה לחתימות` → `היתר`
- Review whether `בקשה ללא היתר`, `היתר היסטורי` etc. need mapping

### 5. Re-run matcher against fresh data

```python
from transform import matcher
matcher.run('docs/bat_yam.xlsx', 'outputs/bat_yam_fresh.xlsx', 'בת ים', 'outputs/bat_yam_report.xlsx')
```

---

## Key file paths

| Path | Role |
|---|---|
| `scrapers/complot/scraper.py` | Old Selenium scraper — anti-detection improved, now superseded |
| `scrapers/complot/api_scraper.py` | **To be created** — API-based, no Selenium |
| `run_bat_yam.py` | Runner — update to import `ComplotPermitsAPI` |
| `transform/matcher.py` | Matching + report |
| `docs/bat_yam.xlsx` | Madlan projects export (601 rows) |
| `outputs/bat_yam_fresh.xlsx` | Live scrape output |

## Python
`C:\Users\Rotem\AppData\Local\Programs\Python\Python314\python.exe`
Run from project root: `cd c:/R_PROJECTS/Project_update_scraper`
