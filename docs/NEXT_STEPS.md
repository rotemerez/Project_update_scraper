# Next Steps — Project Update Scraper

**Last Updated:** 2026-07-05 (Session S)
**Current Phase:** V1 — manual-review report only (no automatic backoffice writes)  
**Scope:** Bat Yam via Complot; Holon + Kiryat Ata + Krayot via Bartech/Complot (Ramat Gan shelved)

---

## Done

### Session S — 2026-07-05
- **Bartech: applied 3 final reviewer annotation decisions**:
  - `גמר בניה` in `STATUS_MAP`: `טופס 4` → `היתר` (construction complete, no Form 4 yet)
  - `הפקת היתר` / `הוצא היתר` / `הוצאת היתר בניה` removed from `STAGE_TO_STATUS` → `_UNMAPPED_STAGES`
    (permit may not be signed yet; reviewer: "doesn't fall under advancement statuses")
  - `החלטה לדחות` — already correct (`בקשה להיתר`), no change
- **Bartech: Krayot log triage** — 18 new `STAGE_TO_STATUS` entries added (construction progress
  stages, Form-4-track variants, committee steps); 24 new `_UNMAPPED_STAGES` entries (warranty
  release, field inspections, legal/enforcement, suspension, admin docs)
- **Krayot matcher**: 38 rows — 1 `new_permit`, 35 `status_advanced`, 2 `untracked`
  (cache: `outputs/krayot_matched_cache.json`, 1683 permits)
- **Kiryat Ata re-scrape**: complete — 3,318 permits with updated scraper code
  (`outputs/kiryat_ata_fresh.csv` via `scrape_log_kiryat_ata_B.txt`)
- **Kiryat Ata matcher**: 64 rows — 0 `new_permit`, 23 `status_advanced`, 41 `untracked`
  (was 14/41 before re-scrape; +9 `status_advanced` from fixed `היתר` detection)
  (cache: `outputs/kiryat_ata_matched_cache.json`, 692 permits)
- **Ramat Gan shelved** — no longer in scope; Krayot + Kiryat Ata are the Bartech/Complot test cases

### Session R — 2026-07-02 (handoff E)
- **Applied all reviewer annotations** from screenshots to both scrapers:
  - `scrapers/complot/api_scraper.py` — `EVENT_TO_STATUS` expanded from 11 → 29 entries;
    `_UNMAPPED_EVENTS` restructured: 9 entries moved to `EVENT_TO_STATUS`, 7 new entries added
    (`בקשה ללא היתר`, `היתר היסטורי`, `ישיבת מליאה`, `גמר פרסום`, `הוגשה תכנית מתוקנת`,
    `הפקת אגרות והיטלים`, `שיבוץ בקשה לדיון / למאגר`)
  - `scrapers/bartech/api_scraper.py` — `STATUS_MAP` expanded to 40 entries (incl. construction
    stages, טופס 4 variants, committee steps); `_KNOWN_CLOSED` shrunk (removed `החלטה לדחות`,
    now maps to `בקשה להיתר`); `STAGE_TO_STATUS` expanded to 21 entries (גמר בניה demoted from
    `טופס 4` → `היתר`; הפקת/הוצא/הוצאת היתר demoted from `היתר` → `היתר בתנאים`; 7 entries
    moved from `_UNMAPPED_STAGES`); 7 new `_UNMAPPED_STAGES` entries added
- **Annotation artifact export fixed**: `execCommand` + modal fallback deployed to same URL
  — reviewer's localStorage preserved; 3 pending decisions still awaited

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

### Session Q — 2026-07-02 (handoff D)
- **Holon re-matcher result confirmed**: same 197 rows (194 `status_advanced`, 3 `untracked`) as the
  pre-fix run — the `הסתיים` guard did not affect Holon because none of those 194 projects had that status.
- **Interactive annotation artifact built**:
  - URL: https://claude.ai/code/artifact/b8043df2-083a-46cd-9ca0-05776418ed69
  - All status strings for Complot, Bartech list, Bartech detail — one dropdown per string
  - All dropdowns start blank (`— בחר —`); reviewer selects the correct milestone
  - localStorage persistence, "Show unset only" filter, Export JSON button
  - Sent to the person who does this manually for annotation
