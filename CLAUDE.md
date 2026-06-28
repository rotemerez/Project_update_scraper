# Project Update Scraper — CLAUDE.md

## What this is

A system that scrapes Israeli local planning committee websites (ועדות תכנון מקומיות) and feeds
permit/project data into the Madlan backoffice CMS at https://backofficeng.madlan.co.il.

The backoffice accepts projects with fields described in `docs/backoffice_fields.md`. Scraped
data must be transformed to match those fields before submission.

---

## Project Structure

```
/
├── CLAUDE.md                     ← this file
├── requirements.txt              ← Python deps — stays at root (pip convention)
├── .gitignore
│
├── scripts/                      ← runnable entry points (one per city/task)
│   └── run_bat_yam.py            ← run from project root: python scripts/run_bat_yam.py
│
├── scrapers/                     ← one module per municipality
│   └── <city_name>/
│       ├── scraper.py
│       └── parser.py
│
├── transform/                    ← raw scraped data → backoffice payload
│   ├── matcher.py
│   ├── gush_helka.py
│   ├── address_match.py
│   └── mapper.py
│
├── backoffice/                   ← API client for backofficeng.madlan.co.il
│   └── client.py
│
├── tests/
│
├── docs/
│   ├── NEXT_STEPS.md             ← live task tracker (READ THIS FIRST)
│   ├── backoffice_fields.md
│   ├── project_creation_norms.md
│   ├── ROADMAP.md
│   ├── DATA_FLOW.md
│   ├── BUG_REFERENCE.md
│   └── session_handoffs/         ← SESSION_HANDOFF_YYYY_MM_DD_X.md files
│
└── outputs/                      ← gitignored; all generated files go here
```

---

## File Placement Rules

**Keep the root clean.** Only `CLAUDE.md`, `requirements.txt`, and `.gitignore` belong at root.
Everything else goes in a named folder. When in doubt, use the rules below.

| File type | Where it goes | Examples |
|---|---|---|
| Runner / entry-point scripts | `scripts/` | `run_bat_yam.py`, `run_haifa.py` |
| Scraper modules | `scrapers/<city>/` | `scrapers/complot/api_scraper.py` |
| Matching / transform logic | `transform/` | `matcher.py`, `gush_helka.py` |
| Backoffice API client | `backoffice/` | `client.py` |
| Tests | `tests/` | `test_matcher.py` |
| Scrape outputs (Excel, JSON) | `outputs/` | `bat_yam_fresh.xlsx`, `bat_yam_report.xlsx` |
| Debug HTML snapshots | `outputs/` | `debug_api_permit_list_b2025.html` |
| Debug screenshots / PNGs | `outputs/` | `debug_download_*.png` |
| Reference docs, field specs | `docs/` | `backoffice_fields.md` |
| Session handoffs | `docs/session_handoffs/` | `SESSION_HANDOFF_2026_06_27_B.md` |
| Madlan project exports | `docs/` | `bat_yam.xlsx` |

**`repo/`** — gitignored reference copy of the prior `municipal-permit-scraper-main` codebase.
Keep it, don't modify it, don't add to it.

**Never create files at the root** other than the three listed above. If a script produces
output files, it must write them to `outputs/`. If you are writing a one-off diagnostic or
analysis script, put it in `scripts/`.

---

## Running Python Scripts

**Python executable:** `C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe`

Background tasks and subshells do not inherit the working directory, so `from scrapers...`
imports fail with `ModuleNotFoundError`. Always set `PYTHONPATH` explicitly:

```bash
# From Bash tool (foreground only — do NOT use & or run_in_background for scrapers):
PYTHONPATH=/c/R_PROJECTS/Project_update_scraper \
  /c/Users/Rotem/AppData/Local/Programs/Python/Python313/python.exe \
  scripts/run_bat_yam.py

# From PowerShell (foreground):
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\run_bat_yam.py
```

### Running Long Scrapers in the Background

Use `Start-Process` from PowerShell — the **only reliable method** for background scrapes.
Three requirements: `-WorkingDirectory`, absolute paths for log files, `-NoNewWindow`.

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
$env:PYTHONUTF8 = '1'
Start-Process `
  -FilePath 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' `
  -ArgumentList 'c:\R_PROJECTS\Project_update_scraper\scripts\run_bat_yam.py' `
  -WorkingDirectory 'c:\R_PROJECTS\Project_update_scraper' `
  -RedirectStandardOutput 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_CITY.txt' `
  -RedirectStandardError  'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_err_CITY.txt' `
  -NoNewWindow
```

Check progress with:
```powershell
Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_CITY.txt' -Tail 5
```

