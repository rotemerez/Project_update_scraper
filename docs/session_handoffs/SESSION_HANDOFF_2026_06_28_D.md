# Session Handoff — 2026-06-28 D

**Date:** 2026-06-28
**Session:** J
**Scope:** PRD analysis, matcher multi-project fix, Complot scraper enhancements, incremental scrape design + implementation

---

## What was accomplished

### 1. PRD analysis — `docs/Scraper_project_updates.pdf`

Read an old design document proposing a state-machine matching hierarchy. Four ideas were
evaluated for incorporation:

| Idea | Decision |
|---|---|
| Fix first-match-wins on shared parcel | Done |
| Migrash precision filter | Done |
| Date anchor ±4 days | Done |
| Fuzzy developer name match | Done |

### 2. Matcher: fixed first-match-wins bug + added `_pick_best_candidate()`

Previously `gh_index[pair][0]` was taken — the first BO project sharing a Gush/Helka.
Now all candidates are collected, then `_pick_best_candidate()` resolves ties in order:

1. **Migrash** — exact match on `migrash` (permit) vs parsed `תבע+מגרש` (BO)
2. **Date anchor** — `request_date` vs `תאריך בקשה להיתר` within ±4 days
   (intentionally before fuzzy name — identical developer names would otherwise mask this)
3. **Fuzzy developer name** — `thefuzz.partial_ratio(requestor, שם יזם/אדריכל/עו"ד) ≥ 80%`
4. **Fallback** — first candidate

Added `thefuzz` + `python-Levenshtein` to `requirements.txt` (installed).

### 3. Complot scraper: added `migrash` and `applicant_name`

`_parse_bakasha_file` now also parses two new sections from the GetBakashaFile detail page:

- **בעלי עניין** table → `applicant_name` (the מבקש row)
- **גושים וחלקות** table → `migrash` (מספר מגרש column, first parcel row)

`_merge_permit` prefers `applicant_name` from the detail page over the list-page `requestor`
(the detail page has structured role types; the list page concatenates all names).
Both fields are exposed in the output schema and used by the matcher.

### 4. Matcher: 1-year cutoff for `new_permit` and `untracked`

`_is_recent(date_val, max_days=365)` added. Applied at flag decision time:
- `new_permit` — skipped if `request_date` > 365 days ago
- `untracked` — skipped if `request_date` > 365 days ago
- `status_advanced` — unaffected (a 2018 permit can still advance today)

### 5. Added 7 events to `_UNMAPPED_EVENTS` (Complot)

Admin/processing events that do not represent trackable milestones:
- `מסירת היתר`, `הכנת היתר טיוטא לחתימות בלבד` (pre-issuance)
- `תשלום אגרת בניה`, `חישוב אגרת בניה`, `אישור העברת בקשה לחישובי אגרות` (fee steps)
- `הוסר מסדר היום`, `החזרת תיק מסריקה` (scheduling/scanning admin)

Two more surfaced in scrape D after the code was reloaded — see immediate tasks.

### 6. Incremental scrape design + implementation

**Problem:** full scrape takes ~80 min (9,600 × `GetBakashaFile` calls at 0.5s each).
**Solution:** two-phase incremental run, ~10 min total.

**Phase A** — re-check known matched permits for `status_advanced`:
- `matcher.run()` now accepts `matched_cache_path` parameter
- After every run (full or incremental), saves `outputs/<city>_matched_cache.json`
  containing all permit numbers that matched a BO project (including unchanged rows)
- Incremental Phase A loads this cache, filters `bat_yam_fresh.xlsx` to matched rows,
  calls `GetBakashaFile` for each (~600 calls, ~5 min)

**Phase B** — catch new permits for `new_permit` / `untracked`:
- `ComplotPermitsAPI(b_params=[2025, 2026]).scrape()` → ~500-800 permits, ~5 min
- Excludes permit numbers already in Phase A cache

**New files:**
- `scrapers/complot/api_scraper.py` — `scrape_targeted(permit_records)` method
- `scripts/run_bat_yam_incremental.py` — full incremental runner with matcher call

**Full scrape** remains unchanged — run monthly to refresh the identity cache.
**Incremental** — intended for weekly runs once `bat_yam_matched_cache.json` exists.

### 7. Bat Yam scrape restarted (scrape D)

