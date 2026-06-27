# Session Handoff — 2026-06-27 A

## What was accomplished

### Built `scrapers/complot/api_scraper.py` — API-based scraper, no Selenium

Complete implementation:
- `ComplotPermitsAPI.scrape()` — two-step: `GetBakashotByNumber` list + `GetTikFile` per building
- `_parse_permit_list()` — handles the 9-column HTML table (first column is empty checkbox column)
- `_parse_tik_file()` — finds the requests table by `ארוע אחרון להצגה` header (no `id=table-requests` in the real HTML — the id was wrong in the handoff)
- `EVENT_TO_STATUS` expanded with `היתר היסטורי` → `היתר`, `בקשה ללא היתר` → `בקשה להיתר`, `הפקת היתר בניה לחתימות` → `היתר`
- UTF-8 stdout reconfigure at module load (same as `scraper.py`)
- **Validated**: permit 20250 → `טופס 4` ✓

### Expanded permit list to full history (2011–2026)

Discovered `b=` is a **substring match on permit number**, not a year filter:
- `b=0` → server error; `b=1` → timeout (matches almost everything)
- `b=2025` returns all permits in the "2025x" series (permit numbers 20250–20769)
- Solution: cycle `b=2011` through `b=2026`, deduplicate by `permit_num`

Updated `ComplotPermitsAPI.__init__` to accept `b_params: List[int]` (default `range(2011, 2027)`).
`_get_permit_list()` now loops, deduplicates via `seen` dict, and logs per-year counts.

**Full scrape result** (run: 2026-06-27 14:12 → 15:00, ~47 min):

| Year | Rows | New unique |
|------|------|------------|
| 2011 | 461 | 461 |
| 2012 | 510 | 509 |
| 2013 | 448 | 444 |
| 2014 | 464 | 459 |
| 2015 | 382 | 378 |
| 2016 | 970 | 962 |
| 2017 | 1198 | 1191 |
| 2018 | 796 | 788 |
| 2019 | 860 | 849 |
| 2020 | 634 | 416 |
| 2021 | 608 | 598 |
| 2022 | 752 | 718 |
| 2023 | 611 | 603 |
| 2024 | 484 | 476 |
| 2025 | 520 | 508 |
| 2026 | 287 | 279 |
| **Total** | | **9,639** |

Output: `outputs/bat_yam_fresh.xlsx` (9,639 rows).

### Fixed `transform/matcher.py` — type-filter logic for empty `request_type`

The API scraper cannot populate `request_type` (requires `GetBakashaFile` which is blocked).
With the old logic, `_is_relevant_type('')` → False → UC1/UC2/UC4 all blocked.

Fix:
- **UC2**: project already exists in Madlan → type is already known relevant → skip type filter entirely
- **UC1**: skip type filter when `request_type` is empty (`type_known = False`)
- **UC4**: still requires type filter (but since `request_type` is always empty from API, UC4 never fires — acceptable for now)

Also fixed: `request_type` column reads as `NaN` (float) from Excel — added `str(... or '')` coercion.

---

## Current blocker: matcher returns 0 rows

Ran `matcher.run(...)` against `outputs/bat_yam_fresh.xlsx` → **0 rows, no report written**.

Debugging was interrupted before root cause was confirmed, but the most likely cause:

**Gush-helka intersection is zero** — the matcher builds a dict from projects' `גוש-חלקה` column and looks up each permit's `block_lot`. Early debugging showed:

- Projects `גוש-חלקה` parses correctly: `'7128-259 , 7128-264'` → `{('7128','259'), ('7128','264')}`
- Permits `block_lot` parses correctly: `'7120-77'` → `{('7120','77')}`
- But **intersection = 0** (confirmed by the 0-row result)

Possible causes to investigate:
1. **Projects `גוש-חלקה` is mostly empty** — many Madlan projects may not have gush-helka filled in
2. **The scraped permit gush-helka doesn't match** — Complot stores gush without sub-parcel; Madlan may have sub-parcel suffixed (e.g. `7120-77-0`)
3. **Address fallback also fails** — `am.match()` compares `שם פרויקט` against `full_address`; the project name format vs address format may not align
4. **`block_lot` is empty for many permits** — the `גוש` and `חלקה` columns might be blank for many rows

---

## Immediate next steps

### 1. Debug the matcher — find why 0 matches

```python
import pandas as pd
from transform import gush_helka as gh

projects_df = pd.read_excel("docs/bat_yam.xlsx")
permits_df = pd.read_excel("outputs/bat_yam_fresh.xlsx")

# How many projects have gush-helka filled?
has_gh = projects_df["גוש-חלקה"].notna() & (projects_df["גוש-חלקה"] != "")
print("Projects with גוש-חלקה:", has_gh.sum(), "/", len(projects_df))

# How many permits have block_lot filled?
has_bl = permits_df["block_lot"].notna() & (permits_df["block_lot"] != "")
print("Permits with block_lot:", has_bl.sum(), "/", len(permits_df))

# Intersection
proj_pairs = set()
for v in projects_df["גוש-חלקה"].dropna():
    proj_pairs.update(gh.parse(str(v)))

perm_pairs = set()
for v in permits_df["block_lot"].dropna():
    perm_pairs.update(gh.parse(str(v)))

print("Project pairs:", len(proj_pairs), "  Permit pairs:", len(perm_pairs))
print("Intersection:", len(proj_pairs & perm_pairs))
print("Sample project pairs:", list(proj_pairs)[:5])
print("Sample permit pairs:", list(perm_pairs)[:5])
```

### 2. Fix whichever side is wrong and re-run matcher

Likely fix paths:
- If projects `גוש-חלקה` is mostly empty → need a different match strategy (address only, or fill in gush-helka from govmap)
- If format mismatch → normalise before comparison in `gush_helka.py`
- If `block_lot` is empty in scraper output → check why `גוש` / `חלקה` columns from `GetBakashotByNumber` aren't being picked up

### 3. Address fallback — verify it works independently

Even if gush-helka fails, address matching should catch some projects. Test:
```python
from transform import address_match as am
# Try a known project
am.match("האורגים 18 פרויקט", "האורגים 18 בת ים", "בת ים")
```

---

## New unmapped events seen in wild (from 2011–2026 scrape)

These appear in `ארוע אחרון להצגה` but aren't in `EVENT_TO_STATUS` yet:
- `סיום טיפול בבקשה להיתר ללא הוצאת היתר` — closed without permit; probably map to `''` (leave unmapped, not a milestone)
- `החזרת תיק מסריקה` — admin/processing event; leave unmapped

---

## Key file paths

| Path | Role |
|---|---|
| `scrapers/complot/api_scraper.py` | API scraper — working, produces `outputs/bat_yam_fresh.xlsx` |
| `scrapers/complot/scraper.py` | Old Selenium scraper — superseded |
| `run_bat_yam.py` | Runner — uses `ComplotPermitsAPI`, `max_requests=None` |
| `transform/matcher.py` | Matcher — 0 rows bug needs investigation |
| `transform/gush_helka.py` | Gush-helka parsing |
| `transform/address_match.py` | Address normalization and matching |
| `docs/bat_yam.xlsx` | Madlan projects export (601 rows) |
| `outputs/bat_yam_fresh.xlsx` | Fresh scrape (9,639 permits, 2011–2026) |
| `outputs/run_bat_yam_log.txt` | Full scrape log |

## Python
`C:\Users\Rotem\AppData\Local\Programs\Python\Python314\python.exe`
Run from project root: `cd c:/R_PROJECTS/Project_update_scraper`
