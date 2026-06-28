"""
Match scraped Complot permits against existing Madlan projects and produce a
flagged report for manual review.

Row types in the output:
  new_permit      - We track this project as pre-request; a real permit now exists for it.
  status_advanced - We track this project with a permit; scraper found a newer milestone.
  unchanged       - Match found, status not newer -> silently skipped (not in output).
  untracked       - Permit exists in Complot but no matching project in Madlan at all.

Output columns:
  flag | project_id | project_name | project_sug_bnia | gush_helka | match_method
  | db_status | scraped_status | scraped_status_date | type_confirmed
  | request_number | request_date | request_category | full_address | request_type
  | requestor
"""

import pandas as pd
from typing import Optional, Dict, List
from transform import gush_helka as gh
from transform import address_match as am

# Permit categories (סוג הבקשה) that are not real permit requests and must be excluded.
# Source: נוהל הקמת פרויקטים מאי 2023 — these types precede the official request submission
# and do not represent a real permit request submitted to the municipality.
EXCLUDED_REQUEST_CATEGORIES = {
    'בקשה מקדמית',          # preliminary inquiry
    'בקשה עקרונית',         # in-principle request
    'בקשה למידע',           # information request only
    'בקשה לתיאום מקדים',   # early coordination request
    'תהליך ראשוני',         # initial process (pre-submission)
}


# Ordered milestone statuses (ascending progress)
STATUS_ORDER = ['בקשה להיתר', 'היתר בתנאים', 'היתר', 'טופס 4']

