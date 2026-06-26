"""
Match scraped Complot permits against existing Madlan projects and produce a
flagged report for manual review.

Use cases:
  UC1 - Project exists with status "טרום בקשה" and a permit was found for it.
  UC2 - Project exists with a permit, and scraper found a newer status milestone.
  UC3 - Match found, status unchanged -> skip (not in output).
  UC4 - Scraped permit has no matching project -> flag as new project candidate.

Output columns:
  use_case | project_id | project_name | gush_helka | match_method
  | db_status | scraped_status | scraped_status_date
  | request_number | request_date | full_address | request_type
  | project_description | requestor
"""

import pandas as pd
from typing import Optional, Dict, List
from transform import gush_helka as gh
from transform import address_match as am


# Ordered milestone statuses (ascending progress)
STATUS_ORDER = ['בקשה להיתר', 'היתר בתנאים', 'היתר', 'טופס 4']

# Relevance filter: only flag permits whose request_type contains one of these substrings.
# Covers the construction types Madlan tracks (per נוהל הקמת פרויקטים מאי 2023).
# Minor work (room additions, renovations, permits-for-business, etc.) is excluded.
RELEVANT_TYPE_SUBSTRINGS = [
    'בניה חדשה',
    'הריסה ובניה',  # covers תמ"א 38/2 and non-תמ"א demolition+rebuild
    'פינוי בינוי',
    'בינוי פינוי',
    'עיבוי בינוי',
    'תמ"א 38',
    "תמ'א 38",      # alternate punctuation seen in some municipalities
    'תיקון 139',    # urban renewal programme
    'שימור',        # preservation projects (tracked when they add units)
]


def _is_relevant_type(request_type: str) -> bool:
    t = str(request_type or '').strip()
    return any(sub in t for sub in RELEVANT_TYPE_SUBSTRINGS)

# Normalize the projects DB "סטטוס פרויקט" values to our STATUS_ORDER vocabulary
DB_STATUS_NORM = {
    'טרום בקשה':    '',               # pre-request, not yet in STATUS_ORDER
    'בקשה להיתר':   'בקשה להיתר',
    'היתר בתנאים':  'היתר בתנאים',
    'היתר בניה':    'היתר',           # DB uses "היתר בניה", we call it "היתר"
    'היתר':         'היתר',
    'טופס 4':       'טופס 4',
}

# Columns in projects DF that hold milestone dates
STATUS_DATE_COLS = {
    'בקשה להיתר':  'תאריך בקשה להיתר',
    'היתר בתנאים': 'תאריך היתר בתנאים',
    'היתר':        'תאריך היתר',
    'טופס 4':      'תאריך קבלת טופס 4',
}


def _status_rank(status: str) -> int:
    try:
        return STATUS_ORDER.index(status)
    except ValueError:
        return -1


def _is_upgrade(db_status_norm: str, scraped_status: str) -> bool:
    """True if scraped_status is a higher milestone than db_status_norm."""
    if not scraped_status:
        return False
    scraped_rank = _status_rank(scraped_status)
    if scraped_rank < 0:
        return False
    db_rank = _status_rank(db_status_norm)
    return scraped_rank > db_rank


def _fmt_date(val) -> str:
    if pd.isna(val):
        return ''
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    return str(val).strip()


