# Bug Reference — Project Update Scraper

**Last Updated:** 2026-06-30

---

## BUG-009 — `status_advanced` flagged stale statuses older than project's existing dates

**Severity:** High — majority of `status_advanced` rows were false positives  
**Fixed in:** Session K (2026-06-30, handoff A)  
**File:** `transform/matcher.py` → `run()`

### Root cause

`_is_upgrade()` only compared status ranks (e.g. `בקשה להיתר` < `היתר`). It never checked
whether the scraped `permit_status_date` was newer than the project's existing milestone dates.
A permit with a 2011 `היתר` event would flag a project already holding a 2024 `תאריך היתר בתנאים`.

### Fix

Added `_latest_project_date()` (returns max of all non-empty BO milestone date columns) and
`_scraped_date_is_actionable()`:
- If scraped date missing → keep (can't compare)
- If project has dates → scraped date must be strictly after the latest
- If project has no dates → scraped date must be within 1 year

`status_advanced` now requires both `_is_upgrade()` AND `_scraped_date_is_actionable()`.

Result: Bat Yam `status_advanced` dropped from 72 to 2.

---

## BUG-008 — Complot list page returns wrong gush/helka for some permits

**Severity:** High — permits matched to wrong projects  
**Fixed in:** Session K (2026-06-30, handoff A)  
**File:** `scrapers/complot/api_scraper.py` → `_parse_bakasha_file()`, `_merge_permit()`

### Root cause

`GetBakashotByNumber` (permit list page) returns the building file's parcel, not the
individual permit's parcel. For example, permit 20160079 showed `7121-29` in the list
but `7121-54` in its detail page. This caused the permit to match the wrong project.

### Fix

`_parse_bakasha_file` now extracts `gush` and `helka` from the גושים וחלקות table on
the detail page and returns `detail_block_lot`. `_merge_permit` uses this value
preferentially, falling back to the list-page `block_lot` only if the detail page has none.

---

## BUG-007 — Complot list parser concatenates request number + rishuy zamin number

**Severity:** High — affected permits had no detail data; appeared as `scrape_status=success` with all NaN fields  
**Fixed in:** Session I (2026-06-28, handoff C) — partial; completed Session K (2026-06-30, handoff A)  
**File:** `scrapers/complot/api_scraper.py` → `_parse_permit_list()`

### Root cause

Some Complot list-page cells contain two numbers in the same `<td>`: the original request number
and the "מספר הבקשה ברישוי זמין" (rishuy zamin number). The fallback path used
`cells[0].get_text(strip=True)`, which concatenates all text nodes:

```
20180471  +  5176056615  →  201804715176056615
```

The scraper then called `GetBakashaFile?t=201804715176056615`, which returned an error page.
All detail fields (`request_type`, `request_category`, `permit_status`) were silently blank.

### Fix

```python
# Before:
cells[0].get_text(strip=True)

# After:
next(cells[0].stripped_strings, '')  # takes only the first text node
```

### Complete fix (Session K)

The session I fix only covered the fallback path. The primary `row_data` column lookup
(e.g. `row_data.get('מספר בקשה(רישוי זמין)')`) could still return the full concatenated value
if the column header existed in the page. Added a regex post-processor applied after all paths:

```python
_m = re.match(r'(20\d{6})', str(permit_num).strip())
if _m:
    permit_num = _m.group(1)
```

Local permit number format is `YYYY####` (8 digits starting with `20`). Verify for other cities.

### How to spot

Permit number in `bat_yam_fresh.csv` is 18+ digits and starts with a plausible 8-digit number.
Corresponding `request_type` and `permit_status` are NaN despite `scrape_status=success`.

---

## BUG-006 — Matcher year filter used `request_date` instead of `permit_status_date`

**Severity:** Medium — admitted old permits (e.g. 1979 status date) into the report  
**Fixed in:** Session I (2026-06-28, handoff C)  
**File:** `transform/matcher.py` → `run()`

### Root cause

`request_date` in Complot is the date the database record was created, not the actual permit
application date. Filtering by `request_date >= min_year` passed old permits whose record was
created in the cutoff window but whose actual milestone events were from the 1970s–1980s.

### Fix

Filter by `permit_status_date` (the date of the highest-ranked milestone event) instead.
Permits with no `permit_status_date` pass through (can't filter what we don't have).

A second filter on `first_event_date` (earliest event in the events table) was also added to
catch old permits whose first event predates the cutoff even if recent activity exists.
`first_event_date` requires a re-scrape to populate — not yet in existing `bat_yam_fresh.xlsx`.

---

## BUG-005 — Bartech `block_lot` returns raw Hebrew text instead of `GUSH-HELKA` format

**Severity:** Low — data was present but in wrong format (`גוש: 6786, חלקה: 8` vs `6786-8`)  
**Fixed in:** Session I (2026-06-28, handoff C)  
**File:** `scrapers/bartech/api_scraper.py` → `_parse_row()`

### Root cause

BeautifulSoup's `html.parser` lowercases all HTML attribute names. The code used
`label12.get('ToolTip', '')` (capital T) — this always returned `''`, falling through to the
raw text content. `_parse_block_lot('')` returned `''`, so the raw text was used as fallback.

### Fix

```python
# Before:
block_lot = _parse_block_lot(label12.get('ToolTip', '')) or label12.get_text(strip=True)

# After:
tooltip = label12.get('tooltip', '') or label12.get('ToolTip', '')  # try lowercase first
raw_text = label12.get_text(strip=True)
block_lot = _parse_block_lot(tooltip) or _parse_block_lot(raw_text) or raw_text
```

---

## BUG-004 — Bartech STATUS_MAP missing common statuses → silent empty `permit_status`

**Severity:** Low — affected classification accuracy; statuses logged as `[NEW STATUS]`  
**Fixed in:** Session I (2026-06-28, handoff C)  
**File:** `scrapers/bartech/api_scraper.py`

### Root cause

Initial `STATUS_MAP` only covered statuses known from the handoff document. First real scrape
surfaced 7 additional statuses not in the map, all silently mapping to `''`.

### Fix

Added to `STATUS_MAP`:
- `החלטה לאשר בועדה`, `בקרה מרחבית - הוחזר לעורך`, `פתיחת בקשה להיתר` → `בקשה להיתר`
- `העברת היתר לפיקוח על הבני`, `גמר בניה`, `מסירת א. תחילת עבודות` → `היתר`

Added to `_KNOWN_CLOSED` (logged but unmapped by design):
- `סגירת בקשה - פג תוקף החלטה`

---

## BUG-001 — NaN coercion: `float('nan') or ''` returns NaN, not `''`

**Severity:** Critical — caused matcher to produce 0 rows  
**Fixed in:** Session F (2026-06-27, handoff B)  
**File:** `transform/matcher.py`

### Root cause

Python's `or` operator returns the first truthy value. `float('nan')` is truthy (it is a
non-zero float), so `float('nan') or ''` evaluates to `float('nan')`, not `''`.