Four duplicate processes were running (PIDs 50604, 54892, 55484, 68280) — killed all.
Restarted with updated code (includes all session changes above):
- Log: `outputs/scrape_log_2026_06_28_D.txt`
- Started: ~15:46
- Expected completion: ~17:05

Note: `_UNMAPPED_EVENTS` update for 7 events was made after the restart — current process
still logs those as `[NEW EVENT]`. Next run will suppress them.

### 8. Holon scrape: COMPLETE

- Process finished, `outputs/holon_fresh.xlsx` saved 15:52 (1.9MB, 26,868 rows)
- Matcher not yet run

---

## What to do next session

### A. Wait for Bat Yam scrape D, then run matcher (bootstrap incremental cache)

```powershell
Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_2026_06_28_D.txt' -Tail 5
```

Once complete:
```python
from transform import matcher
matcher.run(
    'docs/bat_yam.xlsx',
    'outputs/bat_yam_fresh.xlsx',
    'בת ים',
    'outputs/bat_yam_report.xlsx',
    matched_cache_path='outputs/bat_yam_matched_cache.json',
)
```

### B. Run Holon matcher

```python
from transform import matcher
matcher.run(
    'docs/holon_28062026.xlsx',
    'outputs/holon_fresh.xlsx',
    'חולון',
    'outputs/holon_report.xlsx',
    excluded_categories=set(),
    matched_cache_path='outputs/holon_matched_cache.json',
)
```

### C. Classify `שובץ לישיבת ועדה` (Bartech)

"Scheduled for committee meeting" — appeared in Holon scrape, not yet mapped.
Add to `STATUS_MAP` in `scrapers/bartech/api_scraper.py` once confirmed.
Likely `בקשה להיתר` but do not assume.

### D. Add 2 new unmapped Complot events to `_UNMAPPED_EVENTS`

In `scrapers/complot/api_scraper.py`:
- `הפקת טופס 2` — Form 2 production (admin)
- `בדיקת שמאי פנימי להיטל השבחה` — internal appraiser check for betterment levy (admin)

### E. Review Bat Yam + Holon reports

- `new_permit` / `untracked`: only ≤ 1-year-old rows appear
- `status_advanced`: verify matched project ↔ permit pairings are correct
- Check `match_method` column — `gush_helka` vs `address`; any suspicious `address` matches?

### F. Validate incremental mode

After step A generates `bat_yam_matched_cache.json`, run incremental and compare report:
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
Start-Process `
  -FilePath 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  -ArgumentList 'c:\R_PROJECTS\Project_update_scraper\scripts\run_bat_yam_incremental.py' `
  -WorkingDirectory 'c:\R_PROJECTS\Project_update_scraper' `
  -RedirectStandardOutput 'c:\R_PROJECTS\Project_update_scraper\outputs\incremental_log.txt' `
  -RedirectStandardError  'c:\R_PROJECTS\Project_update_scraper\outputs\incremental_err.txt' `
  -NoNewWindow
```

---

## State of key files

| File | State |
|---|---|
| `scrapers/complot/api_scraper.py` | Updated — `migrash`, `applicant_name`, `scrape_targeted()`, 7 new unmapped events |
| `scrapers/bartech/api_scraper.py` | Unchanged — `שובץ לישיבת ועדה` still unclassified |
| `transform/matcher.py` | Updated — `_pick_best_candidate()`, `matched_cache_path`, 1-year cutoff |
| `scripts/run_bat_yam_incremental.py` | New — incremental runner |
| `scripts/run_bat_yam.py` | Unchanged (add `matched_cache_path` to next matcher call) |
| `requirements.txt` | Updated — `thefuzz`, `python-Levenshtein` |
| `outputs/bat_yam_fresh.xlsx` | **IN PROGRESS** — scrape D running, ~17:05 completion |
| `outputs/bat_yam_matched_cache.json` | **NOT YET GENERATED** — needs matcher run after D completes |
| `outputs/bat_yam_report.xlsx` | Stale — regenerate after D scrape |
| `outputs/holon_fresh.xlsx` | **COMPLETE** — 26,868 rows, saved 15:52 |
| `outputs/holon_report.xlsx` | Not yet generated |
| `docs/holon_28062026.xlsx` | Ready — 500 projects |
| `docs/bat_yam.xlsx` | Ready — 601 projects |
