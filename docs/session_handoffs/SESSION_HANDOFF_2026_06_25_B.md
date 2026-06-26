# Session Handoff — 2026-06-25 B

## What was accomplished

### Relevance filter — applied to all use cases
- Read `docs/מידענות_ נוהל הקמת פרויקטים- מאי 2023.pdf` and extracted the
  official Madlan `סוג בניה` taxonomy (page 1 + page 13, section D)
- Updated `transform/matcher.py`:
  - Renamed `UC4_RELEVANT_TYPE_SUBSTRINGS` → `RELEVANT_TYPE_SUBSTRINGS`
  - Renamed `_is_relevant_for_uc4()` → `_is_relevant_type()`
  - Added missing type substrings: `בינוי פינוי`, `עיבוי בינוי`, `שימור`
  - Applied the filter to **UC1 and UC2** (previously only UC4 was filtered)
  - Minor-work permits (e.g. "הוספת גלריה") no longer leak through UC1

### Documentation
- Created `docs/NEXT_STEPS.md` — live task tracker (Done + what's next)
- Updated `CLAUDE.md` to reference `NEXT_STEPS.md` as the session-start document

---

## Current state of the codebase

All matching and relevance logic is in `transform/matcher.py`.  
`RELEVANT_TYPE_SUBSTRINGS` at the top of the file is the single list that gates
UC1, UC2, and UC4.

The scraper at `scrapers/complot/scraper.py` has two known gaps in `EVENT_TO_STATUS`:
- `היתר בתנאים` — Complot event text unknown
- `טופס 4` — Complot event text unknown

These can only be discovered by running a live scrape and inspecting raw event text.

---

## Immediate next steps

### 1. Run a live Bat Yam scrape
Bat Yam URL (from `repo/municipal-permit-scraper-main/tests/test_batyam_selenium.py`):
```
https://batyam.complot.co.il/iturbakashot/#search/GetBakashotByNumber&siteid=81&grp=0&t=0&b=2025&l=false&arguments=siteId,grp,t,b,l
```

Write a runner script (was about to be created when session ended):
```python
# run_bat_yam.py — at project root
from scrapers.complot.scraper import ComplotScraper
import pandas as pd, os

scraper = ComplotScraper(
    city_name_hebrew='בת ים',
    url='https://batyam.complot.co.il/iturbakashot/#search/GetBakashotByNumber&siteid=81&grp=0&t=0&b=2025&l=false&arguments=siteId,grp,t,b,l',
    headless=False,
)
scraper.max_requests = 20  # test mode first
permits = scraper.scrape()
df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_excel('outputs/bat_yam_fresh.xlsx', index=False)
print(df[['permit_status', 'permit_status_date', 'request_type']].to_string())
```

Run test mode first (20 permits) to verify the scraper works and to see raw
`permit_status` values. Then run full.

### 2. Discover missing EVENT_TO_STATUS mappings
After the scrape, inspect the printed output for:
- Any rows where `permit_status` is blank but the permit looks advanced
- Open one such permit in the browser, find its "אירועים" section, and read
  the exact `תיאור האירוע` text for היתר בתנאים / טופס 4 events

Add the discovered substrings to `EVENT_TO_STATUS` in `scrapers/complot/scraper.py`.

### 3. Re-run matcher against fresh data
```python
from transform import matcher
matcher.run(
    projects_path='docs/bat_yam.xlsx',
    permits_path='outputs/bat_yam_fresh.xlsx',
    city_hebrew='בת ים',
    output_path='outputs/bat_yam_report.xlsx',
)
```
UC2 results should now appear.

---

## Key file paths

| Path | Role |
|---|---|
| `scrapers/complot/scraper.py` | Scraper — `EVENT_TO_STATUS` dict at top |
| `transform/matcher.py` | Matching + report — `RELEVANT_TYPE_SUBSTRINGS` list |
| `docs/bat_yam.xlsx` | Madlan projects export (601 rows) |
| `outputs/bat_yam_fresh.xlsx` | Target for live scrape output (does not exist yet) |
| `outputs/bat_yam_report.xlsx` | Latest report (from stale data, UC2=0) |
| `docs/NEXT_STEPS.md` | Full backlog — read this at session start |

## Python
`/c/Users/Rotem/AppData/Local/Programs/Python/Python314/python.exe`  
Run from project root: `cd c:/R_PROJECTS/Project_update_scraper`