When pandas reads an empty Excel cell it stores `float('nan')`. The code used:

```python
str(permit.get('request_type', '') or '').strip()
```

This produced the string `'nan'` instead of `''` for every blank `request_type` cell, because:

```python
float('nan') or ''   # → float('nan')  (NaN is truthy!)
str(float('nan'))    # → 'nan'
```

### What broke

1. `type_known = bool('nan') = True` — the matcher thought the request type was known for every
   API-scraped permit, even though the API never returns `request_type`.
2. `type_relevant = _is_relevant_type('nan') = False` — `'nan'` doesn't match any construction type.
3. Combined effect: `(type_relevant or not type_known)` → `False or False` → `False` — the
   `new_permit` branch never fired. **0 rows output.**
4. Same issue in `scraped_status`: `'nan'` → `_is_upgrade()` returns `False` → `status_advanced`
   never fires either.

### Fix

Added `_clean()` helper that explicitly handles `None`, `float('nan')`, and the string `'nan'`:

```python
def _clean(val) -> str:
    if val is None:
        return ''
    if isinstance(val, float) and pd.isna(val):
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s
```

Replaced every `str(... or '').strip()` call with `_clean(...)` throughout `run()`.

### Prevention

Never use `x or ''` to guard against NaN. Always check `pd.isna()` or `isinstance(val, float)`
explicitly when the value may come from a DataFrame.

---

## BUG-002 — Matcher returned 0 rows (masked by BUG-001)

**Severity:** Critical — same root cause as BUG-001  
**Fixed in:** Session F (2026-06-27, handoff B)

Documented separately to clarify the symptom: the matcher produced an empty Excel report,
making it appear that there were no matching projects/permits. The actual gush-helka intersection
was 672 pairs (out of 779 project pairs and 2,705 permit pairs) — plenty of matches. The 0-row
output was entirely caused by BUG-001 preventing any branch from firing.

**After fix:** 414 `new_permit` rows, re-scrape in progress to surface `status_advanced` rows.
