# Session Handoff — 2026-06-28 A

**Date:** 2026-06-28  
**Session:** G (first session of the day)  
**Scope:** Bat Yam / Complot pipeline

---

## What was accomplished

### 1. Removed fabricated data from matcher

The `scraped_status` column in the report was showing `בקשה להיתר` for all 414 rows.
This was a fallback — `scraped_status or 'בקשה להיתר'` — that fired when no event was mapped.
Removed from both `new_permit` and `untracked` branches. Blank is now blank. No invented values.

Same for `scraped_status_date`. Both are now empty when the scraper returned nothing real.

### 2. Discovered GetBakashaFile is accessible

Tested `GetBakashaFile` (permit detail page) from within a scraper session. It returns:
- `תיאור הבקשה` → the construction description (e.g. `תמ"א 38- הריסה ובנייה`)
- `סוג הבקשה` → permit category (e.g. `בקשה מקדמית`, `היתר בניה`)
- Per-permit events table with accurate `תיאור אירוע` + `תאריך אירוע`

This is the real fix for why `scraped_status` was empty — we were using `GetTikFile` (building-level)
which misses per-permit events, especially for older permits.

### 3. Rewrote api_scraper.py — replaced GetTikFile with GetBakashaFile

Old flow: GetBakashotByNumber → GetTikFile per unique building_id  
New flow: GetBakashotByNumber → GetBakashaFile per permit_num

Output schema now includes:
- `request_type` — from `תיאור הבקשה` (was always empty before)
- `request_category` — from `סוג הבקשה` (new field)
- `permit_status` / `permit_status_date` — from per-permit events (accurate)

Runtime: ~80 minutes for 9,639 permits at 0.5s/call.

`GetTikFile` code removed entirely.

### 4. matcher.py — new filters and columns

**`excluded_categories` parameter** (defaults to `EXCLUDED_REQUEST_CATEGORIES`):
Filters permits whose `request_category` is a non-real preliminary type before any matching.
Excluded by default (per נוהל הקמת פרויקטים מאי 2023):
- `בקשה מקדמית`, `בקשה עקרונית`, `בקשה למידע`, `בקשה לתיאום מקדים`, `תהליך ראשוני`

**City exception**: In פתח תקווה and הרצליה, `בקשה מקדמית` advances directly to a permit
without being closed and reopened. For those cities pass:
```python
excluded_categories=EXCLUDED_REQUEST_CATEGORIES - {'בקשה מקדמית'}
```

**`min_year` auto-computed** from projects file: earliest `תאריך בקשה להיתר` among projects
without `תאריך קבלת טופס 4`. For Bat Yam = **2011**.

**New report columns**:
- `project_sug_bnia` — from project's `סוג בנייה` column
- `type_confirmed` — True when `request_type` was known; False when empty (API limitation)
- `request_category` — the raw `סוג הבקשה` value from the detail page

**New type substrings** added to `RELEVANT_TYPE_SUBSTRINGS`:
- `חיזוק ותוספת` — תמ"א 38/1, may appear without the תמ"א prefix
- `צמודי קרקע` — attached housing

### 5. Read and applied נוהל הקמת פרויקטים מאי 2023

Key findings encoded in code and CLAUDE.md:
- Excluded request categories (listed above)
- Trackable construction types in CLAUDE.md
- Project timeframe: up to 10 years old without occupancy
- תמ"א 38 has no unit minimum; new construction requires 3+ units
- Build stage transitions: בתכנון → permit issued → בניה → Form 4 → הסתיים

---

## State of key files

| File | State |
|---|---|
| `scrapers/complot/api_scraper.py` | Rewritten — GetBakashaFile per permit, no GetTikFile |
| `transform/matcher.py` | Updated — excluded_categories, min_year, new columns |
| `CLAUDE.md` | Updated — data integrity rule, excluded categories, city exception |
| `docs/NEXT_STEPS.md` | Updated — session G done, immediate steps revised |
| `outputs/bat_yam_fresh.xlsx` | **STALE** — scraped with old scraper (GetTikFile). Must re-scrape. |
| `outputs/bat_yam_report.xlsx` | **STALE** — generated from stale scrape data |

---

## What to do next session

### Step 1 — Re-scrape Bat Yam with updated scraper (~80 min)

```
python scripts/run_bat_yam.py
```

This will call GetBakashaFile for each of the ~9,639 permits. Expect to see:
- `request_type` populated for most permits (instead of all-empty)
- `request_category` populated (filters out preliminary requests)
- `permit_status` / `permit_status_date` accurate per-permit

### Step 2 — Run the matcher

```python
from transform import matcher
matcher.run('docs/bat_yam.xlsx', 'outputs/bat_yam_fresh.xlsx', 'בת ים', 'outputs/bat_yam_report.xlsx')
```

min_year=2011 will be auto-computed. Expected changes vs previous run:
- `type_confirmed=True` rows now have real `request_type` values
- Preliminary requests excluded automatically
- `scraped_status` populated for permits with real events
- Possibly some `status_advanced` rows

### Step 3 — Review the report

Open `outputs/bat_yam_report.xlsx`:
- Are `request_type` values sensible? (Should see `תמ"א 38`, `בניה חדשה`, etc.)
- Any new `request_category` values we haven't seen? Add new exclusions if needed.
- Does `type_confirmed=False` cover only edge cases, or is it widespread?
- Check `status_advanced` rows if any appear.

### Step 4 — [USER ACTION] Investigate גוש 7141-52

Request 20211734 was a `בקשה מקדמית` for `תמ"א 38- הריסה ובנייה` at גוש 7141-52.
It closed without a permit (`סיום טיפול בבקשה להיתר ללא הוצאת היתר`).
Question: Is there a separate non-preliminary permit for this parcel we should track?

---

## Key API facts (for reference)

| Endpoint | Purpose | Auth required |
|---|---|---|
| `GetBakashotByNumber` | Full permit list, deduplicated across b= params | None |
| `GetBakashaFile` | Per-permit detail: request_type, request_category, events | None (session) |
| `GetTikFile` | Building-level events — **no longer used** | None |
| `GetBakashaFile` (old test) | Was wrongly tested outside scraper session — appeared blocked | N/A |

---

## Gotcha — city name must be Hebrew in matcher.run()

Always pass `city_hebrew='בת ים'` not `'bat yam'`. The address-matching regex uses
`re.escape(city)` against Hebrew text and will silently fail with an English string.