- **`דיון בועדת ערר`** identified as a companion unmapped Complot event (Kiryat Ata log).
  Not yet added to the artifact — needs to be added next session.
- **Example permit for ועדת ערר events**: `20110030` in Kiryat Ata (Complot site_id=32).
  The actual Complot detail page should be reviewed to understand whether the appeal outcome
  indicates an actionable milestone before classifying.
- **Krayot scrape**: was at 6000/9037 at last check (~66%). Status unknown at session end.

### Session P — 2026-07-02 (handoff C)
- **Holon matcher (first run)**: 197 rows — 0 `new_permit`, 194 `status_advanced`, 3 `untracked`.
  Cache: `outputs/holon_matched_cache.json` (2,487 permits).
  Note: first run was pre-fix; second run (with הסתיים fix) still running.
- **Matcher fix — `הסתיים` projects** (`transform/matcher.py`):
  Projects with `סטטוס פרויקט = הסתיים` now skip all minor-alteration permits;
  genuine new construction (relevant type + recent) surfaces as `untracked` for a new BO entry.
  Root cause: `הסתיים` was not in `DB_STATUS_NORM`, so `_is_upgrade('', X)` was always True.
- **Bartech STATUS_MAP**: added `ישיבה` → `בקשה להיתר` and `בדיקה גליון דרישות` → `בקשה להיתר`
  (both appeared as `[NEW STATUS]` in Krayot list-page log).
- **Bartech STAGE_TO_STATUS**: added `'טופס 4'` → `'טופס 4'` (seen as `[NEW STAGE]` in Krayot detail phase).
- **Bartech `_UNMAPPED_STAGES`**: added `ישיבת ועדת משנה לתכנון` (Krayot detail phase).
- **Krayot scrape**: entered detail phase ~14:00 2026-07-02. Still running.
- **Status reference artifact** compiled: all status/event strings per scraper with current
  mapping. Awaiting user annotation (ignore/flag decisions) for NEW Krayot and Ramat Gan entries.

### Session O — 2026-07-02 (handoff B)
- **Kiryat Ata scrape complete**: `outputs/kiryat_ata_fresh.csv`, 3,318 permits.
  Note: scrape started before `הוצאת היתר בניה` → `היתר` fix was applied; some `היתר`
  statuses are missing from the output (running process used old in-memory code).
- **Kiryat Ata matcher**: 55 rows — 14 `status_advanced`, 41 `untracked`, 0 `new_permit`.
  Cache: `outputs/kiryat_ata_matched_cache.json` (704 permits).
- **41 new Complot `_UNMAPPED_EVENTS`** added from Kiryat Ata log (admin/routing events).
- **Krayot scrape started**: `scripts/run_krayot.py`, `base_url=https://www.vkrayot.co.il`,
  `min_year=2009` (auto-computed from `docs/krayot_projects_30062026.xlsx`).
  Estimated completion: 4-6 hours. Type 51: 4,944 pages.
- **Bartech scraper improved**:
  - `min_year` now filters at LIST phase (not just detail phase) — old permits skipped entirely
  - `min_year` auto-computed from projects file in runner scripts (never hardcoded)
  - New STATUS_MAP entries: `היתר`, `היתר/תחילת עבודות`, `היתר/טופס 4`, `הגשה`,
    `עמידה בתנאים מוקדמים`, `אי עמידה בתנאים מוקדמים`, `קבלת תוכנית מתוקנת`,
    `תשלום פקדון`, `הפקת אגרה`, `החלטה לאשר`, `אי עמידה בתנאים מוקדמים לצורך פרסום`
  - New STAGE_TO_STATUS entries: `הוצאת היתר בניה` → `היתר`, `הפקת אישור לתחילת עבודות` → `היתר`,
    `החלטה לאשר` → `היתר בתנאים` (shortens existing key to catch both forms)
  - `_KNOWN_CLOSED`: added `החלטה לדחות`
  - 20 new Krayot-specific `_UNMAPPED_STAGES` added (Rishuy Zamin + committee workflow)
  - `run_holon.py` updated to auto-compute min_year