# Relevance filter: only flag permits whose request_type contains one of these substrings.
# Covers the construction types Madlan tracks (per נוהל הקמת פרויקטים מאי 2023).
# Minor work (room additions, renovations, permits-for-business, etc.) is excluded.
RELEVANT_TYPE_SUBSTRINGS = [
    'בניה חדשה',
    'הריסה ובניה',    # covers תמ"א 38/2 and non-תמ"א demolition+rebuild
    'פינוי בינוי',
    'בינוי פינוי',
    'עיבוי בינוי',
    'תמ"א 38',
    "תמ'א 38",        # alternate punctuation seen in some municipalities
    'חיזוק ותוספת',  # תמ"א 38/1 -- may appear without the תמ"א prefix in תיאור הבקשה
    'תיקון 139',      # urban renewal programme
    'שימור',          # preservation projects (tracked when they add units)
    'צמודי קרקע',    # attached housing -- 4+ units by same developer
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


def _clean(val) -> str:
    """Return val as a stripped string; NaN / None / the string 'nan' all become ''."""
    if val is None:
        return ''
    if isinstance(val, float) and pd.isna(val):
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


def _fmt_date(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ''
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s


def _year_of(val) -> int:
    """Return the year from a date value, or 0 if unparseable."""
    if hasattr(val, 'year'):
        return val.year
    s = _clean(val)
    if not s:
        return 0
    for fmt in ('%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(s[:10], fmt[:8] if len(fmt) > 8 else fmt).year
        except ValueError:
            continue
    return 0


def _compute_min_year(projects_df: pd.DataFrame) -> Optional[int]:
    """
    Return the year of the earliest permit request among in-progress projects
    (those without a Form 4 date). Used as the lower cutoff for scraped permits.
    Returns None if the required columns are absent or no qualifying rows exist.
    """
    req_col  = 'תאריך בקשה להיתר'
    form4_col = 'תאריך קבלת טופס 4'
    if req_col not in projects_df.columns or form4_col not in projects_df.columns:
        return None
    in_progress = projects_df[projects_df[form4_col].isna()]
    dates = in_progress[req_col].dropna()
    if dates.empty:
        return None
    years = dates.apply(_year_of)
    valid = years[years > 0]
    return int(valid.min()) if not valid.empty else None


def run(
    projects_path: str,
    permits_path: str,
    city_hebrew: str,
    output_path: str,
    min_year: Optional[int] = None,
) -> pd.DataFrame:
    """
    Load projects and permits files, run matching, write flagged report to output_path.

    min_year: if set, permits with request_date year < min_year are excluded.
    Returns the report DataFrame.
    """
    projects_df = pd.read_excel(projects_path)
    permits_df = pd.read_excel(permits_path)

    # Normalise column names (strip whitespace)
    projects_df.columns = [c.strip() for c in projects_df.columns]
    permits_df.columns = [c.strip() for c in permits_df.columns]

    # Auto-compute min_year from projects file if not explicitly provided
    if min_year is None:
        min_year = _compute_min_year(projects_df)
        if min_year:
            print(f'[INFO] Auto-computed min_year={min_year} from projects file')

    # Year cutoff filter
    if min_year is not None:
        before = len(permits_df)
        permits_df = permits_df[permits_df['request_date'].apply(
            lambda v: _year_of(v) >= min_year
        )]
        print(f'[INFO] min_year={min_year}: {before} -> {len(permits_df)} permits')

    # Excluded request categories (e.g. בקשה מקדמית)
    if 'request_category' in permits_df.columns:
        before = len(permits_df)
        permits_df = permits_df[~permits_df['request_category'].apply(
            lambda v: _clean(v) in EXCLUDED_REQUEST_CATEGORIES
        )]
        excluded = before - len(permits_df)
        if excluded:
            print(f'[INFO] Excluded {excluded} permits by request_category filter')

    report_rows = []

    # Build a gush-helka index over projects:
    # { (gush, helka) -> list of project row indices }
    gh_index: Dict = {}
    for idx, row in projects_df.iterrows():
        for pair in gh.parse(row.get('גוש-חלקה', '')):
            gh_index.setdefault(pair, []).append(idx)

    for _, permit in permits_df.iterrows():
        permit_gh_pairs = gh.parse(permit.get('block_lot', ''))

        # --- Attempt match ---
        matched_idx: Optional[int] = None
        match_method = ''

        # 1. Gush-helka
        for pair in permit_gh_pairs:
            if pair in gh_index:
                matched_idx = gh_index[pair][0]
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

            db_status_raw = str(proj.get('סטטוס פרויקט', '') or '').strip()
            db_status_norm = DB_STATUS_NORM.get(db_status_raw, '')

            scraped_status = _clean(permit.get('permit_status', ''))
            scraped_date   = _clean(permit.get('permit_status_date', ''))
            request_type   = _clean(permit.get('request_type', ''))
            type_known     = bool(request_type)
            type_relevant  = _is_relevant_type(request_type)

            if db_status_raw == 'טרום בקשה' and (type_relevant or not type_known):
                report_rows.append(_make_row(
                    flag='new_permit',
                    proj=proj,
                    permit=permit,
                    match_method=match_method,
                    db_status=db_status_raw,
                    scraped_status=scraped_status,
                    scraped_status_date=scraped_date,
                    type_confirmed=type_known,
                ))

            elif _is_upgrade(db_status_norm, scraped_status):
                report_rows.append(_make_row(
                    flag='status_advanced',
                    proj=proj,
                    permit=permit,
                    match_method=match_method,
                    db_status=db_status_raw,
                    scraped_status=scraped_status,
                    scraped_status_date=scraped_date,
                    type_confirmed=True,   # project already known relevant
                ))
            # else unchanged: match found, nothing new -> skip

        else:
            # No matching project -- only flag permits with a confirmed relevant type
            if not _is_relevant_type(_clean(permit.get('request_type', ''))):
                continue
            scraped_status = _clean(permit.get('permit_status', ''))
            scraped_date   = _clean(permit.get('permit_status_date', ''))
            report_rows.append(_make_row(
                flag='untracked',
                proj=None,
                permit=permit,
                match_method='',
                db_status='',
                scraped_status=scraped_status,
                scraped_status_date=scraped_date,
                type_confirmed=True,   # type_relevant was required to reach here
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
    flag: str,
    proj,
    permit: pd.Series,
    match_method: str,
    db_status: str,
    scraped_status: str,
    scraped_status_date: str,
    type_confirmed: bool = False,
) -> dict:
    return {
        'flag':               flag,
        'project_id':         str(proj['מזהה פרויקט']) if proj is not None else '',
        'project_name':       str(proj['שם פרויקט']) if proj is not None else '',
        'project_sug_bnia':   _clean(proj.get('סוג בנייה', '')) if proj is not None else '',
        'project_gush_helka': str(proj['גוש-חלקה']) if proj is not None else '',
        'match_method':       match_method,
        'db_status':          db_status,
        'scraped_status':     scraped_status,
        'scraped_status_date': scraped_status_date,
        'type_confirmed':     type_confirmed,
        'request_number':     str(permit.get('request_number', '')),
        'request_date':       _fmt_date(permit.get('request_date')),
        'request_category':   _clean(permit.get('request_category', '')),
        'full_address':       str(permit.get('full_address', '')),
        'request_type':       _clean(permit.get('request_type', '')),
        'requestor':          _clean(permit.get('requestor', '')),
        'permit_block_lot':   _clean(permit.get('block_lot', '')),
    }


def _print_summary(df: pd.DataFrame):
    if df.empty:
        return
    counts = df['flag'].value_counts()
    print('[Summary]')
    for flag in ['new_permit', 'status_advanced', 'untracked']:
        print(f'  {flag}: {counts.get(flag, 0)}')
