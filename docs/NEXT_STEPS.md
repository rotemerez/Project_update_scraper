# Next Steps — Project Update Scraper

**Last Updated:** 2026-06-25  
**Current Phase:** V1 — manual-review report only (no automatic backoffice writes)  
**Scope:** Bat Yam via Complot, expanding to additional cities

---

## Done

### Session A — 2026-06-25
- Project scaffolding: all folders, `CLAUDE.md`, `requirements.txt`
- `scrapers/complot/scraper.py` — Selenium scraper with `_extract_permit_status()`
- `transform/gush_helka.py` — parse + set-intersect gush-helka pairs
- `transform/address_match.py` — street+number normalization and range matching
- `transform/matcher.py` — UC1/UC2/UC3/UC4 logic, Excel report output
- Test run (stale data): 85 flagged rows — UC1: 23, UC2: 0 (no `permit_status` in old file), UC4: 62

### Session B — 2026-06-25
- Read `נוהל הקמת פרויקטים מאי 2023.pdf` — extracted all official Madlan `סוג בניה` values
- Updated `RELEVANT_TYPE_SUBSTRINGS` in `transform/matcher.py`:
  - Added: `בינוי פינוי`, `עיבוי בינוי`, `שימור`
  - Renamed: `UC4_RELEVANT_TYPE_SUBSTRINGS` → `RELEVANT_TYPE_SUBSTRINGS`
  - Renamed: `_is_relevant_for_uc4()` → `_is_relevant_type()`
- Applied relevance filter to **all** use cases (UC1, UC2, UC4) — minor-work permits like "הוספת גלריה" no longer leak through UC1

### Session C — 2026-06-26
- Explored `C:\R_PROJECTS\local_committee_scrapers` — found working Complot (API) and Bartech (Selenium) scrapers; `bartech/permits.py` is a stub
- Fixed 9 bugs in `scrapers/complot/scraper.py` (see `SESSION_HANDOFF_2026_06_26_A.md` for full list):
  - ChromeDriver version mismatch → auto-detect Chrome version from registry
  - Download button intercepted by sticky header → JS click
  - Excel title row → `header=1`; column detected by name `מספר בקשה(רישוי זמין)`
  - **Root cause**: double `#` in detail URL — `base_url` had search hash so `#request/20250` was appended after it, giving `#search/...#request/20250`. SPA ignored everything after second `#`. Fixed with `self.origin = url.split('#')[0]`
  - Wait condition: `top-navbar-info-desc` (non-existent) → `#table-gushim-helkot`
  - Events section: h3 XPath → direct `#table-events table` CSS selector
  - Added `'הפקת תעודת גמר': 'טופס 4'` to `EVENT_TO_STATUS`
  - `_clean_number`: preserve slashes/hyphens in permit IDs
  - UTF-8 stdout for Hebrew in error messages
- Added `year_filter` parameter to `ComplotScraper` — filters by `תאריך הגשה` year
- Verified: 20/20 success, G:True T:True D:True S:status

---

## Immediate — Do First Next Session

### 1. Handle CAPTCHA / "I'm not a robot" on the permit detail page
During testing the Chrome window was blocked by an anti-bot challenge before reaching a permit
detail page. `undetected_chromedriver` normally bypasses this but it may trigger intermittently.
Options to try in order:
- Run with `headless=False` (already the case) — let the challenge solve itself on first load
- Add a longer sleep after the first `driver.get(self.base_url)` (currently 10s — try 20s)
- If it still blocks: open the Chrome window manually, solve it once, then allow the scraper to
  continue (the cookie persists for the session)
- Longer term: look at how `local_committee_scrapers/base/browser_utils.py` handles this

### 2. Test year filter and run full scrape
`YEARS = [2025, 2026]` is already set in `run_bat_yam.py`.
Run with `max_requests = 20` first to confirm year filter works (log should show
"Year filter [2025, 2026]: 520 -> N permits").
Then set `max_requests = None` for the full scrape.

### 3. Discover "היתר בתנאים" event text
After scraping 2025 permits, find one that reached `היתר בתנאים` stage, open in browser,
read the exact `תיאור אירוע` text, add to `EVENT_TO_STATUS` in the scraper.

### 4. Re-run matcher against fresh data
```python
from transform import matcher
matcher.run('docs/bat_yam.xlsx', 'outputs/bat_yam_fresh.xlsx', 'בת ים', 'outputs/bat_yam_report.xlsx')
```

---

## Soon

### 3. Investigate automating the backoffice projects export
Currently `docs/bat_yam.xlsx` is a manual export from the backoffice.  
Check if the backoffice has a download API or script-accessible endpoint — if yes, automate the pull so the report always runs against fresh project data.

### 4. Widen to a second city
Once Bat Yam is validated end-to-end, pick a second city from `complot_cities.csv` and verify the scraper + matcher generalise cleanly (new city column in matcher, separate output file).

---

## Later

### 5. Resolve `שימור` substring noise
`שימור` is broad — it could match minor facade-preservation permits.  
After seeing real Complot data, tighten to a more specific substring if noise appears.

### 6. Complot event mapping — complete the table
Once live scrapes have surfaced enough event types, finalise `EVENT_TO_STATUS` in the scraper and document the mapping in a comment block.

### 7. V2 — automatic backoffice writes
After the manual-review cycle is validated:
- Build `backoffice/client.py` (API wrapper)
- Build `transform/mapper.py` (scraped fields → backoffice payload)
- Tie into matcher output for auto-update of UC2 projects
- UC1 and UC4 still require human sign-off before creation

---

## Key File Paths

| Path | Role |
|---|---|
| `scrapers/complot/scraper.py` | Scraper — `EVENT_TO_STATUS` dict at top |
| `transform/matcher.py` | Matching + report — `RELEVANT_TYPE_SUBSTRINGS` list |
| `transform/gush_helka.py` | Gush-helka parsing and set-intersection |
| `transform/address_match.py` | Address normalization and range matching |
| `docs/bat_yam.xlsx` | Madlan projects export for Bat Yam (601 rows) |
| `outputs/bat_yam_report.xlsx` | Latest report output |
| `docs/session_handoffs/` | Per-session handoff notes |
