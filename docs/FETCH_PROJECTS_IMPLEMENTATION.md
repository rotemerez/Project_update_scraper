# Implementing `scripts/fetch_projects.py`

## Context

This project scrapes Israeli municipal planning permit data and feeds it into the Madlan backoffice.
One required input is a "current projects" table that was previously exported manually from Looker.
The goal of this task is to automate that export using the Looker Python SDK.

**Read first:** `docs/NEXT_STEPS.md`, `CLAUDE.md`, and `docs/backoffice_fields.md` to orient yourself.
The existing projects file used as input is `docs/bat_yam.xlsx` — its column structure is what the
matcher expects.

---

## Task

Create `scripts/fetch_projects.py` — a script that authenticates with the Looker API, fetches the
full projects table from dashboard 724, and writes it to `outputs/madlan_projects_fresh.xlsx`. This
file will replace the manually exported `docs/bat_yam.xlsx` in the pipeline.

**Looker instance:** `https://localize.eu.looker.com`
**Dashboard ID:** `724`
**Target tile title:** `"Projects by each developer/architect/lawyer"` (tile index 2 in the dashboard)

---

## Auth

Use the Looker Python SDK (`looker-sdk` package). Credentials come from environment variables:
`LOOKER_BASE_URL`, `LOOKER_CLIENT_ID`, `LOOKER_CLIENT_SECRET`. Load them from a `.env` file using
`python-dotenv`. Do not hardcode credentials.

---

## How to Fetch

```python
import looker_sdk

sdk = looker_sdk.init40()

# Get the query ID from the dashboard tile
elements = sdk.dashboard_dashboard_elements("724")
tile = next(e for e in elements if e.title == "Projects by each developer/architect/lawyer")
query_id = tile.query_id

# Fetch all rows (no pagination needed — limit=-1 = "All results")
result = sdk.run_query(query_id=str(query_id), result_format="csv", limit=-1)
```

Then parse the CSV result into a pandas DataFrame and write to `outputs/madlan_projects_fresh.xlsx`.

---

## Known Fields Returned by This Tile

Use these to verify the output looks correct:

| Field | Description |
|---|---|
| `dwh_dim_properties.property_id` | Project ID (מזהה פרויקט) |
| `dwh_dim_properties.project_name` | Project name |
| `dwh_dim_properties.city` | City |
| `dwh_dim_properties.neighbourhood` | Neighbourhood |
| `dwh_dim_properties.project_status_heb` | Status (Hebrew) |
| `dwh_dim_properties.project_building_stage_heb` | Build stage (Hebrew) |
| `dwh_dim_properties.project_urban_renewal_type_heb` | Construction type (Hebrew) |
| `dwh_dim_properties.project_permit_request_date` | Permit request date |
| `dwh_dim_properties.project_permit_with_condition_date` | Permit with conditions date |
| `dwh_dim_properties.project_permit_date` | Permit date |
| `dwh_dim_properties.project_population_permit_request_date_date` | Tofes 4 date |
| `dwh_dim_properties.total_project_units` | Total units after |
| `dwh_dim_properties.total_project_units_before` | Total units before |
| `dwh_dim_project_locations.gush_helka` | Gush/Helka |
| `projects_by_each_dev_architect_lawyer.id` | Developer ID |
| `projects_by_each_dev_architect_lawyer.name` | Developer name |

---

## Output Verification

After writing the file, print:
- Row count
- Column names
- First 3 rows

---

## Error Handling

If the tile title is not found among the dashboard elements, print all available tile titles and
raise a descriptive error. Do not silently fall back to a different tile.

---

## `.env` File

Create `.env.example` at repo root and ensure `.env` is in `.gitignore`:

```
LOOKER_BASE_URL=https://localize.eu.looker.com
LOOKER_CLIENT_ID=your_client_id
LOOKER_CLIENT_SECRET=your_client_secret
```

The Looker SDK also supports a `looker.ini` config file as an alternative — check the SDK docs and
use whichever approach fits cleanest, but env vars are preferred.

---

## File Placement (per CLAUDE.md)

- Script: `scripts/fetch_projects.py`
- Output: `outputs/madlan_projects_fresh.xlsx`
- No files at repo root other than `CLAUDE.md`, `requirements.txt`, `.gitignore`

---

## After Implementing

1. Add `looker-sdk` and `python-dotenv` to `requirements.txt`
2. Update `docs/NEXT_STEPS.md` — mark this task done, note the output file path
3. Do **not** yet wire this into `run_bat_yam.py` — that is a separate step

---

## Running the Script

From repo root, per CLAUDE.md conventions:

```bash
PYTHONPATH=/c/R_PROJECTS/Project_update_scraper \
  /c/Users/Rotem/AppData/Local/Programs/Python/Python313/python.exe \
  scripts/fetch_projects.py
```
