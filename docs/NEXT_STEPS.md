# Next Steps — Project Update Scraper

**Last Updated:** 2026-06-27  
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

### Session C — 2026-06-26 (handoff A)
- Explored `C:\R_PROJECTS\local_committee_scrapers` — found working Complot (API) and Bartech (Selenium) scrapers; `bartech/permits.py` is a stub
- Fixed 9 bugs in `scrapers/complot/scraper.py` (see `SESSION_HANDOFF_2026_06_26_A.md` for full list)
- Added `year_filter` parameter to `ComplotScraper` — filters by `תאריך הגשה` year
- Verified: 20/20 success, G:True T:True D:True S:status

### Session D — 2026-06-26 (handoff B)
- Ported anti-detection from `browser_utils.py` into `scraper.py`: viewport randomization, Hebrew language
  prefs, page load timeout, `_handle_privacy_dialog()` method, initial sleep 20s, browser restart warm-up
- **Discovered CAPTCHA is persistent and reappears after manual solve** — Selenium scraper not viable
- **Investigated `handasi.complot.co.il` backend** (no Cloudflare) — found complete API architecture:
  - `GetBakashotByNumber` → full permit list, 521 rows, no auth (one HTTP call)
  - `GetBakashaFile` → permit detail, **blocked** for all permits (authentication required)
  - `GetTikFile` → building file, full data, no auth — `table-requests` has `ארוע אחרון להצגה`
    which is exactly the `permit_status` field we need
- Confirmed field mapping from column headers (see `SESSION_HANDOFF_2026_06_26_B.md`)
- Found via `_routes.min.js` at `handasi.complot.co.il/handasi2016/Scripts/Complot/request/min/`

### Session E — 2026-06-27 (handoff A)
- Built `scrapers/complot/api_scraper.py` — complete API scraper, no Selenium
  - `ComplotPermitsAPI` with `GetBakashotByNumber` + `GetTikFile` per building
  - Table finder uses header text search (not id — `table-requests` id absent in real HTML)
  - `EVENT_TO_STATUS` expanded: `היתר היסטורי` → `היתר`, `בקשה ללא היתר` → `בקשה להיתר`, `הפקת היתר בניה לחתימות` → `היתר`
  - `permit 20250` → `טופס 4` confirmed ✓
- Discovered `b=` is substring match on permit number, not year filter
  - Expanded to `b_params=range(2011, 2027)` — cycles 16 year-series, deduplicates by permit_num
- **Full scrape completed**: 9,639 unique permits (2011–2026), saved to `outputs/bat_yam_fresh.xlsx`
- Fixed `transform/matcher.py`:
  - UC2 no longer blocked by empty `request_type` (project already exists in Madlan → relevant by definition)
  - `NaN` coercion for `request_type` from Excel
- **Matcher returns 0 rows** — gush-helka intersection appears to be empty; root cause not yet confirmed

---

## Immediate — Do First Next Session

### 1. Debug matcher — find why 0 matches

Run the diagnostic in `SESSION_HANDOFF_2026_06_27_A.md` to confirm:
- How many projects have `גוש-חלקה` filled?
- How many permits have `block_lot` non-empty?
- What is the actual intersection size?

Then fix whichever side is wrong (format mismatch, empty data, etc.) and re-run:
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
| `scrapers/complot/scraper.py` | Old Selenium scraper — superseded by API approach |
| `scrapers/complot/api_scraper.py` | **To be created** — API-based, no Selenium |
| `transform/matcher.py` | Matching + report — `RELEVANT_TYPE_SUBSTRINGS` list |
| `transform/gush_helka.py` | Gush-helka parsing and set-intersection |
| `transform/address_match.py` | Address normalization and range matching |
| `docs/bat_yam.xlsx` | Madlan projects export for Bat Yam (601 rows) |
| `outputs/bat_yam_report.xlsx` | Latest report output |
| `docs/session_handoffs/` | Per-session handoff notes |
