# Session Handoff — 2026-07-13 B

**Date:** 2026-07-13  
**Session:** N  
**Scope:** min_year fix for Complot scraper; mordot carmel relaunch; event classification; triage artifact (incomplete)

---

## What was accomplished

### 1. `min_year` gap in Complot scraper — found and fixed

**Problem:** `run_mordot_carmel.py` computed `min_year` via `_compute_min_year()` but never passed
it to `ComplotPermitsAPI`. The scraper had no `min_year` parameter at all. Result: every scrape
fetched all permits from 2011 onward (20,098 for mordot carmel), ignoring the year filter entirely.

**Fix:**
- Added `min_year: Optional[int] = None` to `ComplotPermitsAPI.__init__`
- Added `_passes_min_year(date_str)` method (returns `True` if year >= self.min_year, or if date
  unparseable — avoids silent drops)
- `scrape()` now filters permit list by `min_year` before the detail-fetch phase (saves the slow
  `GetBakashaFile` calls for out-of-range permits)
- `run_mordot_carmel.py` updated to pass `min_year=min_year`

**mordot carmel result:** 20,098 list → 18,540 after min_year=2015 filter (dropped 2011–2014).
Still a large scrape (~2.5 hrs at 0.5s/permit), but 8% smaller than without the fix.

**Note:** This fix applies to all future Complot scrapers. Any existing runner script that calls
`ComplotPermitsAPI` without `min_year` will still work (defaults to `None` = no filter).

### 2. mordot carmel scrape relaunched

Killed the stuck scrape (was at 1553/20098, started the previous session before the fix).
Relaunched from office at ~09:29 with min_year=2015. Was at permit ~17/18540 at end of session.
Expected completion: several hours after launch (probably done by next session).

### 3. New Complot events classified

From the first ~80 mordot carmel detail pages, these new events appeared and were classified:

**Added to `EVENT_TO_STATUS`:**
- `חתימת היתר` → `'היתר'` (signing the permit; `חתימת היתר בניה` was already mapped)
- `הפקת היתר בניה` → `'היתר בתנאים'` (generating permit doc for signing, pre-delivery)
- `שיבוץ לישיבת ועדה` → `'בקשה להיתר'` (same family as `שיבוץ לועדת משנה`)

**Added to `_UNMAPPED_EVENTS` (mordot carmel block):**
`בדיקה לשחרור ערבות`, `פתיחת ערבות`, `סיום ושחרור ערבות`, `דוח מפקח`,
`דיווח מפקח בשלבי בניה`, `דו"ח פיקוח לפני וועדה`, `דו"ח ביקור לטופס 4`,
`העברת נתונים לשמאי לעריכת שומה`, `החזרת התיק משמאי`, `השלמת דרישות בקרת תכן`,
`אי השלמת דרישות בקרת תכן`, `המתנה לתיקון תכנית אצל העורך`, `הגשת הבקשה מחדש`,
`העברת תכנית לפיקוח`, `שיבוץ לישיבת מליאה`, `הודעה על פרסום הקלה`

**2 events seen but NOT yet classified** (appeared a few permits in):
- `מסירת אישור הרצת מערכות` — delivery of systems-running approval
- `הפקת אישור הרצת מערכות` — producing systems-running approval
Both are likely `היתר` milestones. Add before running the matcher.

### 4. Complot triage artifact — first attempt, wrong design

Built an artifact at https://claude.ai/code/artifact/72b9f41b-7c31-4e2e-a557-c8a685ea05d7 but
the design was wrong: paste-log input, 6 buttons per row. The Bartech artifact
(https://claude.ai/code/artifact/c0dae2d0-319e-4123-b580-332c90957984) was fetched to understand
the correct design:
- Table layout: row# | Hebrew event text (RTL) | `<select>` dropdown
- Colored dropdown border/background updates on selection
- Events hardcoded in JS (no paste step)
- localStorage persistence across page closes
- "Unset only" toggle + search
- "Mark visible → ignore" bulk button
- Export JSON (or Python) of all classifications

**Not rebuilt yet.** Next session: deduplicate the full log, embed unique events into a new
artifact matching the Bartech design.

---

## Open items carried forward

- **2 unclassified events**: `מסירת אישור הרצת מערכות`, `הפקת אישור הרצת מערכות`
- **Complot triage artifact**: rebuild to match Bartech design
- **מורדות כרמל matcher**: run once scrape finishes
- **Pending report reviews**: קרית אתא, הראל, זמורה, מיצפה אפק, ישובי הברון
- **Hadera stage classification**: Bartech artifact still open
- **מורדות כרמל**: still needs office IP for future scrapes

---

## What to do next session

### Step 1 — Check if mordot carmel scrape finished

```powershell
Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_mordot_carmel.txt' -Tail 5
```
Look for `Done. NNNNN permits assembled.` to confirm completion.

### Step 2 — Classify 2 remaining events + deduplicate full log

Add to `scrapers/complot/api_scraper.py` before running matcher:
- `מסירת אישור הרצת מערכות` → classify (probably `'היתר'`)
- `הפקת אישור הרצת מערכות` → classify (probably `'היתר'`)

Then extract all unique events from the full log:
```powershell
$env:PYTHONUTF8 = '1'
$log = Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_mordot_carmel.txt' -Encoding UTF8
$counts = @{}
foreach ($line in $log) {
    if ($line -match '\[NEW EVENT\] Unmapped: \[(.+?)\]') {
        $counts[$matches[1].Trim()] = ($counts[$matches[1].Trim()] ?? 0) + 1
    }
}
$counts.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "$($_.Value)`t$($_.Key)" }
```

### Step 3 — Rebuild Complot triage artifact

Match the Bartech design exactly (see fetched source). Embed unique events from the log.
Pre-mark the ones already classified this session.

### Step 4 — Run mordot carmel matcher

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\run_mordot_carmel_matcher.py
```

---

## State of key files

| File | State |
|---|---|
| `scrapers/complot/api_scraper.py` | Updated — `min_year` param + `_passes_min_year()`; 3 new `EVENT_TO_STATUS`; 17 new `_UNMAPPED_EVENTS` |
| `scripts/run_mordot_carmel.py` | Updated — passes `min_year=min_year` |
| `outputs/scrape_log_mordot_carmel.txt` | Running — ~09:29 start, 18,540 permits, min_year=2015 |
| `outputs/mordot_carmel_fresh.csv` | Not yet written (scrape in progress) |