def run(
    projects_path: str,
    permits_path: str,
    city_hebrew: str,
    output_path: str,
) -> pd.DataFrame:
    """
    Load projects and permits files, run matching, write flagged report to output_path.
    Returns the report DataFrame.
    """
    projects_df = pd.read_excel(projects_path)
    permits_df = pd.read_excel(permits_path)

    # Normalise column names (strip whitespace)
    projects_df.columns = [c.strip() for c in projects_df.columns]
    permits_df.columns = [c.strip() for c in permits_df.columns]

    report_rows = []

    # Build a gush-helka index over projects:
    # { (gush, helka) -> list of project row indices }
    gh_index: Dict = {}
    for idx, row in projects_df.iterrows():
        for pair in gh.parse(row.get('גוש-חלקה', '')):
            gh_index.setdefault(pair, []).append(idx)

    matched_project_indices = set()  # projects that got matched to at least one permit

    for _, permit in permits_df.iterrows():
        permit_gh_pairs = gh.parse(permit.get('block_lot', ''))

        # --- Attempt match ---
        matched_idx: Optional[int] = None
        match_method = ''

        # 1. Gush-helka
        for pair in permit_gh_pairs:
            if pair in gh_index:
                matched_idx = gh_index[pair][0]  # take first if multiple (edge case)
                match_method = 'gush_helka'
                break

        # 2. Address fallback
        if matched_idx is None:
            for idx, proj_row in projects_df.iterrows():
                if am.match(proj_row.get('שם פרויקט', ''), permit.get('full_address', ''), city_hebrew):
                    matched_idx = idx
                    match_method = 'address'
                    break

        # --- Apply use-case logic ---
        if matched_idx is not None:
            proj = projects_df.loc[matched_idx]
            matched_project_indices.add(matched_idx)

            db_status_raw = str(proj.get('סטטוס פרויקט', '') or '').strip()
            db_status_norm = DB_STATUS_NORM.get(db_status_raw, '')

            scraped_status = str(permit.get('permit_status', '') or '').strip()
            scraped_date = str(permit.get('permit_status_date', '') or '').strip()

            if not _is_relevant_type(permit.get('request_type', '')):
                pass  # UC3: minor-work permit, irrelevant regardless of project status

            elif db_status_raw == 'טרום בקשה':
                # UC1: pre-request project, relevant permit now found
                report_rows.append(_make_row(
                    use_case='UC1',
                    proj=proj,
                    permit=permit,
                    match_method=match_method,
                    db_status=db_status_raw,
                    scraped_status=scraped_status or 'בקשה להיתר',
                    scraped_status_date=scraped_date or _fmt_date(permit.get('request_date')),
                ))

            elif _is_upgrade(db_status_norm, scraped_status):
                # UC2: status advanced since last check
                report_rows.append(_make_row(
                    use_case='UC2',
                    proj=proj,
                    permit=permit,
                    match_method=match_method,
                    db_status=db_status_raw,
                    scraped_status=scraped_status,
                    scraped_status_date=scraped_date,
                ))
            # else UC3: match found, no relevant change -> skip

        else:
            # UC4: no matching project found — only flag relevant permit types
            if not _is_relevant_type(permit.get('request_type', '')):
                continue
            scraped_status = str(permit.get('permit_status', '') or '').strip()
            scraped_date = str(permit.get('permit_status_date', '') or '').strip()
            report_rows.append(_make_row(
                use_case='UC4',
                proj=None,
                permit=permit,
                match_method='',
                db_status='',
                scraped_status=scraped_status or 'בקשה להיתר',
                scraped_status_date=scraped_date or _fmt_date(permit.get('request_date')),
            ))

    report_df = pd.DataFrame(report_rows)
    if not report_df.empty:
        report_df.to_excel(output_path, index=False)
        print(f'[OK] Report written to {output_path} ({len(report_df)} rows)')
    else:
        print('[OK] No flagged items found.')

    _print_summary(report_df)
    return report_df


def _make_row(
    use_case: str,
    proj,
    permit: pd.Series,
    match_method: str,
    db_status: str,
    scraped_status: str,
    scraped_status_date: str,
) -> dict:
    return {
        'use_case':           use_case,
        'project_id':         str(proj['מזהה פרויקט']) if proj is not None else '',
        'project_name':       str(proj['שם פרויקט']) if proj is not None else '',
        'project_gush_helka': str(proj['גוש-חלקה']) if proj is not None else '',
        'match_method':       match_method,
        'db_status':          db_status,
        'scraped_status':     scraped_status,
        'scraped_status_date': scraped_status_date,
        'request_number':     str(permit.get('request_number', '')),
        'request_date':       _fmt_date(permit.get('request_date')),
        'full_address':       str(permit.get('full_address', '')),
        'request_type':       str(permit.get('request_type', '')),
        'project_description': str(permit.get('project_description', '')),
        'requestor':          str(permit.get('requestor', '')),
        'permit_block_lot':   str(permit.get('block_lot', '')),
    }


def _print_summary(df: pd.DataFrame):
    if df.empty:
        return
    counts = df['use_case'].value_counts()
    print('[Summary]')
    for uc in ['UC1', 'UC2', 'UC4']:
        print(f'  {uc}: {counts.get(uc, 0)}')
