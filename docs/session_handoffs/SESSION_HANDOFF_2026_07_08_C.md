# Session Handoff — 2026-07-08 C

**Date:** 2026-07-08
**Session:** Z
**Scope:** Hadera scraper — parcel-search investigation, plain type scan, scrape launched

---

## What was accomplished

### 1. `scrape_parcels` hardened (kept for future use)

`scrapers/bartech/api_scraper.py` — `scrape_parcels()` now has three exit conditions in addition
to the existing last-page and min_year exits:

- `max_pages` guard at loop top (for smoke testing)
- `max_pages_per_parcel = 20` hard cap — logs `[CAP]` when fired
- **Zero-new-streak exit**: 3 consecutive pages returning 0 new permits → stop. This is the
  key fix for the duplicate-parcel problem: once a parcel's permits are all already in `seen`
  (because another helka in the same gush was fetched first), the loop exits after 9 seconds
  instead of going all 20 pages.

Also added `min_year` filtering at the row-collection level in `scrape_parcels` — pre-`min_year`
permits are skipped before counting as "new".

### 2. Two-phase approach abandoned for Hadera

Investigation revealed: the Bartech `GushNumber+HelkaNumber` query returns permits for the
entire gush, not just the specific helka. The 544 Hadera project pairs mostly come from a few
large gushes (10034, 10037, 10038, 10036, 10042). After the first helka in each gush is fetched
(20 pages, 100 permits), all subsequent helkas in that gush return 100% duplicates and exit via
the zero-new-streak. Result: Phase A collected 100 unique permits from 20 parcels in 213s —
same coverage as just scraping type 51 directly, but slower.

`scripts/run_hadera.py` reverted to the same plain `scraper.scrape()` pattern used by Holon,
Krayot, and Kiryat Ata.

### 3. Hadera type-scan sort order confirmed

Sampled type 51 pages to determine sort order and early-exit behavior:

| Page | Year |
|------|------|
| 1–5  | 2018–2024 (mixed, sorted by permit number descending) |
| 100  | 2016 |
| 500  | 2011 |
| 1000 | 2007 |
| 2000 | 1998 |
| 4000 | 1979 |
| 5500 | 1955 |
| 6000 | 1949 |
| 6183–6188 | no date (paper-era records, year=0) |

Sort: **newest-first by permit number**. The `min_year=2010` early exit fires correctly when
all permits on a page are pre-2010. The portal holds records back to 1949.

### 4. Hadera scrape launched

`scripts/run_hadera.py` — plain type scan, `min_year=2010` (auto-computed).

- **Type 51** (מסלול רישוי מלא): ran 259 pages, collected **1,295 permits**.
  Note: portal reported 6,188 total pages but stopped returning results after page 259.
  Likely a per-session cap on the Hadera portal. Early exit did not need to fire.
- **Type 56** (מסלול רישוי מקוצר): 197 pages total, running as of ~14:08.
- **Types 57, 71, 72, 73**: pending.
- Log: `outputs/scrape_log_hadera.txt`
- Output: `outputs/hadera_fresh.csv` (written at end)

---

## What's still pending — do first

### Run Hadera matcher

1. Check `outputs/scrape_log_hadera.txt` for completion ("Detail phase complete" + "[OK] Saved").
2. Create `scripts/run_hadera_matcher.py`:
   - Copy from `scripts/run_kiryat_ata_matcher.py` (closest equivalent)
   - Update: `PROJECTS_PATH`, `SCRAPE_PATH`, `city_name`, `permit_url_base`
   - For `permit_url_base`: inspect a Hadera permit detail URL from `scrape_log_hadera.txt`
     or the Hadera portal to find the pattern. Likely something like
     `https://hadera.bartech-net.co.il/PermitApplicationDetails?...` but confirm.
3. Run the matcher and review the report.

### Also pending (unchanged from session Y)

- **Kiryat Ata report review** — 59 `manual_review` rows at `outputs/kiryat_ata_report.xlsx`.
- **Request 20250178** — wrong-project match (sub-permit), known case.

---

## State of key files

| File | State |
|---|---|
| `scrapers/bartech/api_scraper.py` | Updated (session Z) — `scrape_parcels` hardened with 3 new exits; `max_pages_per_parcel=20` |
| `scripts/run_hadera.py` | Updated (session Z) — plain `scraper.scrape()` pattern |
| `outputs/scrape_log_hadera.txt` | Live — type 51 done (1,295), type 56 running |
| `outputs/hadera_fresh.csv` | Does not exist yet — written at scrape completion |
| `outputs/kiryat_ata_report.xlsx` | Valid — 89 rows (59 manual_review pending review) |
