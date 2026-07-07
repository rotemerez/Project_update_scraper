# Session Handoff — 2026-07-05 B

**Date:** 2026-07-05
**Session:** T
**Scope:** Kiryat Ata report review, matcher false-positive fixes (אוכלס, public building, unit minimum)

---

## What was accomplished

### 1. Kiryat Ata report — first reviewer pass (requests 1–9)

Reviewer annotated 9 rows from `outputs/kiryat_ata_report.xlsx` (64-row report from Session S):

| Request | Verdict | Reason |
|---|---|---|
| 20110413 | False positive | Matched to הגפן 2 (completed) — different project: different start date (28/11/2011 vs 23/08/2010), different unit count (3 vs 5), demolition+rebuild adjacent to existing building |
| 20140052 | False positive | Matched to completed project — minor changes to existing buildings (garbage/gas room), project already אוכלס |
| 20140208 | False positive | Matched to completed project — barely any request details (מבנה טכני use, no unit count), project already אוכלס |
| 20150266 | False positive | Matched to completed project — single-room addition to one unit in existing 7-floor building, project already אוכלס |
| 20220181 | Confirmed status advance | ✓ |
| 20230159 | Confirmed status advance | ✓ |
| 20230260 | Confirmed status advance | ✓ |
| 20230283 | Confirmed status advance | ✓ |
| 20230289 | Confirmed status advance | ✓ |

Root cause of requests 1–4: `אוכלס` was not in `DB_STATUS_NORM`, so its rank was -1 and any scraped
status appeared as an upgrade.

### 2. Fix: treat `אוכלס` same as `הסתיים` in matcher

`transform/matcher.py`:
```python
if db_status_raw in ('הסתיים', 'אוכלס'):
```
(previously only `'הסתיים'`)

Re-ran matcher: **64 → 60 rows** (18 `status_advanced`, 42 `untracked`).
The 4 false positives are gone. Request 20110413 (new project on same parcel) surfaced correctly as
`untracked` but was dropped as not recent (2011 start date > 365-day cutoff).

### 3. Kiryat Ata report — second reviewer pass (requests in untracked section)

Reviewer annotated the following `untracked` rows in the 60-row report:

| Request | Verdict | Reason |
|---|---|---|
| 20250178 | False positive (wrong match) | Matched to open project 11051-3 — different project: report shows date 2024-02-07 but actual date is 13/07/2025 (Complot list-page date bug); bakasha_description says it's a dig+foundation sub-permit referencing request 20250142 |
| 20250181 | Date confusion (valid permit?) | permit_status_date = 28/06/2026 = date of שיבוץ לועדת משנה event, not filing date; request_date = 16/07/2025 (correct). Status date behavior is correct — see note below. |
| 20250184 | False positive | Construction of a gym in a school — public building, not a Madlan project |
| 20250188 | Date confusion | Same as 20250181; request_date = 27/07/2025 |
| 20250192 | False positive | Minor changes to a single family home — does not meet project creation criteria |
| 20250201 | Date confusion | Same as 20250181; request_date = 17/08/2025 |
| 20250203 | Date confusion | Same as 20250181; request_date = 19/08/2025 |
| 20250216 | False positive | No unit count, no floors, no description — insufficient information |
| 20250228 | False positive | Single family home — below 3-unit minimum for בניה חדשה |

**Note on status_date confusion (20250181, 20250188, 20250201, 20250203):**
The `scraped_status_date` column shows the date of the LATEST event that mapped to the current
`permit_status`. For these permits, the latest mapped event is `שיבוץ לועדת משנה` (→ `בקשה להיתר`)
on 28/06/2026. This is correct behavior — it is NOT the filing date, which is in `request_date`.
These permits are not necessarily false positives; the date shown is just the most recent committee
scheduling event, which is routine.

### 4. Read נוהל הקמת פרויקטים מאי 2023 PDF

Key project creation thresholds extracted:
- **בניה חדשה**: minimum 3 units
- **צמודי קרקע**: minimum 4 units (same developer)
- **תמ"א 38**: no minimum
- **מבני ציבור** (kindergartens, synagogues, schools, etc.): NOT tracked — never open a project

### 5. Complot scraper: added `shimush_ikari` field

`scrapers/complot/api_scraper.py`:
- `_parse_bakasha_file()` now extracts `שימוש עיקרי` from the detail page
- Field name: `shimush_ikari`
- Added to output schema, `_merge_permit()`, and `scrape_targeted()` fallback
- `shimush_ikari` now appears as a column in all future Complot CSV outputs

### 6. Matcher: added `_is_public_use()` and `_is_below_unit_minimum()` filters

