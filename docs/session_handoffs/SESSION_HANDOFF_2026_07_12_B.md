# Session Handoff — 2026-07-12 B

**Date:** 2026-07-12  
**Session:** L  
**Scope:** Looker fetch_projects.py implemented; ישובי הברון matcher run; Complot scraper updated with 87 new event mappings

---

## What was accomplished

### 1. `scripts/fetch_projects.py` — Looker SDK export (Priority 1)

Implemented the Looker API export script per `docs/FETCH_PROJECTS_IMPLEMENTATION.md`:

- **Auth:** loads `LOOKER_BASE_URL`, `LOOKER_CLIENT_ID`, `LOOKER_CLIENT_SECRET` from `.env` via
  `python-dotenv`, maps them to `LOOKERSDK_*` prefix before calling `looker_sdk.init40()`
- **Fetch:** `sdk.dashboard_dashboard_elements("724")` → finds tile by title → `sdk.run_query(..., result_format="csv", limit=-1)`
- **Output:** `outputs/madlan_projects_fresh.xlsx`
- **Error handling:** if tile not found, prints all available titles and raises a descriptive error

Both `looker-sdk` (26.10.0) and `python-dotenv` (1.2.2) were already installed on the system.
Added both to `requirements.txt`. Created `.env.example` at repo root.

**Status:** Script is ready. Needs `.env` file with real credentials to run.

### 2. ישובי הברון matcher — complete (Priority 2)

Scrape had finished at 11:40:38 (9,737 permits, all 4 cities). Matcher ran against
`docs/all_projects_08072026.xlsx` with `city_filter=['זכרון יעקב', 'אור עקיבא', 'בנימינה גבעת עדה', "ג'סר א זרקא"]`.

```
outputs/yishuvei_habaron_report.xlsx     — 51 rows (2 status_advanced, 49 untracked, 0 manual_review)
outputs/yishuvei_habaron_matched_cache.json — 455 permits
```

Auto-computed `min_year=2015`. After filtering: 6842 permits (by date) → 5354 (by first_event_date) → 2 dropped (ניסיון).

### 3. Complot api_scraper.py — 87 new event entries

From the full yishuvei_habaron scrape (9737 permits × 2011–2026):

**EVENT_TO_STATUS additions (7 entries):**
- `'תעודת גמר'` → `'טופס 4'` (standalone completion certificate)
- `'הפקת טופס 4 מותלה'` → `'טופס 4'` (conditional Form 4 issued)
- `'הפקת טופס 4 להרצת מערכות'` → `'טופס 4'` (partial match for system-testing Form 4 variant)
- `'הפקת טופס נלווה לטופס 4'` → `'טופס 4'` (supplementary Form 4 form — implies Form 4 issued)
- `'חתימת היתר בניה'` → `'היתר'` (building permit signed)
- `'הפקת אישור תחילת עבודות'` → `'היתר'` (construction start approval issued)
- `'אישור המפקך לתחילת עבודות'` → `'היתר'` (inspector approved start)

**_UNMAPPED_EVENTS additions (~80 entries):** admin/routing/inspection/financial steps —
all ישובי הברון specific events that don't represent trackable milestones.

---

## Open items

- **Looker credentials** — user needs to create `.env` file before running `fetch_projects.py`
- **Report reviews** — kiryat_ata (59 manual_review), harel, zmora, mitzpe_afek, yishuvei_habaron with colleague
- **מורדות כרמל** — needs office IP
- **Hadera stage classification** — still pending colleague input

---

## What to do next session

### Priority 1 — Run Looker projects export

Create `.env`:
```
LOOKER_BASE_URL=https://localize.eu.looker.com
LOOKER_CLIENT_ID=<your_client_id>
LOOKER_CLIENT_SECRET=<your_client_secret>
```
Then run:
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\fetch_projects.py
```

### Priority 2 — Review reports with colleague

| Committee | Report | Key figures |
|---|---|---|
| קרית אתא | `outputs/kiryat_ata_report.xlsx` | 14 status_advanced, 41 untracked, 59 manual_review |
| הראל | `outputs/harel_report.xlsx` | 5 status_advanced, 32 untracked |
| זמורה | `outputs/zmora_report.xlsx` | 7 status_advanced, 70 untracked |
| מיצפה אפק | `outputs/mitzpe_afek_report.xlsx` | 14 status_advanced, 33 untracked |
| ישובי הברון | `outputs/yishuvei_habaron_report.xlsx` | 2 status_advanced, 49 untracked |

---

## State of key files

| File | State |
|---|---|
| `scripts/fetch_projects.py` | New — Looker SDK export; needs `.env` credentials to run |
| `.env.example` | New — template at repo root |
| `requirements.txt` | Updated — `looker-sdk` + `python-dotenv` added |
| `scrapers/complot/api_scraper.py` | Updated — 7 new EVENT_TO_STATUS + ~80 new _UNMAPPED_EVENTS from yishuvei_habaron |
| `outputs/yishuvei_habaron_report.xlsx` | Complete — 2 status_advanced, 49 untracked |
| `outputs/yishuvei_habaron_matched_cache.json` | Complete — 455 permits |
| `outputs/yishuvei_habaron_fresh.csv` | Complete — 9737 permits (2026-07-12 11:40) |