**What does NOT work — do not retry these:**
- Bash `& ` background (`python script.py &`) — process starts but log stays empty
- Bash `run_in_background=true` with `>` redirect — output goes to task file, not the log file
- PowerShell `Start-Job` — job IDs don't survive across separate PowerShell tool invocations
- `Start-Process` without `-WorkingDirectory` — script runs from wrong dir, silent failure

---

## Development Guidelines

### Windows Console Compatibility
Do not use Unicode symbols (✓, ✗, ❌, ►, ▼, etc.) in `print()` or `logging` output.
Use ASCII alternatives: `[OK]`, `[X]`, `->`, `[DONE]`, `[ERROR]`.

### Session Handoff Documents
Session handoff files live in `docs/session_handoffs/` and follow:
`SESSION_HANDOFF_YYYY_MM_DD_X.md` — where `X` is an ordered letter within the day (A, B, C, …).

Rules:
- **Never overwrite** an existing session handoff file
- Each session produces a new file with the next available letter for that day

### Coding Principles
- No fallbacks that hide real failures — surface errors explicitly
- Keep scrapers modular: one file per municipality, common interface
- Transform logic lives in `transform/`, not inside scrapers
- Full code on edits — never say "[X] remains unchanged"
- Think before writing: scraper logic, field mapping, and validation rules should be
  reasoned through before implementation

### Data Integrity — No Invented Values
**Never fabricate or infer field values that did not come from a real data source.**

If a field was not returned by the API or scraper, leave it empty. Do not:
- Default a status field to an assumed value (e.g. `scraped_status or 'בקשה להיתר'`)
- Fill in a date from a proxy field when the real date is missing
- Infer a value from context, naming, or "reasonable assumption"

A blank cell in the report is honest. A fabricated value is worse than no value — it will
be trusted and entered into the system as real data. If data is absent, surface the absence.

### Living Document — NEXT_STEPS.md
`docs/NEXT_STEPS.md` is the single source of truth for project status.
- Read it at the start of every session to orient quickly
- Update it at the end of every session: mark completed items as done, add newly discovered tasks
- It replaces needing to re-read session handoffs to understand current state

### Documentation Triggers
- **Any work done** → update `docs/NEXT_STEPS.md` (Done section + remaining tasks)
- **New scraper** → update `docs/ROADMAP.md` with covered municipality
- **Bug fixed** → add entry to `docs/BUG_REFERENCE.md` with root cause + fix
- **Field mapping change** → update `docs/backoffice_fields.md`
- **Architecture change** → update `docs/DATA_FLOW.md`

### Data Norms (from נוהל הקמת פרויקטים)
Key rules when mapping scraped data to backoffice fields:
- Project ID (`מזהה`): Hebrew address, underscores only, no spaces/special chars, always include city name
- Project name: marketing name + city, or address + city if no marketing name
- Developer: link to parent company (not project-specific subsidiary), verify in company registry
- Construction type (`סוג בניה`): תמ"א 38, בניה חדשה, פינוי בינוי, etc. — follow classification rules
- Minimum 3 units for new construction (4 for attached housing by same developer); תמ"א 38 has no minimum
- Build stage: בתכנון until permit issued; בניה until Form 4; הסתיים after Form 4
- Don't show suspended/rejected projects publicly — set hidden, don't delete
- Parcel (גוש/חלקה): required for transaction linkage; from govmap

**Excluded permit request categories (סוג הבקשה)** — these precede official permit submission
and must never be treated as real permit requests (source: נוהל הקמת פרויקטים מאי 2023):
- `בקשה מקדמית` — preliminary inquiry
- `בקשה עקרונית` — in-principle request
- `בקשה למידע` — information request
- `בקשה לתיאום מקדים` — early coordination request
- `תהליך ראשוני` — initial process (pre-submission)

**City exception**: In פתח תקווה and הרצליה, `בקשה מקדמית` requests advance directly into
a full permit request without being closed and reopened — do NOT exclude them for these cities.
Pass `excluded_categories=EXCLUDED_REQUEST_CATEGORIES - {'בקשה מקדמית'}` to `matcher.run()`.

**Trackable construction types (תיאור הבקשה substrings)**:
`בניה חדשה`, `הריסה ובניה`, `תמ"א 38`, `חיזוק ותוספת`, `פינוי בינוי`, `בינוי פינוי`,
`עיבוי בינוי`, `שימור`, `צמודי קרקע`, `תיקון 139`

**Project timeframe**: Track permit requests submitted up to 10 years ago that have not yet been
occupied. Auto-compute `min_year` from the earliest `תאריך בקשה להיתר` among in-progress
projects (without `תאריך קבלת טופס 4`) in the projects file.

---

## Tech Stack (planned)

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| HTTP / scraping | requests + BeautifulSoup / Playwright (JS-heavy sites) |
| Data validation | pydantic |
| Scheduling | cron / GitHub Actions |
| Output | JSON files + optional DB |