- **`scripts/run_krayot.py`** created.

### Session N — 2026-07-02 (handoff A)
- **Complot IP block** (triggered by Ramat Gan scrape) confirmed and resolved from office IP.
  Ramat Gan restriction was the block, not city policy — re-scrape needed from office.
- **Kiryat Ata scrape** started: `scripts/run_kiryat_ata.py`, site_id=32, 3,318 permits,
  detail phase running (expected completion ~08:00 2026-07-02).
- **Holon re-scrape complete**: `outputs/holon_fresh.csv`, 21,039 rows.
- **EVENT_TO_STATUS** updated: `הוצאת היתר בניה` → `היתר`.
- **14 new `_UNMAPPED_EVENTS`** added (Kiryat Ata admin events + `החלטת ועדת ערר`).
- **Bartech `_UNMAPPED_STAGES`** updated: `אישור לת. גמר, פיקוח בניה` added.

### Session M — 2026-06-30 (handoff C)
- **Complot IP block diagnosed**: the Ramat Gan scrape (4,916 GetBakashaFile calls) triggered
  an IP-level block on handasi.complot.co.il that affects ALL Complot cities globally —
  including the web frontend. Ramat Gan's "restriction" was the block, not a city policy.
  All Complot cities need to be run/tested from the office IP.
- **Ramat Gan scrape is stale**: `outputs/ramat_gan_fresh.csv` was scraped while blocked —
  detail fields empty. Re-scrape from office IP needed before running the matcher.
- **Kiryat Ata** (Complot, site_id=32) selected as next city: `scripts/run_kiryat_ata.py` created.
  Projects file: `docs/Kiryat_Ata_Projects_30062026.xlsx`.
- **Holon re-scrape** started 2026-06-30 ~17:00 (running); new unmapped Bartech stage
  `אישור לת. גמר, פיקוח בניה` added to `_UNMAPPED_STAGES`.

### Session L — 2026-06-30 (handoff B)
- **Ramat Gan scraper**: `scripts/run_ramat_gan.py` created (`site_id=3`, city_name_hebrew=`רמת גן`)
  — full scrape ran, 4,916 unique permits. Complot site_ids documented in Claude memory
  (`local_committee_scrapers/registry/dispatcher.py` is the canonical source).
