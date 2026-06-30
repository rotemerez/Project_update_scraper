# Session Handoff — 2026-06-30 A

**Date:** 2026-06-30
**Session:** K
**Scope:** Report quality fixes — false positive elimination, scraper data improvements

---

## What was accomplished

### 1. `status_advanced` date guard (`_scraped_date_is_actionable`)

Added `_latest_project_date()` and `_scraped_date_is_actionable()` to `matcher.py`.
`status_advanced` now only fires if the permit's `permit_status_date` is strictly newer than
the latest existing milestone date on the BO project.

Rules:
- Scraped date missing → keep (can't compare)
- Project has existing dates → scraped date must be after the latest
- Project has no dates → scraped date must be within 1 year (same cutoff as `new_permit`)

Result: Bat Yam `status_advanced` dropped from 72 → 14 → 7 → 4 → 2 across successive fixes.

### 2. `status_advanced` relevance filter

`status_advanced` previously bypassed `_is_relevant_type()` entirely ("project already known
relevant"). Fixed: now checks `_is_relevant_type()` on `request_type` OR `bakasha_description`.
A minor single-apartment addition matching a multi-parcel project is now filtered out.

### 3. Scraped `מהות הבקשה` (bakasha_description)

`_parse_bakasha_file` now extracts `מהות הבקשה` (free-text nature of request) as
`bakasha_description`. Used as a second relevance signal alongside `request_type`
(since `תיאור הבקשה` is often vague, e.g. "תוספת למבנה קיים").
Added to report output as a visible column.

### 4. Detail-page gush/helka is authoritative (BUG-008)

The Complot list page (`GetBakashotByNumber`) returns the wrong parcel for some permits —
it shows the building file's parcel rather than the permit's actual parcel.

`_parse_bakasha_file` now also extracts `gush` and `helka` from the גושים וחלקות table
and returns `detail_block_lot`. `_merge_permit` uses `detail_block_lot` preferentially,
falling back to the list-page value only if the detail page has none.

### 5. Permit number concatenation — complete fix (extends BUG-007)

The session E fix (`next(cells[0].stripped_strings, '')`) only covered the fallback path.
The primary `row_data` column lookup could still return a concatenated value
(e.g. `2025064810000517679` instead of `20250648`).

Added a regex post-processor after all extraction paths:
```python
_m = re.match(r'(20\d{6})', str(permit_num).strip())
if _m:
    permit_num = _m.group(1)
```

This strips any appended national ID regardless of which code path extracted the number.

### 6. Extended excluded_categories filter

Previously only checked `request_category` (סוג הבקשה). Some permits have the excluded
category in `request_type` instead (or `request_category` is empty). Now checks both fields.

### 7. Test permit filter

Added filter in matcher: skip permits where `requestor` contains `ניסיון`.

### 8. Switched scraper outputs from xlsx to csv

`run_bat_yam.py`, `run_holon.py`, `run_bat_yam_incremental.py` now write `.csv`.
Matcher auto-detects by extension. Existing xlsx files converted to csv.
Typical speedup: 5-10x on the permit file read.

### 9. Bartech STATUS_MAP: added `שובץ לישיבת ועדה` → `בקשה להיתר`

### 10. Many new events added to `_UNMAPPED_EVENTS`

~35 new events across multiple runs:
- מבנה מסוכן declaration events
- בקשה למידע workflow events (entire workflow family)
- Deposit/Rishuy Zamin intake steps
- Licensing authority / inspector / committee admin events

### 11. Bat Yam report — final state

Ran incremental scrape (Phase A 2228 permits + Phase B 2025-2026).
Micro-rescrape of 10 type_confirmed=False permits with corrected numbers.
Final report: **5 rows** — 2 status_advanced, 1 new_permit, 2 untracked.

---

## What to do next session

### A. Test a second Complot city

Pick a city from `complot_cities.csv` (or the Complot city list). Steps:
1. Create `scripts/run_<city>.py` (copy `run_bat_yam.py`, update `site_id` and `city_name_hebrew`)
2. Export that city's projects from the backoffice → `docs/<city>_YYYYMMDD.xlsx`
3. Run full scrape (first time — no cache yet)
4. Run matcher with `matched_cache_path`
5. Review report for false positives, new event types, address matching issues

```python
matcher.run(
    'docs/<city>_YYYYMMDD.xlsx',
    'outputs/<city>_fresh.csv',
    '<city_hebrew>',
    'outputs/<city>_report.xlsx',
    matched_cache_path='outputs/<city>_matched_cache.json',
)
```

Excluded categories: use default `EXCLUDED_REQUEST_CATEGORIES` unless the city is
פתח תקווה or הרצליה (those pass `בקשה מקדמית`).

### B. Investigate Holon `status_advanced` count (1,675)

Bartech scraper doesn't populate `permit_status_date` — so `_scraped_date_is_actionable`
can't fire and no date filtering occurs. 1,675 out of 500 projects flagged suggests many
projects match multiple permits, each generating a row. Need to:
- Verify whether the Bartech detail page has a status date
- If yes: add `permit_status_date` extraction to Bartech scraper
- If not: consider using the permit's open date (`תאריך פתיחה`) as a proxy

### C. Verify permit number format for other Complot cities

The regex `r'(20\d{6})'` assumes 8-digit numbers starting with `20`. Confirm this holds for
other cities before running them. If a city uses a different format (e.g., longer numbers),
the regex will truncate incorrectly.

---

## State of key files

| File | State |
|---|---|
| `scrapers/complot/api_scraper.py` | Updated — `bakasha_description`, `detail_block_lot`, permit number regex, ~35 new unmapped events |
| `scrapers/bartech/api_scraper.py` | Updated — `שובץ לישיבת ועדה` → `בקשה להיתר` |
| `transform/matcher.py` | Updated — `_scraped_date_is_actionable`, `_latest_project_date`, relevance check for `status_advanced`, extended excluded_categories, ניסיון filter |
| `scripts/run_bat_yam.py` | Updated — CSV output |
| `scripts/run_holon.py` | Updated — CSV output |
| `scripts/run_bat_yam_incremental.py` | Updated — CSV paths |
| `outputs/bat_yam_fresh.csv` | Current — 9,639 rows (scrape D, 2026-06-28) |
| `outputs/bat_yam_fresh_incremental.csv` | Current — 2,875 rows (Phase A+B, 2026-06-29) |
| `outputs/bat_yam_matched_cache.json` | Current — 2,202 matched permits |
| `outputs/bat_yam_report.xlsx` | Current — 5 rows (2 status_advanced, 1 new_permit, 2 untracked) |
| `outputs/holon_fresh.csv` | Current — 26,869 rows (2026-06-28) |
| `outputs/holon_report.xlsx` | Current — 1,720 rows (status_advanced count inflated — see next steps B) |
| `docs/bat_yam.xlsx` | Ready — 601 projects |
| `docs/holon_28062026.xlsx` | Ready — 500 projects |
