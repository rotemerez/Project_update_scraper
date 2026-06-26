# Session Handoff — 2026-06-26 A

## What was accomplished

### Codebase comparison — local_committee_scrapers vs permit scraper
- Explored `C:\R_PROJECTS\local_committee_scrapers` fully
- Found working Complot scrapers (HTTP/BeautifulSoup API approach — no Selenium needed) and
  Bartech scrapers (Selenium) with ~130 municipalities in `registry/dispatcher.py`
- `systems/bartech/permits.py` is a stub — Bartech permit scraper does not yet exist there
- Key finding: Codebase A uses `systems/complot/plans_api.py` for direct API calls to
  `handasi.complot.co.il/magicscripts/mgrqispi.dll` — much faster than Selenium

### Fixed all blocking bugs in `scrapers/complot/scraper.py`

**Bug 1 — ChromeDriver version mismatch**
Added auto-detection of Chrome major version from Windows registry in `_init_driver()`.
Passes `version_main=N` to `uc.Chrome()` so the matching driver is downloaded automatically.

**Bug 2 — Download button intercepted by sticky nav**
Changed `download_btn.click()` to scroll-into-view + JS click to bypass the sticky Elementor
header that was sitting on top of the button.

**Bug 3 — Excel title row / column detection**
The downloaded Excel has a "Exported data" title in row 0. Added `header=1` to skip it.
Column name is `מספר בקשה(רישוי זמין)` — added to the candidate list for name-based detection.

**Bug 4 (ROOT CAUSE) — Double hash in detail page URL**
`self.base_url` was set to the full search URL including `#search/GetBakashotByNumber&...`.
Building detail URLs as `f'{self.base_url}#request/{id}'` produced two `#` symbols:
`...iturbakashot/#search/GetBakashotByNumber&...#request/20250`
A URL can only have one `#`. The browser discarded everything after the second `#`, so the
SPA always saw the search hash and stayed on the results page — the detail page never loaded.

Fix: added `self.origin = url.split('#')[0].rstrip('/')` and use `self.origin` for detail URLs.

**Bug 5 — Wrong wait condition**
Was waiting for `top-navbar-info-desc` (a class that doesn't exist in Bat Yam's DOM).
Wait timed out immediately, and extraction ran against the half-loaded shell.
Replaced with `WebDriverWait` on `#table-gushim-helkot` — an element that only appears once
the permit detail page has rendered.

**Bug 6 — Events section selector**
`_extract_permit_status` used XPaths looking for `h3[contains(text(),'אירועים')]`.
Bat Yam uses `<div id="btn-events">` and `<div id="table-events">` — no h3 header.
Added Strategy 1: direct `#table-events table` CSS selector (fast, reliable).
Kept old h3 XPaths as Strategy 2 fallback for other Complot municipalities.

**Bug 7 — Missing EVENT_TO_STATUS entry**
Found `הפקת תעודת גמר` (completion certificate) in the events table for permit 20250.
Added: `'הפקת תעודת גמר': 'טופס 4'`

**Bug 8 — `_clean_number` destroying permit IDs**
Was stripping all non-digits and capping at 8 chars, which would destroy IDs like `2025/1234`.
Changed to just strip Hebrew label prefixes; preserve the number as-is.

**Bug 9 — Windows Hebrew encoding crash**
`print()` on Windows cp1252 terminal crashed when logging Hebrew strings from error messages.
Fixed by reconfiguring `sys.stdout` to UTF-8 at module level.

### Added year filter
Added `year_filter: List[int]` parameter to `ComplotScraper`.
After downloading the Excel, filters rows by `תאריך הגשה` year before scraping.
`run_bat_yam.py` now sets `YEARS = [2025, 2026]`.

### Verified end-to-end
20/20 permits scraped successfully: `G:True T:True D:True S:<status>`.
Permit 20250 correctly returns `permit_status=טופס 4, permit_status_date=23/02/1982`.

---

## Current state of the codebase

All bugs are fixed. The scraper works correctly on Bat Yam.
Year filter is implemented but **not yet tested** — the test run was interrupted before it ran.

---

## Immediate next steps

### 1. Test year filter and run full scrape
```
YEARS = [2025, 2026]  # already set in run_bat_yam.py
scraper.max_requests = 20  # verify count first, then set to None
```
Run `python run_bat_yam.py` to confirm how many 2025/2026 permits are in the list,
then set `max_requests = None` for the full scrape.

### 2. Discover "היתר בתנאים" event text
After scraping 2025 permits, inspect one that has reached `היתר בתנאים` stage.
Open it in Chrome, look in the events table, read the exact `תיאור אירוע` text.
Add the substring to `EVENT_TO_STATUS` in `scrapers/complot/scraper.py`.

### 3. Re-run matcher against fresh data
```python
from transform import matcher
matcher.run(
    projects_path='docs/bat_yam.xlsx',
    permits_path='outputs/bat_yam_fresh.xlsx',
    city_hebrew='בת ים',
    output_path='outputs/bat_yam_report.xlsx',
)
```

---

## Key file paths

| Path | Role |
|---|---|
| `scrapers/complot/scraper.py` | Scraper — all bugs fixed this session |
| `run_bat_yam.py` | Runner script — set `YEARS` and `max_requests` here |
| `transform/matcher.py` | Matching + report |
| `docs/bat_yam.xlsx` | Madlan projects export (601 rows) |
| `outputs/bat_yam_fresh.xlsx` | Live scrape output |
| `outputs/bat_yam_report.xlsx` | Latest matcher report |
| `outputs/debug_excel_בת ים.txt` | Excel column diagnostic |
| `outputs/debug_בת ים_permit.html` | First permit page HTML (for DOM inspection) |

## Python
`C:\Users\Rotem\AppData\Local\Programs\Python\Python314\python.exe`
Run from project root: `cd c:/R_PROJECTS/Project_update_scraper`

## Notes on local_committee_scrapers
- `C:\R_PROJECTS\local_committee_scrapers\unified_scraper\municipal_scraper\systems\bartech\`
  contains `plans.py` (full Selenium scraper) and `permits.py` (stub — not yet implemented)
- When building a Bartech permit scraper, start from `systems/bartech/plans.py` as the base
- Complot API approach (no Selenium) lives in `systems/complot/plans_api.py` — worth porting
  to this project for speed if Selenium proves too slow at scale
