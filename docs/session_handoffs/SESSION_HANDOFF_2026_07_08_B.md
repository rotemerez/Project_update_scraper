# Session Handoff — 2026-07-08 B

**Date:** 2026-07-08
**Session:** Y
**Scope:** Hadera setup — filter parity check, Bartech scraper upgrades, two-phase scrape design

---

## What was accomplished

### 1. Filter parity: Bartech now matches Complot for all נוהל הקמת פרויקטים filters

Verified that `_is_public_use()` and `_is_below_unit_minimum()` lacked input data for Bartech:
- `shimush_ikari` (שימוש עיקרי) was absent from Bartech scraper output
- `unit_count` (מספר יח"ד) was absent from Bartech scraper output

Confirmed both fields exist on Bartech detail pages (DT/DD structure, same `_extract_dl_field()`
helper). Added extraction in `_parse_detail()`, initialization in `_parse_row()`, wiring in
`_enrich_with_details()`. Output schema updated in module docstring.

Sample from live Hadera page (permit 20240013):
- `שימוש עיקרי` = `מלאכה` ✓ (would be caught by `_is_public_use` if added to patterns)
- `מספר יח"ד` = '' (industrial permit, no units — correct)
- `תאור הבקשה` = `בניה חדשה` ✓

### 2. Hadera STATUS_MAP and STAGE_TO_STATUS entries

New STATUS_MAP (from smoke test list-page `[NEW STATUS]` log):
- `פתיחה` → `בקשה להיתר`
- `תשלום פקדון` → `בקשה להיתר`
- `בוצע פרסום` → `בקשה להיתר`

New STAGE_TO_STATUS (from smoke test `[NEW STAGE]` log — mapped entries):
- `ישיבת ועדה מקומית` → `בקשה להיתר`
- `שיבוץ בישיבת ועדה מקומית` → `בקשה להיתר`
- `שיבוץ בועדת מישנה` → `בקשה להיתר`
- `דחיה` → `בקשה להיתר`
- `הפקת בקשה לאישור תחילת עבודות` → `היתר`

New `_UNMAPPED_STAGES` (~25 entries): Rishuy Zamin workflow, spatial review error messages,
fee calculation steps, deposit steps, inspection steps, internal routing. All confirmed as
admin-only, no tracked milestone.

### 3. Bartech scraper refactored for two-phase scraping

`scrapers/bartech/api_scraper.py`:
- `_enrich_with_details(seen)` — extracted from `scrape()`, shared post-processor
- `scrape_parcels(parcel_pairs)` — fetches all permits by (gush, helka); uses `GushNumber`
  + `HelkaNumber` query params on the same `SearchPermitApplicationResults` endpoint (confirmed
  working on Hadera: returns all permits for that parcel)
- `merge_and_enrich(*seen_dicts)` — merges multiple raw seen-dicts, then enriches with details
- `_fetch_parcel_page(gush, helka, page)` — single parcel page fetch
- `early_exit_year` param on `_scrape_type()` — stops when all permits on a page predate year

### 4. `scripts/run_hadera.py` created

Two-phase runner:
- Phase A: parcel search for all 544 gush/helka pairs from the projects file
- Phase B: 1-year recent scan (`datetime.now().year - 1`) with early exit per type
- Merges + deduplicates before calling `merge_and_enrich()` for detail fetching

### 5. Hadera projects file confirmed

`docs/Hadera_Projects_08072026.xlsx`:
- 544 unique gush/helka pairs across all projects
- `min_year = 2010` (driven by `מנחם בגין 13 חדרה`, `היתר בתנאים`, permit date 2010-10-31, no Form 4)
- Bartech URL: `https://hadera.bartech-net.co.il`

---

## What's still pending — do first

### CRITICAL: Fix `scrape_parcels` before running Hadera

**Problem discovered in smoke test**: `scrape_parcels` has no early-exit by date and doesn't
honor `max_pages`. Parcel 10034-450 returned 39+ pages (5 rows each) before timeout — it's a
large municipal block returning hundreds of unrelated old permits.

**Exact fix needed** in `scrapers/bartech/api_scraper.py`, method `scrape_parcels`:

```python
def scrape_parcels(self, parcel_pairs: List[tuple]) -> Dict[str, Dict]:
    seen: Dict[str, Dict] = {}
    for gush, helka in parcel_pairs:
        page = 1
        while True:
            if self.max_pages and page > self.max_pages:   # ADD THIS
                break
            html = self._fetch_parcel_page(gush, helka, page)
            if not html or 'לא נמצאו נתונים' in html:
                break
            rows = self._parse_page(html, '', 51)
            if not rows:
                break
            new = 0
            for p in rows:
                if p['request_number'] not in seen:
                    seen[p['request_number']] = p
                    new += 1
            _log(f'  Parcel {gush}-{helka} page {page}: {len(rows)} rows, {new} new')
            # ADD EARLY EXIT: stop when all dated permits are older than min_year
            if self.min_year and rows:                      # ADD THIS BLOCK
                years = [_permit_year(r) for r in rows]
                dated = [y for y in years if y > 0]
                if dated and all(y < self.min_year for y in dated):
                    _log(f'  Early exit parcel {gush}-{helka}: all pre-{self.min_year}')
                    break
            if len(rows) < 5:
                break  # last page
            page += 1
            time.sleep(0.3)
    return seen
```

Also update `run_hadera.py` to set `scraper.min_year = _compute_min_year(projects_df)` before
calling `scrape_parcels()`.

**After fixing**: verify with `max_pages=2, parcel_pairs[:10]` smoke test — parcel 10034-450
should early-exit quickly once it hits pre-2010 permits.

---

## State of key files

| File | State |
|---|---|
| `scrapers/bartech/api_scraper.py` | Updated (session Y) — `shimush_ikari`, `unit_count`, two-phase methods, Hadera status/stage mappings |
| `scripts/run_hadera.py` | Created (session Y) — two-phase runner; needs `scrape_parcels` fix before running |
| `docs/Hadera_Projects_08072026.xlsx` | Valid — 544 gush/helka pairs, min_year=2010 |
| `outputs/hadera_fresh.csv` | Does not exist yet — scrape not yet run |
| `outputs/kiryat_ata_report.xlsx` | Valid — 89 rows (59 manual_review still pending review) |
| `transform/matcher.py` | Unchanged this session |
