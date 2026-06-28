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
- Minimum 3 units for new construction (4 for attached housing by same developer)
- Build stage: בתכנון until permit issued; בניה until Form 4; הסתיים after Form 4
- Don't show suspended/rejected projects publicly — set hidden, don't delete
- Parcel (גוש/חלקה): required for transaction linkage; from govmap

---

## Tech Stack (planned)

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| HTTP / scraping | requests + BeautifulSoup / Playwright (JS-heavy sites) |
| Data validation | pydantic |
| Scheduling | cron / GitHub Actions |
| Output | JSON files + optional DB |