`transform/matcher.py`:
- `_PUBLIC_USE_PATTERNS`: list of use-type strings that indicate non-trackable public buildings
- `_is_public_use(permit)`: checks `shimush_ikari` first, then `bakasha_description` fallback
- `_extract_unit_count(text)`: regex-based unit count parser from Hebrew free text
- `_is_below_unit_minimum(permit)`: returns True if explicit unit count < 3 (or < 4 for צמודי קרקע);
  תמ"א 38 is never filtered; returns False if no count can be parsed (avoids false negatives)
- Both filters applied to `untracked` (unmatched) branch AND to `הסתיים`/`אוכלס` completed-project branch
- `shimush_ikari` added to `_make_row()` output so it appears in the report

**Session ended before verifying whether these filters reduced the count.** The final re-run
still showed 60 rows. The filters may not have fired because:
1. The existing `kiryat_ata_fresh.csv` was scraped before `shimush_ikari` was added — that column
   is empty for all permits, so `_is_public_use()` relies entirely on `bakasha_description` keywords.
2. The `bakasha_description` patterns in the actual data may differ from the keywords in `_PUBLIC_USE_PATTERNS`.
3. The unit count for 20250228 (single SFH) may not be stated in a parseable format in the CSV.

---

## What's still pending

### Immediate — next session

#### 1. Diagnose why the public-building and unit-minimum filters didn't fire

Inspect `bakasha_description` for the problem rows to understand what text is actually there:

```python
import pandas as pd
df = pd.read_csv('outputs/kiryat_ata_fresh.csv', encoding='utf-8-sig')
targets = ['20250178', '20250184', '20250192', '20250216', '20250228']
cols = ['request_number', 'request_date', 'request_type', 'bakasha_description', 'permit_status']
for t in targets:
    rows = df[df['request_number'].astype(str) == t]
    if not rows.empty:
        r = rows.iloc[0]
        for c in cols:
            print(f'{c}: {r.get(c, "")}')
        print()
```

Then either:
- Add the correct keywords/patterns to `_PUBLIC_USE_PATTERNS` or the unit count extractor
- Or conclude the data is too sparse and these require manual review

#### 2. Request 20250178 — wrong-project match

This is a `status_advanced` row matched to open project 11051-3 via gush-helka. It's actually a
dig+foundation sub-permit for a different project (20250142). Two issues:
- The `request_date` in the CSV is 2024-02-07 (Complot list-page date bug; actual filing is 13/07/2025)
- The bakasha_description references permit 20250142 — it's not a standalone project

This can't be auto-filtered reliably. Decide: accept as a known false positive that requires manual
review, or add a pattern that detects "dig/foundation only" permits as sub-permits.

#### 3. Re-scrape Kiryat Ata to populate `shimush_ikari`

Once the false-positive analysis is complete and filter patterns are finalized, re-scrape:
```bash
PYTHONPATH=/c/R_PROJECTS/Project_update_scraper \
  /c/Users/Rotem/AppData/Local/Programs/Python/Python313/python.exe \
  scripts/run_kiryat_ata.py
```
Then re-run the matcher. The `shimush_ikari` field will be populated and `_is_public_use()` will
work correctly from that data.

#### 4. Remaining Kiryat Ata untracked rows

After fixing the filters, review remaining `untracked` rows to decide:
- Open new BO projects for confirmed qualifying permits
- Reject anything still slipping through

#### 5. Remaining annotation decisions (from previous sessions)

Still unclassified:
- **Complot**: `הוצאת היתר בניה`, `ביטול היתר`, `החלטת ועדת ערר`, `הפקת פרסום תמ"38`, `עיכוב היתר ע"י ועדת ערר`
- **Bartech**: `תוכנית מאושרת בסמכות מהנדס` (currently `_UNMAPPED_STAGES`; likely `היתר בתנאים`)

---

## State of key files

| File | State |
|---|---|
| `transform/matcher.py` | Updated — `אוכלס` handled like `הסתיים`; `_is_public_use()`, `_is_below_unit_minimum()` added; `shimush_ikari` in output |
| `scrapers/complot/api_scraper.py` | Updated — `shimush_ikari` extracted from detail page |
| `outputs/kiryat_ata_report.xlsx` | 60 rows (18 `status_advanced`, 42 `untracked`) — review in progress |
| `outputs/kiryat_ata_fresh.csv` | 3,318 permits — no `shimush_ikari` column (scraped before this session's change) |
| `outputs/kiryat_ata_matched_cache.json` | 705 permits |
| `outputs/krayot_report.xlsx` | 38 rows — not yet reviewed beyond first pass |
