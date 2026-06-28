# Next Steps — Project Update Scraper

**Last Updated:** 2026-06-28  
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
  - `status_advanced` no longer blocked by empty `request_type`
  - Partial NaN coercion fix (BUG-001, not yet fully resolved)
- **Matcher returned 0 rows** — root cause confirmed next session

### Session F — 2026-06-27 (handoff B)
- **Fixed BUG-001**: `float('nan') or ''` returns NaN not `''` — added `_clean()` helper,
  replaced all NaN-unsafe coercions in `matcher.py` (see `docs/BUG_REFERENCE.md`)
- Matcher now produces **414 `new_permit` rows** (was 0)
- Renamed match flags: `UC1→new_permit`, `UC2→status_advanced`, `UC3→unchanged`, `UC4→untracked`
  — output column is now `flag` instead of `use_case`
- Diagnosed why 98% of permits have no `permit_status`: `GetTikFile` only covers active/recent
  permits; most older ones have no event in `ארוע אחרון להצגה`, and many event types were unmapped
- Expanded `EVENT_TO_STATUS` with 3 new mappings found in scrape log:
  - `מסירת תעודת גמר` → `טופס 4`
  - `מסירת היתר(בסמכות מהנדס)` → `היתר`
  - `החלטה לאשר בתנאי/ם` → `היתר בתנאים`
- Cleaned root folder: moved `run_bat_yam.py` → `scripts/`, `debug_download_*.png` → `outputs/`
- Added file placement rules to `CLAUDE.md`
- **Re-scrape triggered** with updated event mapping — running in background (~47 min)

### Session I — 2026-06-28 (handoff C)
- **Built Bartech scraper**: `scrapers/bartech/api_scraper.py` + `scripts/run_holon.py`
  - Smoke-tested against Holon; fixed two bugs found during test (see BUG-004, BUG-005)
  - Full Holon scrape running (~15:40 expected completion)
- **Fixed matcher year filter (BUG-006)**: was filtering by `request_date` (DB record creation date,
  not a real milestone); now filters by `permit_status_date`. Empty status date passes through.
- **Added `first_event_date` capture** to Complot scraper + second filter pass in matcher.
  Catches old permits whose first event predates the cutoff even if recent activity exists.
  Requires re-scrape to take effect.
- **Fixed permit number concatenation bug (BUG-007)**: `get_text(strip=True)` on the list-page
  cell concatenated the request number and rishuy zamin number → changed to
  `next(cells[0].stripped_strings, '')` to take only the first text node.
- **Bat Yam re-scrape running** (~15:04 start) — picks up BUG-007 fix + `first_event_date`
- **Bat Yam matcher run** (prior scrape): 623 rows — `new_permit`: 222, `status_advanced`: 79,
  `untracked`: 322
- **Updated CLAUDE.md**: documented the only working method for background scrapes (`Start-Process`
  with `-WorkingDirectory` + absolute paths) plus 4 methods that do NOT work
- **Holon backoffice export available**: `docs/holon_28062026.xlsx` (500 projects)

### Session H — 2026-06-28 (handoff B)
- **Bartech architecture fully discovered** — no Selenium needed, plain HTTP works
  - reCAPTCHA not validated server-side — any token value passes
  - Endpoint: `GET /SearchPermitApplicationResults/?searchType=ByDetails&TypeOfPermit=X&g-recaptcha-response=x&page=N`
  - `TypeOfPermit` filter works; `ApplicationDescription` free-text search is broken (do not use)
  - 6 types to scrape (exclude 55=info, 63=apartment map); type 51 dominates (5089 pages for Holon)
  - HTML structure: Label10=status, Label11=address, Label12=gush/helka (ToolTip), Label13=applicant, Label14=description
  - Entity_Number from detail link href; date from `span.phone` with "תאריך פתיחה"
  - Status vocab: `מאושר` → `היתר`, `פעיל`/admin statuses → `בקשה להיתר`, `לא פעיל` → ''
- **Bat Yam re-scrape started** — running in background (~52% at session end, log: `outputs/scrape_log_2026_06_28.txt`)
- **Created** `scrapers/bartech/__init__.py`
- **Full scraper spec** written in `SESSION_HANDOFF_2026_06_28_B.md` — ready to implement

### Session G — 2026-06-28 (handoff C)
- **Removed fabricated data**: stripped `or 'בקשה להיתר'` fallback from `matcher.py` — blank
  `scraped_status` is now honest; all 414 rows had been falsely showing `בקשה להיתר`
- **Discovered `GetBakashaFile` is accessible** — the permit detail page returns:
  - `תיאור הבקשה` (request description / construction type)
  - `סוג הבקשה` (permit category, e.g. `בקשה מקדמית`)
  - Per-permit events table with accurate status and date
- **Rewrote scraper** (`scrapers/complot/api_scraper.py`): replaced `GetTikFile` (per-building)
  with `GetBakashaFile` (per-permit) — runtime ~80 min, but data is accurate