- **Bartech scraper rebuilt** — two-phase, same design as Complot:
  - Phase 2: `PermitApplicationDetails` fetched per permit; ALL stages tables parsed
    (`שלבי הבקשה: מסלול רישוי בניה` + `שלבי בניה` + any other tracks)
  - `STAGE_TO_STATUS` priority ranking (mirrors Complot `EVENT_TO_STATUS`) — highest-ranked
    status across all stages wins, not just the most recent row
  - Detail page also yields `request_type` (תאור הבקשה), `bakasha_description` (מהות הבקשה),
    and accurate `block_lot` (gush/helka from detail overrides list-page value)
  - `permit_status_date` now populated → `_scraped_date_is_actionable` will fire for Holon
  - Added `min_year` parameter: skips detail fetch for pre-`min_year` permits (keeps them in
    output for the matcher's own filter). Holon data goes back to 1944 — `min_year=2011`
    reduces detail fetches from 26,869 → ~8,739 (saves ~60 min).
- **`run_holon.py`** updated with `min_year=2011` and `bakasha_description` in output cols.

### Session K — 2026-06-30 (handoff A)
- **`_scraped_date_is_actionable()`** added to matcher: `status_advanced` now requires scraped
  date to be strictly newer than the project's latest existing milestone date. If project has no
  dates, falls back to 1-year recency cutoff. Result: Bat Yam `status_advanced` 72 → 2.
- **`status_advanced` relevance filter**: now checks `_is_relevant_type()` on `request_type` OR
  `bakasha_description` — minor single-apartment additions no longer match multi-unit projects.
- **Scraped `מהות הבקשה`** (`bakasha_description`): added to Complot scraper and report output.
- **Detail-page gush/helka** (BUG-008): `_parse_bakasha_file` now extracts `gush`+`helka` from
  גושים וחלקות table; `_merge_permit` prefers this over the unreliable list-page value.
- **Permit number regex** (extends BUG-007): post-processor strips appended national ID from
  all extraction paths — `re.match(r'(20\d{6})', permit_num)`.
- **Extended excluded_categories filter**: now checks `request_type` as well as `request_category`.
- **Test permit filter**: matcher drops permits where `requestor` contains `ניסיון`.
- **CSV output**: scraper runner scripts switched from `.xlsx` to `.csv`; matcher auto-detects.
- **Bartech**: `שובץ לישיבת ועדה` → `בקשה להיתר` added to `STATUS_MAP`.
- **~35 new `_UNMAPPED_EVENTS`**: מבנה מסוכן, בקשה למידע workflow, deposit/Rishuy Zamin, admin.
- **Bat Yam final report**: 5 rows — 2 `status_advanced`, 1 `new_permit`, 2 `untracked`.
- **`bat_yam_matched_cache.json`** bootstrapped (2,202 permits).

### Session J — 2026-06-28 (handoff D)
- **Read old PRD** (`docs/Scraper_project_updates.pdf`) — identified 4 applicable ideas
- **Fixed first-match-wins bug** in GH index: matcher now collects ALL BO candidates sharing
  a Gush/Helka, then calls `_pick_best_candidate()` to resolve ties
- **Added `_pick_best_candidate()`** with 3-step disambiguation:
  1. Migrash exact match (if both sides populated)
  2. Date anchor: permit `request_date` vs BO `תאריך בקשה להיתר` (±4 days) — runs before
     fuzzy name so identical developer names don't mask a date-based distinction
  3. Fuzzy developer name: `thefuzz.partial_ratio(requestor, שם יזם/אדריכל/עו"ד) ≥ 80%`
- **Added `migrash` + `applicant_name` to Complot scraper**: `_parse_bakasha_file` now also
  parses the בעלי עניין table (מבקש row → `applicant_name`) and גושים וחלקות table
  (מספר מגרש → `migrash`). `_merge_permit` prefers detail-page applicant over list-page requestor.
- **Added 1-year cutoff** for `new_permit` and `untracked` flags — older than 365 days are
  silently dropped (not actionable). `status_advanced` is unaffected.
- **Added 7 events to `_UNMAPPED_EVENTS`**: 5 fee/admin events classified earlier + 2 new
  (`הוסר מסדר היום`, `החזרת תיק מסריקה`). Two more surfaced in D scrape (see immediate tasks).
- **Designed + implemented incremental scrape mode** (~10 min vs ~80 min full):
  - `ComplotPermitsAPI.scrape_targeted(records)` — refreshes status for known permit numbers
    without re-fetching the 9,600-row permit list
  - `matcher.run(..., matched_cache_path=...)` — saves JSON of all matched permit numbers
    (including unchanged) after each run; this is Phase A input for incremental
  - `scripts/run_bat_yam_incremental.py` — Phase A (re-check ~600 matched permits) +
    Phase B (scrape 2025-2026 only); runs matcher at end. ~10 min total.
- **Added `thefuzz` + `python-Levenshtein`** to `requirements.txt`; installed
- **Killed 4 duplicate Bat Yam processes**, restarted with updated code
  Log: `outputs/scrape_log_2026_06_28_D.txt`, started ~15:46, expected completion ~17:05
- **Holon scrape: COMPLETE** — `outputs/holon_fresh.xlsx` saved at 15:52 (1.9MB, 26,868 rows)

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

### 1. Review Krayot + Kiryat Ata reports

Both reports are ready for review:
- `outputs/krayot_report.xlsx` — 38 rows (1 new_permit, 35 status_advanced, 2 untracked)
- `outputs/kiryat_ata_report.xlsx` — 64 rows (0 new_permit, 23 status_advanced, 41 untracked)

Check for obvious false positives, especially in `untracked` rows (many single-apartment
additions may slip through if `bakasha_description` is empty).

### 2. Remaining unset annotation items (when reviewer responds)

Still unclassified in the annotation artifact:
- Complot: `הוצאת היתר בניה`, `ביטול היתר`, `החלטת ועדת ערר`, `הפקת פרסום תמ"38`, `עיכוב היתר ע"י ועדת ערר`
- Bartech detail: `תוכנית מאושרת בסמכות מהנדס` (currently in `_UNMAPPED_STAGES` — engineer-authority
  approval; likely `היתר בתנאים` but needs confirmation)

### 3. New cities

Current test cities are complete. Ready to add new Bartech or Complot cities when decided.

---

## Soon

### 4. Investigate automating the backoffice projects export
Currently `docs/bat_yam.xlsx` is a manual export. Check if the backoffice has a download
API endpoint — if yes, automate so reports always run against fresh project data.

### 5. Full rescrape of Bat Yam (quarterly)
Current `bat_yam_fresh.csv` is from 2026-06-28 (scrape D). The `detail_block_lot` fix
and permit number regex fix will only take effect in the next full scrape.
Run quarterly to refresh the identity cache and pick up old permit ↔ new project linkages.

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
| `scrapers/complot/api_scraper.py` | Complot API scraper — working; outputs `migrash` + `applicant_name` |
| `scrapers/bartech/api_scraper.py` | Bartech API scraper — two-phase (list + detail pages); `min_year` param |
| `scripts/run_bat_yam.py` | Full scrape runner (~80 min) |
| `scripts/run_bat_yam_incremental.py` | Incremental runner — Phase A + Phase B (~10 min) |
| `scripts/run_ramat_gan.py` | Ramat Gan (Complot, site_id=3) — needs office IP; re-scrape required |
| `scripts/run_kiryat_ata.py` | Kiryat Ata (Complot, site_id=32) — needs office IP |
| `scripts/run_holon.py` | Holon (Bartech) full scrape runner — min_year auto-computed |
| `scripts/run_krayot.py` | Krayot (Bartech, vkrayot.co.il) — min_year auto-computed from projects file |
| `transform/matcher.py` | Matching + report; `_pick_best_candidate()` for multi-project parcels |
| `transform/gush_helka.py` | Gush-helka parsing and set-intersection |
| `transform/address_match.py` | Address normalization and range matching |
| `docs/bat_yam.xlsx` | Madlan projects export for Bat Yam (601 rows) |
| `docs/holon_28062026.xlsx` | Madlan projects export for Holon (500 rows) |
| `outputs/bat_yam_fresh.csv` | Latest full Bat Yam scrape |
| `outputs/ramat_gan_fresh.csv` | Stale — scraped while IP-blocked, detail fields empty; re-scrape from office |
| `outputs/holon_fresh.csv` | Complete — 21,039 permits (2026-07-02) |
| `outputs/kiryat_ata_fresh.csv` | Complete — 3,318 permits (2026-07-02); some `היתר` statuses missing (old code) |
| `outputs/kiryat_ata_report.xlsx` | Matcher output — 14 status_advanced, 41 untracked |
| `outputs/holon_report.xlsx` | First run: 194 status_advanced, 3 untracked (pre-הסתיים fix); re-run in progress |
| `outputs/holon_matched_cache.json` | 2,487 matched permits (first run) |
| `outputs/krayot_fresh.csv` | Detail phase running ~14:00 2026-07-02 |
| `docs/krayot_projects_30062026.xlsx` | Madlan projects export for Krayot (534 projects) |
| `outputs/bat_yam_matched_cache.json` | Permit numbers matched to BO projects — Phase A input |
| `outputs/ramat_gan_matched_cache.json` | Generated by first matcher run (not yet run) |
| `outputs/bat_yam_report.xlsx` | Latest Bat Yam report (5 rows) |
| `docs/Ramat_Gan_Projects_30062026.xlsx` | Madlan projects export for Ramat Gan |
| `docs/session_handoffs/` | Per-session handoff notes |
