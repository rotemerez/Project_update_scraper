# Bug Reference — Project Update Scraper

**Last Updated:** 2026-07-07

---

## BUG-012 — `הוצאת היתר בניה` in both `EVENT_TO_STATUS` and `_MANUAL_REVIEW_EVENTS` simultaneously

**Severity:** Medium — caused `permit_status` to show `היתר בתנאים` instead of `היתר` for permits where this was the highest-ranked event  
**Fixed in:** Session V (2026-07-07)  
**File:** `scrapers/complot/api_scraper.py` → `EVENT_TO_STATUS`

### Root cause

Session U intended to remove `הוצאת היתר בניה` from `EVENT_TO_STATUS` and move it exclusively to
`_MANUAL_REVIEW_EVENTS`. The removal did not survive (code was in uncommitted working-tree state).
With the event in both sets, the manual review flag fired correctly but the event also contributed to
`best_rank`, causing `permit_status` to be set inconsistently depending on other events present.
In practice, for permit 20130371, `permit_status = 'היתר בתנאים'` even though the permit had an
`הוצאת היתר בניה` event with higher rank.

### Fix

Removed `'הוצאת היתר בניה': 'היתר'` from `EVENT_TO_STATUS`. The event now lives only in
`_MANUAL_REVIEW_EVENTS`. Status `היתר` is now sourced from the `תאריך הפקת היתר` header field
(see BUG-013) or from other `היתר`-mapping events (`מתן היתר למבקש`, `מסירת היתר`, etc.).

---

## BUG-013 — `permit_status` not set to `היתר` when only `תאריך הפקת היתר` header field is present

**Severity:** Medium — permits with issued permits showed `היתר בתנאים` in the report  
**Fixed in:** Session V (2026-07-07)  
**File:** `scrapers/complot/api_scraper.py` → `_parse_bakasha_file()`, `_merge_permit()`

### Root cause

The permit detail page has a header field `תאריך הפקת היתר` (permit issuance date) that is set
when the permit was formally issued. The scraper only derived `permit_status` from the events table
(`שלבי הבקשה`). If the only `היתר`-level event was `הוצאת היתר בניה` (now removed from
`EVENT_TO_STATUS`), no event mapped to `היתר` and the status remained at `היתר בתנאים`.

### Fix

`_parse_bakasha_file()` now extracts `תאריך הפקת היתר` via `_extract_field()`.
`_merge_permit()` compares its rank (`היתר` = 2) against the event-derived status rank.
If the field implies a higher status, `permit_status` and `permit_status_date` are overridden.
`טופס 4` events (rank 3) still take priority. Requires re-scrape to populate existing CSVs.

---

## BUG-011 — Matched `manual_review` branch applied no project-criteria filters

**Severity:** High — 40 of 177 `manual_review` rows were noise (irrelevant type, public use, stale date)  
**Fixed in:** Session V (2026-07-07)  
**File:** `transform/matcher.py` → `run()` matched branch

### Root cause

When a matched permit had a non-empty `manual_review_event`, the matcher emitted a row immediately
without checking whether the permit met project-creation criteria. The same filters applied to
`untracked` and `הסתיים`/`אוכלס` branches were absent here. Result: permits with irrelevant
construction types (`תוספת למבנה קיים`, `שונות`), public buildings, and unit counts below the
minimum all appeared as `manual_review` rows.

### Fix

Added three guards before emitting a `manual_review` row for a matched permit:
1. `_is_relevant_type(request_type)` — must be True
2. `_is_public_use(permit)` — must be False
3. `_is_below_unit_minimum(permit)` — must be False, with an exception: if the matched project's
   `סוג בנייה` contains `תמ"א 38`, the unit minimum is waived (Complot labels these as `בניה חדשה`).

---

## BUG-010 — Temporal mismatch: old permits matched to new projects via shared gush-helka

**Severity:** High — permits from 2013/2014 matched to projects created in 2020/2021  
**Fixed in:** Session V (2026-07-07)  
**File:** `transform/matcher.py` → `run()`, new `_is_temporally_plausible()`

### Root cause

The gush-helka and address-fallback matching had no temporal guard. A permit from 2013 could match
a project created in 2021 if they shared a parcel — even though they are entirely separate
applications on the same land. Example: permit 20130414 (2013) matched project `הדקלים_3_קרית_אתא`
whose `תאריך בקשה להיתר` is 2021-12-21 (8-year gap).

### Fix

Added `_is_temporally_plausible(permit, proj, max_days_before=365)`: returns False if the permit's
`request_date` is more than 365 days before the project's `תאריך בקשה להיתר`. Applied at both
match methods:
- Gush-helka: candidates are filtered to `plausible` list before `_pick_best_candidate()`
- Address fallback: plausibility check added inline before accepting the match

When no candidates pass the check, `matched_idx` stays None and the permit falls through to the
unmatched path where age and type filters apply.

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