- **Added `request_category` exclusion filter** to `matcher.py`:
  excludes `בקשה מקדמית`, `בקשה עקרונית`, `בקשה למידע`, `בקשה לתיאום מקדים`, `תהליך ראשוני`
  (source: נוהל הקמת פרויקטים מאי 2023)
- **Added `min_year` auto-computation**: derived from earliest `תאריך בקשה להיתר` among
  in-progress projects (without טופס 4); for Bat Yam = 2011
- **Added report columns**: `project_sug_bnia`, `type_confirmed`, `request_category`
- **Added `חיזוק ותוספת` and `צמודי קרקע`** to `RELEVANT_TYPE_SUBSTRINGS`
- **Updated CLAUDE.md**: data integrity rule, excluded categories, trackable types, timeframe rule
- Re-scrape required — GetBakashaFile data not yet scraped for 9,639 permits

---

## Immediate — Do First Next Session

### 1. Bat Yam re-scrape completing
Re-scrape started ~15:04 (log: `outputs/scrape_log_2026_06_28_C.txt`). Once done, run matcher:
```python
from transform import matcher
matcher.run('docs/bat_yam.xlsx', 'outputs/bat_yam_fresh.xlsx', 'בת ים', 'outputs/bat_yam_report.xlsx')
```

### 2. Holon scrape + matcher
Holon scrape started ~12:55 (log: `outputs/holon_scrape_log_2026_06_28.txt`).
Expected completion ~15:40. Once done:
```python
from transform import matcher
matcher.run(
    'docs/holon_28062026.xlsx',
    'outputs/holon_fresh.xlsx',
    'חולון',
    'outputs/holon_report.xlsx',
    excluded_categories=set(),   # Bartech excludes bad types at scrape time
)
```

### 3. Classify `שובץ לישיבת ועדה` Bartech status
This status ("scheduled for committee meeting") appeared during the Holon scrape but was not
mapped — user asked not to assume. Review against the backoffice norms and add to
`STATUS_MAP` in `scrapers/bartech/api_scraper.py` once confirmed.

### 4. Review Bat Yam + Holon reports
- `type_confirmed=True` rows: request_type values sensible?
- `status_advanced` rows: correct upgrades?
- Any new unmapped statuses in logs?

---

## Soon

### 3. Investigate automating the backoffice projects export
Currently `docs/bat_yam.xlsx` is a manual export from the backoffice.  
Check if the backoffice has a download API or script-accessible endpoint — if yes, automate
the pull so the report always runs against fresh project data.

### 4. Widen to a second city
Once Bat Yam is validated end-to-end, pick a second city from `complot_cities.csv` and verify
the scraper + matcher generalise cleanly (new city column in matcher, separate output file).

### 5. Build Bartech scraper
Base it on the working Bartech scraper at `C:\R_PROJECTS\local_committee_scrapers` (not on
`repo/municipal-permit-scraper-main/src/scrapers/bartech_scraper.py` which is a generic
Playwright template that has never been tested against a real site).

---

## Later

### 6. Resolve `שימור` substring noise
`שימור` is broad — it could match minor facade-preservation permits.  
After seeing real Complot data, tighten to a more specific substring if noise appears.

### 7. Complot event mapping — finalise
All distinct events from the 2011–2026 scrape have been catalogued (see session F handoff).
Three new ones were added. Remaining unmapped events are intentionally left blank (admin/processing).
No further action needed unless new event types surface in future scrapes.

### 8. V2 — automatic backoffice writes
After the manual-review cycle is validated:
- Build `backoffice/client.py` (API wrapper)
- Build `transform/mapper.py` (scraped fields → backoffice payload)
- Tie into matcher output for auto-update of `status_advanced` projects
- `new_permit` and `untracked` still require human sign-off before creation

---

## Key File Paths

| Path | Role |
|---|---|
| `scrapers/complot/scraper.py` | Old Selenium scraper — superseded by API approach |
| `scrapers/complot/api_scraper.py` | Complot API scraper — working |
| `scrapers/bartech/api_scraper.py` | Bartech API scraper — working, smoke-tested |
| `scripts/run_bat_yam.py` | Runner — uses `ComplotPermitsAPI`, `max_requests=None` |
| `scripts/run_holon.py` | Runner — Holon (Bartech), scrape in progress |
| `transform/matcher.py` | Matching + report — `RELEVANT_TYPE_SUBSTRINGS` list |
| `transform/gush_helka.py` | Gush-helka parsing and set-intersection |
| `transform/address_match.py` | Address normalization and range matching |
| `docs/bat_yam.xlsx` | Madlan projects export for Bat Yam (601 rows) |
| `outputs/bat_yam_report.xlsx` | Latest report output |
| `docs/session_handoffs/` | Per-session handoff notes |
