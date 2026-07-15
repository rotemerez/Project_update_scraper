# Session Handoff — 2026-07-13 A

**Date:** 2026-07-13  
**Session:** M  
**Scope:** Looker projects export pipeline finalised; fetch_projects.py updated with column renaming and CSV mode

---

## What was accomplished

### 1. Looker projects export — pipeline complete

**Problem:** Looker SDK auth (`init40()`) fails with 404 on POST /login because the user's
Looker credentials are email/password login credentials, not API keys. API key access requires
admin action.

**Solution:** Claude Desktop Looker MCP can export the data directly. Workflow established:
1. In Claude Desktop: export dashboard 724 tile "Projects by each developer/architect/lawyer"
   as CSV to `outputs/madlan_projects_fresh.csv`
2. Here: run `scripts/fetch_projects.py --from-csv outputs/madlan_projects_fresh.csv`
   → produces `outputs/madlan_projects_fresh.xlsx` with Hebrew column names

**Verification:** 45,496 rows, 23,240 unique project IDs. City-by-city comparison against
`docs/all_projects_08072026.xlsx` (23,233 projects) showed perfect alignment — all cities
within 0–1 projects (7 net new projects since the old file). First export attempt returned
wrong tile (`sold_*` numeric IDs, fewer projects); second export after refined prompt returned
the correct data.

### 2. `scripts/fetch_projects.py` rewritten

- **`--from-csv <path>` mode:** reads a pre-exported CSV, renames 29 Looker dot-notation
  columns to Hebrew names the matcher expects, writes xlsx. This is the working path.
- **SDK mode (default):** still implemented for when API keys become available.
- **`COLUMN_RENAME` dict** maps all 29 Looker fields to Hebrew equivalents.
- **`low_memory=False`** added to suppress dtype warning on mixed-type column.

### Repeat workflow for future exports

In Claude Desktop, prompt:
> "Using the Looker MCP, fetch all rows from dashboard 724 at localize.eu.looker.com,
> tile 'Projects by each developer/architect/lawyer'. Save as CSV to
> c:\R_PROJECTS\Project_update_scraper\outputs\madlan_projects_fresh.csv"

Then here:
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\fetch_projects.py --from-csv outputs/madlan_projects_fresh.csv
```

---

## Open items

- **Report reviews** — kiryat_ata (59 manual_review), harel, zmora, mitzpe_afek, yishuvei_habaron with colleague
- **מורדות כרמל** — needs office IP
- **Hadera stage classification** — still pending colleague input
- **Looker API keys** — if admin grants API access, SDK mode in fetch_projects.py will work directly

---

## What to do next session

### Priority 1 — Review reports with colleague

| Committee | Report | Key figures |
|---|---|---|
| קרית אתא | `outputs/kiryat_ata_report.xlsx` | 14 status_advanced, 41 untracked, 59 manual_review |
| הראל | `outputs/harel_report.xlsx` | 5 status_advanced, 32 untracked |
| זמורה | `outputs/zmora_report.xlsx` | 7 status_advanced, 70 untracked |
| מיצפה אפק | `outputs/mitzpe_afek_report.xlsx` | 14 status_advanced, 33 untracked |
| ישובי הברון | `outputs/yishuvei_habaron_report.xlsx` | 2 status_advanced, 49 untracked |

### Priority 2 — Re-run matchers against fresh projects file (optional)

Now that `outputs/madlan_projects_fresh.xlsx` is available with up-to-date projects,
matchers can be re-run with this file instead of the per-city xlsx files. This would catch
any projects added since the old per-city exports. Update runner scripts to point to the
new file if desired.

---

## State of key files

| File | State |
|---|---|
| `scripts/fetch_projects.py` | Updated — `--from-csv` mode + full `COLUMN_RENAME` map |
| `outputs/madlan_projects_fresh.csv` | Complete — 45,496 rows from Looker MCP (2026-07-12) |
| `outputs/madlan_projects_fresh.xlsx` | Complete — 23,240 unique projects, Hebrew columns |
| `outputs/yishuvei_habaron_report.xlsx` | Complete — 2 status_advanced, 49 untracked |
| `scrapers/complot/api_scraper.py` | Updated — 7 new EVENT_TO_STATUS + ~80 _UNMAPPED_EVENTS |
