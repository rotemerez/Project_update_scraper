"""
Fetch the Madlan projects table from Looker dashboard 724 and write to Excel.

Two modes:
  1. SDK mode (default): authenticates via Looker API, fetches live.
     Requires .env with LOOKER_BASE_URL / CLIENT_ID / CLIENT_SECRET.
  2. CSV mode (--from-csv <path>): converts a pre-exported CSV (e.g. from
     Claude Desktop Looker MCP) to the same Excel format without API access.

Output columns are renamed from Looker dot-notation to the Hebrew column names
the matcher expects.
"""

import io
import os
import sys

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

OUTPUT_PATH = "outputs/madlan_projects_fresh.xlsx"
DASHBOARD_ID = "724"
TILE_TITLE = "Projects by each developer/architect/lawyer"

# Looker field name → Hebrew column name used by matcher
COLUMN_RENAME = {
    'dwh_dim_neighbourhoods.tlv_neighbourhood_rova':              'רובע (ת"א)',
    'dwh_dim_project_lands.taba_migrash':                         'תבע+מגרש',
    'dwh_dim_project_locations.gush_helka':                       'גוש-חלקה',
    'dwh_dim_properties.city':                                    'עיר',
    'dwh_dim_properties.neighbourhood':                           'שכונה',
    'dwh_dim_properties.project_building_stage_heb':              'שלב בנייה',
    'dwh_dim_properties.project_building_utility':                'שימושי בניין',
    'dwh_dim_properties.project_local_taba_acceptance_date':      'תב"ע - תאריך קבלת תוקף',
    'dwh_dim_properties.project_local_taba_objection_publication_date': 'תב"ע - תאריך פרסום להתנגדויות',
    'dwh_dim_properties.project_name':                            'שם פרויקט',
    'dwh_dim_properties.project_permit_date':                     'תאריך היתר',
    'dwh_dim_properties.project_permit_request_date':             'תאריך בקשה להיתר',
    'dwh_dim_properties.project_permit_with_condition_date':      'תאריך היתר בתנאים',
    'dwh_dim_properties.project_population_permit_request_date_date': 'תאריך קבלת טופס 4',
    'dwh_dim_properties.project_status_heb':                      'סטטוס פרויקט',
    'dwh_dim_properties.project_urban_renewal_type_heb':          'סוג בנייה',
    'dwh_dim_properties.property_id':                             'מזהה פרויקט',
    'dwh_dim_properties.property_usage_type':                     'סוג פרויקט',
    'dwh_dim_properties.total_project_buildings':                 'מספר בניינים',
    'dwh_dim_properties.total_project_buildings_before':          'מס. בניינים לפני',
    'dwh_dim_properties.total_project_units':                     'מספר יחידות',
    'dwh_dim_properties.total_project_units_before':              'מס. יחידות לפני',
    'dwh_dim_properties.total_project_units_netto':               'תוספת דירות',
    'projects_by_each_dev_architect_lawyer.id':                   'מזהה יזם/אדריכל/עו"ד',
    'projects_by_each_dev_architect_lawyer.name':                 'שם יזם/אדריכל/עו"ד',
    'projects_by_each_dev_architect_lawyer.partners':             'פרטנרים',
    'projects_by_each_dev_architect_lawyer.previous_buildings_number': 'עו"ד - מס. בניינים לפני',
    'projects_by_each_dev_architect_lawyer.previous_units_number': 'עו"ד - מס. יחידות לפני',
    'projects_by_each_dev_architect_lawyer.units_number':         'עו"ד - מספר יחידות',
}


def _rename_and_write(df: pd.DataFrame) -> None:
    df = df.rename(columns=COLUMN_RENAME)
    unknown = [c for c in df.columns if c not in COLUMN_RENAME.values()]
    if unknown:
        print(f"[WARN] Unmapped columns (kept as-is): {unknown}")
    unique = df['מזהה פרויקט'].nunique() if 'מזהה פרויקט' in df.columns else '?'
    print(f"[OK] {len(df)} rows, {unique} unique project IDs")
    df.to_excel(OUTPUT_PATH, index=False)
    print(f"[DONE] Written to {OUTPUT_PATH}")


def from_csv(path: str) -> None:
    print(f"[CSV mode] Reading {path}...")
    df = pd.read_csv(path, low_memory=False)
    print(f"[OK] {len(df)} rows, {len(df.columns)} columns")
    _rename_and_write(df)


def from_sdk() -> None:
    for _key in ("BASE_URL", "CLIENT_ID", "CLIENT_SECRET"):
        _val = os.environ.get(f"LOOKER_{_key}")
        if _val:
            os.environ[f"LOOKERSDK_{_key}"] = _val

    import looker_sdk  # noqa: E402

    missing = [k for k in ("LOOKER_BASE_URL", "LOOKER_CLIENT_ID", "LOOKER_CLIENT_SECRET")
               if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {missing}. Add them to .env")

    sdk = looker_sdk.init40()
    print(f"[OK] Authenticated — fetching dashboard {DASHBOARD_ID} elements...")
    elements = sdk.dashboard_dashboard_elements(DASHBOARD_ID)

    tile = next((e for e in elements if e.title == TILE_TITLE), None)
    if tile is None:
        available = [e.title for e in elements]
        print("[ERROR] Available tile titles:")
        for t in available:
            print(f"  - {t!r}")
        raise ValueError(f"Tile '{TILE_TITLE}' not found in dashboard {DASHBOARD_ID}")

    print(f"[OK] Tile found — query_id={tile.query_id}")
    print("[...] Running query (limit=-1 = all rows)...")
    result = sdk.run_query(query_id=str(tile.query_id), result_format="csv", limit=-1)
    if isinstance(result, bytes):
        result = result.decode("utf-8")

    df = pd.read_csv(io.StringIO(result))
    _rename_and_write(df)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--from-csv":
        from_csv(sys.argv[2])
    else:
        from_sdk()
