# Session Handoff — 2026-06-25 A

## What was accomplished

### Project setup
- Read existing repo at `repo/municipal-permit-scraper-main/` (extracted from zip)
- Created `CLAUDE.md` with project conventions and data norms
- Created all project folders per the structure in `CLAUDE.md`:
  `docs/session_handoffs/`, `scrapers/`, `transform/`, `backoffice/`, `tests/`, `outputs/`

### Scope decision
V1 goal is **a report for manual review only**, no automatic backoffice updates yet.  
Two scenarios:
1. Check for permit updates to existing Madlan projects
2. Flag new permit requests not yet in the database

### Files created this session

| File | Purpose |
|---|---|
| `requirements.txt` | `undetected-chromedriver`, `selenium`, `pandas`, `openpyxl` |
| `scrapers/complot/scraper.py` | Selenium scraper adapted from repo; adds `_extract_permit_status()` |
| `transform/gush_helka.py` | Parse + set-intersect gush-helka from either separator style |
| `transform/address_match.py` | Street+number normalization, range membership match |
| `transform/matcher.py` | Orchestrates matching, applies 4 use cases, writes report Excel |

### Reference data
- **`docs/bat_yam.xlsx`** — 601 Bat Yam projects from Madlan backoffice (provided by user)
- **`repo/.../results/bat_yam_results.xlsx`** — 390 Bat Yam permits scraped previously (no `permit_status` field, predates this session's scraper)

---

## Current matching logic

### Matching keys
1. **Gush-helka** (primary, 93% coverage): set-intersection of `(gush, helka)` tuples
2. **Address** (fallback): strip city, extract street + number, require both sides have a number, check if scraped number falls within project's number range

### Four use cases
| ID | Condition | Action |
|---|---|---|
| UC1 | Project `סטטוס פרויקט = טרום בקשה`, permit match found | Flag: pre-request now has permit |
| UC2 | Match found, scraped `permit_status` is higher milestone than DB status | Flag: status upgrade |
| UC3 | Match found, same status | Skip |
| UC4 | No matching project, `request_type` is relevant construction type | Flag: new project candidate |

### Status milestone order
`בקשה להיתר` < `היתר בתנאים` < `היתר` < `טופס 4`

### Complot events → status mapping (from screenshot provided by user)
| Complot `תיאור האירוע` substring | Our status |
|---|---|
| `פתיחת בקשה` | `בקשה להיתר` |
| `מתן היתר למבקש` | `היתר` |
| `היתר בתנאים` equivalent | **unknown — to be investigated** |
| `טופס 4` equivalent | **unknown — to be investigated** |

Mapping lives in `scrapers/complot/scraper.py` at `EVENT_TO_STATUS` dict — add entries there.

### Current UC4 filter (request_type substrings)
```python
UC4_RELEVANT_TYPE_SUBSTRINGS = [
    'בניה חדשה',
    'פינוי בינוי',
    'תמ"א 38',
    "תמ'א 38",
    'תיקון 139',
    'הריסה ובנייה',
]
```

### Test run results (existing data, no live scrape)
- Input: `docs/bat_yam.xlsx` (601 projects) vs `repo/.../bat_yam_results.xlsx` (390 permits)
- Output: `outputs/bat_yam_report.xlsx` — **85 rows** (UC1: 23, UC2: 0, UC4: 62)
- UC2 = 0 because the existing scraped file predates the `permit_status` field

---

## Known issues / next steps

### IMMEDIATE — First thing next session

**1. Read `docs/מידענות_ נוהל הקמת פרויקטים- מאי 2023.pdf` section "סוג פרויקט"**
The PDF is in `docs/`. Use pdfminer (already installed) with line-reversal to read Hebrew:
```python
from pdfminer.high_level import extract_text
text = extract_text('docs/מידענות_ נוהל הקמת פרויקטים- מאי 2023.pdf')
lines = text.split('\n')
for line in lines:
    print(line.strip()[::-1])  # reverse each line for RTL
```
Goal: extract the **exact list of `סוג בניה` values** that Madlan tracks, then replace the
`UC4_RELEVANT_TYPE_SUBSTRINGS` list in `transform/matcher.py` **and** apply the same filter to
UC1 (currently UC1 has no type filter — minor-work permits like "הוספת גלריה" and "חדר על הגג"
are leaking through even though we found a gush-helka match on a pre-request project).

**2. Apply the same relevant-types filter to UC1**
In `transform/matcher.py`, the UC1 block currently appends every match regardless of
`request_type`. Add the same `_is_relevant_for_uc4()` check (rename it to
`_is_relevant_type()`) before appending a UC1 row.

### THEN — Run a live scrape for Bat Yam
The Bat Yam scraper hasn't been run in this project yet. The report above used stale data
without `permit_status`. Steps:
1. Find Bat Yam's Complot URL (check `repo/data/complot_cities.csv`)
2. Run `scrapers/complot/scraper.py` on it
3. Save output to `outputs/bat_yam_fresh.xlsx` (or `.json`)
4. Re-run matcher against the fresh data — UC2 results should now appear

### LATER
- Add `היתר בתנאים` and `טופס 4` Complot event text mappings once discovered on a live page
- Extend to additional cities beyond Bat Yam
- Investigate whether the backoffice projects export can be automated (instead of manually
  exporting `bat_yam.xlsx` per city)

---

## Key file paths

| Path | Description |
|---|---|
| `scrapers/complot/scraper.py` | Production Complot scraper — `EVENT_TO_STATUS` dict at top |
| `transform/matcher.py` | `UC4_RELEVANT_TYPE_SUBSTRINGS` list + `_is_relevant_for_uc4()` function |
| `transform/gush_helka.py` | `parse()` and `match()` |
| `transform/address_match.py` | `match(project_name, scraped_address, city)` |
| `docs/bat_yam.xlsx` | Madlan projects export for Bat Yam (601 rows, 31 cols) |
| `outputs/bat_yam_report.xlsx` | Latest report output |
| `repo/municipal-permit-scraper-main/` | Original scraper repo — reference only, do not modify |

## Python
`/c/Users/Rotem/AppData/Local/Programs/Python/Python314/python.exe`  
Run from project root: `cd c:/R_PROJECTS/Project_update_scraper`
