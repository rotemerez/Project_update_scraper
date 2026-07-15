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

import re
from datetime import datetime, timedelta
import pandas as pd
from typing import Optional, Dict, List
from transform import gush_helka as gh
from transform import address_match as am

try:
    from thefuzz import fuzz as _fuzz
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False

_BO_DEVELOPER_COL   = 'שם יזם/אדריכל/עו"ד'
_BO_MIGRASH_COL     = 'תבע+מגרש'
_FUZZY_THRESHOLD    = 80
_NEW_REQUEST_CUTOFF = 365  # days: new_permit / untracked rows older than this are dropped

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
    'בנייה חדשה',     # alternate spelling (double-yod) seen in Hadera Bartech
    'הריסה ובניה',    # covers תמ"א 38/2 and non-תמ"א demolition+rebuild
    'הריסה ובנייה',   # double-yod variant
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


# Uses that indicate public/institutional buildings Madlan does not track.
# Source: נוהל הקמת פרויקטים — "מבני ציבור (גני ילדים, בתי כנסת...) - לא נתייחס"
# Checked against shimush_ikari first; falls back to bakasha_description keyword scan.
_PUBLIC_USE_PATTERNS = [
    'מבנה ציבור', 'מבנה טכני', 'מוסד חינוכי', 'מוסדות חינוך', 'בית ספר', "בי\"ס",
    'גן ילדים', 'בית כנסת', 'בית כנסיה', 'כנסיה', 'מסגד', 'מדרשה',
    'אולם ספורט', 'בריכה', 'בית חולים', 'מרפאה',
    'בית עלמין', 'תחנת דלק', 'בנין ציבורי',
    'תחנת טרנספורמציה', 'תעשיה', 'תשתיות', 'שונות',
]


def _is_public_use(permit: pd.Series) -> bool:
    """
    True if shimush_ikari or bakasha_description indicates a public/institutional
    building that is not tracked as a Madlan project per נוהל הקמת פרויקטים.
    shimush_ikari (added to Complot scraper output) takes priority when present.
    bakasha_description fallback only matches very clear primary-use indicators.
    """
    shimush = _clean(permit.get('shimush_ikari', ''))
    if shimush and any(pat in shimush for pat in _PUBLIC_USE_PATTERNS):
        return True
    bakasha = _clean(permit.get('bakasha_description', ''))
    if bakasha and any(pat in bakasha for pat in _PUBLIC_USE_PATTERNS):
        return True
    return False


def _extract_unit_count(text: str) -> Optional[int]:
    """
    Try to extract the explicitly stated residential unit count from free Hebrew text.
    Returns None if no clear count can be found (permits it through; don't over-filter).
    """
    t = str(text or '')
    # Digit patterns: "3 יח\"ד", "3 יח'ד", "3 יחידות דיור", "3 דירות"
    for pattern in [
        r'(\d+)\s*יח["ד״]?["ד]',   # יח"ד variants
        r'(\d+)\s*יחידות\s*דיור',
        r'(\d+)\s*יחידות\s*מגורים',
        r'(\d+)\s*דירות',
    ]:
        m = re.search(pattern, t)
        if m:
            return int(m.group(1))
    # Explicit single-unit phrases
    if any(p in t for p in ['דירה אחת', 'יחידה אחת', '1 דירה', 'בית מגורים אחד']):
        return 1
    return None


def _is_below_unit_minimum(permit: pd.Series) -> bool:
    """
    True if the permit's unit count is explicitly below the minimum required to open a new
    project (per נוהל הקמת פרויקטים):
      - בניה חדשה / הריסה ובניה (non-תמ"א): minimum 3 units
      - צמודי קרקע: minimum 4 units (same-developer rule enforced manually)
      - תמ"א 38 (any variant): no minimum — never filter these
    Checks the structured unit_count field first (from scraper), falls back to parsing
    bakasha_description. Allows through if count cannot be determined.
    """
    request_type = _clean(permit.get('request_type', ''))

    # תמ"א 38 has no unit minimum — never filter
    if any(s in request_type for s in ['תמ"א 38', "תמ'א 38", 'חיזוק ותוספת']):
        return False

    # Try direct unit_count field from scraper first
    raw_count = _clean(permit.get('unit_count', ''))
    if raw_count:
        try:
            units = int(float(raw_count))  # float() handles '2.0' when CSV loaded without dtype=str
        except ValueError:
            units = None
    else:
        units = _extract_unit_count(_clean(permit.get('bakasha_description', '')))

    if units is None:
        return False  # can't determine — let through

    if 'צמודי קרקע' in request_type:
        return units < 4
    return units < 3

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


def _is_recent(date_val, max_days: int = _NEW_REQUEST_CUTOFF) -> bool:
    """True if date_val is within max_days of today, or if it cannot be parsed (keep unknown)."""
    d = _parse_date(date_val)
    if d is None:
        return True
    return (datetime.now() - d).days <= max_days


def _parse_date(val) -> Optional['datetime']:
    """Parse a date value (string, Timestamp, or date) into a datetime; returns None on failure."""
    from datetime import datetime
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, 'to_pydatetime'):
        return val.to_pydatetime()
    if hasattr(val, 'year'):
        return datetime(val.year, val.month, val.day)
    s = _clean(val)
    if not s:
        return None
    for fmt in ('%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue
    return None


def _latest_project_date(proj: pd.Series) -> Optional['datetime']:
    """Return the latest non-empty milestone date on a BO project row."""
    latest = None
    for col in STATUS_DATE_COLS.values():
        d = _parse_date(proj.get(col))
        if d is not None and (latest is None or d > latest):
            latest = d
    return latest


def _scraped_date_is_actionable(permit: pd.Series, proj: pd.Series) -> bool:
    """
    True if the permit's status date is genuinely newer than the project's existing dates.

    - Scraped date missing → keep (can't compare).
    - Project has existing milestone dates → scraped date must be strictly after the latest.
    - Project has no dates → scraped date must be within the last year (same cutoff as new_permit).
    """
    scraped_dt = _parse_date(permit.get('permit_status_date'))
    if scraped_dt is None:
        return True
    latest_proj_dt = _latest_project_date(proj)
    if latest_proj_dt is not None:
        return scraped_dt > latest_proj_dt
    return _is_recent(permit.get('permit_status_date'))


def _dates_within(d1: Optional['datetime'], d2: Optional['datetime'], days: int = 4) -> bool:
    """True if both dates are non-None and differ by at most `days` calendar days."""
    if d1 is None or d2 is None:
        return False
    return abs((d1 - d2).days) <= days


def _is_temporally_plausible(permit: pd.Series, proj: pd.Series, max_days_before: int = 365) -> bool:
    """
    False if the permit's request_date is more than max_days_before days before the
    project's תאריך בקשה להיתר. Permits filed after the project's date are always allowed.
    Returns True when either date is missing (can't disprove plausibility).
    """
    permit_date = _parse_date(permit.get('request_date'))
    proj_date = _parse_date(proj.get('תאריך בקשה להיתר'))
    if permit_date is None or proj_date is None:
        return True
    return (proj_date - permit_date).days <= max_days_before


def _parse_migrash(val) -> str:
    """Extract a bare migrash number from a 'תבע+מגרש' field value like 'נת/1234/מגרש 5' or '5'."""
    s = _clean(val)
    if not s:
        return ''
    m = re.search(r'מגרש\s*(\d+)', s)
    if m:
        return m.group(1)
    if re.fullmatch(r'\d+', s):
        return s
    return ''


def _fuzzy_name_score(name1: str, name2: str) -> int:
    """partial_ratio of two name strings; returns 0 if thefuzz is not installed."""
    if not _FUZZY_AVAILABLE or not name1 or not name2:
        return 0
    return _fuzz.partial_ratio(name1, name2)


def _pick_best_candidate(
    candidates: List[int],
    permit: pd.Series,
    projects_df: pd.DataFrame,
) -> int:
    """
    Given multiple BO project candidates sharing a Gush/Helka with this permit,
    return the index of the best match using:
      1. Migrash (if both sides have one and exactly one candidate matches)
      2. Fuzzy developer name vs. requestor (highest score >= threshold)
      3. First candidate (fallback)
    """
    if len(candidates) == 1:
        return candidates[0]

    permit_migrash = _clean(permit.get('migrash', ''))
    if permit_migrash:
        migrash_hits = [
            idx for idx in candidates
            if _parse_migrash(projects_df.loc[idx].get(_BO_MIGRASH_COL, '')) == permit_migrash
        ]
        if len(migrash_hits) == 1:
            return migrash_hits[0]
        if migrash_hits:
            candidates = migrash_hits

    # Step 2: Date anchor — match permit's request_date against BO's תאריך בקשה להיתר (±4 days)
    # Runs before fuzzy name so an exact date match isn't overridden by identical developer names.
    permit_date = _parse_date(permit.get('request_date'))
    if permit_date:
        date_hits = [
            idx for idx in candidates
            if _dates_within(permit_date, _parse_date(projects_df.loc[idx].get('תאריך בקשה להיתר')))
        ]
        if len(date_hits) == 1:
            return date_hits[0]
        if date_hits:
            candidates = date_hits

    # Step 3: Fuzzy developer name — fallback when date anchor can't narrow to one
    requestor = _clean(permit.get('requestor', ''))
    if requestor and _FUZZY_AVAILABLE:
        best_idx, best_score = candidates[0], 0
        for idx in candidates:
            dev = _clean(projects_df.loc[idx].get(_BO_DEVELOPER_COL, ''))
            score = _fuzzy_name_score(requestor, dev)
            if score > best_score:
                best_score, best_idx = score, idx
        if best_score >= _FUZZY_THRESHOLD:
            return best_idx

    return candidates[0]


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
    excluded_categories: Optional[set] = None,
    matched_cache_path: Optional[str] = None,
    permit_url_base: Optional[str] = None,
    city_filter: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Load projects and permits files, run matching, write flagged report to output_path.

    min_year: if set, permits with request_date year < min_year are excluded.
              Defaults to auto-computed from projects file (earliest permit date without Form 4).
    excluded_categories: set of request_category values to filter out before matching.
              Defaults to EXCLUDED_REQUEST_CATEGORIES. Pass an empty set to disable.
              NOTE: in פתח תקווה and הרצליה, 'בקשה מקדמית' advances to a real permit
              without being closed and reopened -- do NOT exclude it for those cities.
    matched_cache_path: if set, saves a JSON file listing every permit number that matched
              a BO project (including unchanged). Used by the incremental runner.
    Returns the report DataFrame.
    """
    if excluded_categories is None:
        excluded_categories = EXCLUDED_REQUEST_CATEGORIES

    def _permit_url(permit_num: str) -> str:
        if not permit_url_base or not permit_num:
            return ''
        return f'{permit_url_base}{permit_num}'

    projects_df = pd.read_excel(projects_path)
    if permits_path.endswith('.csv'):
        permits_df = pd.read_csv(permits_path, encoding='utf-8-sig')
    else:
        permits_df = pd.read_excel(permits_path)

    # Normalise column names (strip whitespace)
    projects_df.columns = [c.strip() for c in projects_df.columns]
    permits_df.columns = [c.strip() for c in permits_df.columns]

    if city_filter:
        before = len(projects_df)
        projects_df = projects_df[projects_df['עיר'].isin(city_filter)]
        print(f'[INFO] city_filter={city_filter}: {before} -> {len(projects_df)} projects')

    # Auto-compute min_year from projects file if not explicitly provided
    if min_year is None:
        min_year = _compute_min_year(projects_df)
        if min_year:
            print(f'[INFO] Auto-computed min_year={min_year} from projects file')

    # Year cutoff filters — permits with no date are kept (can't filter what we don't have).
    # Filter 1: permit_status_date (the date of the highest-ranked milestone event).
    # Filter 2: first_event_date (earliest event in the events table — catches old permits
    #           whose first event predates the cutoff even if recent activity exists).
    if min_year is not None:
        def _passes_year(v):
            y = _year_of(v)
            return y == 0 or y >= min_year
        before = len(permits_df)
        permits_df = permits_df[permits_df['permit_status_date'].apply(_passes_year)]
        print(f'[INFO] min_year={min_year}: {before} -> {len(permits_df)} permits (permit_status_date filter)')
        if 'first_event_date' in permits_df.columns:
            before = len(permits_df)
            permits_df = permits_df[permits_df['first_event_date'].apply(_passes_year)]
            print(f'[INFO] min_year={min_year}: {before} -> {len(permits_df)} permits (first_event_date filter)')

    # Excluded request categories — check both request_category (סוג הבקשה) and
    # request_type (תיאור הבקשה) since some cities place the category value in either field.
    if excluded_categories:
        before = len(permits_df)
        def _is_excluded(row):
            return (
                _clean(row.get('request_category', '')) in excluded_categories
                or _clean(row.get('request_type', '')) in excluded_categories
            )
        permits_df = permits_df[~permits_df.apply(_is_excluded, axis=1)]
        excluded = before - len(permits_df)
        if excluded:
            print(f'[INFO] Excluded {excluded} permits by request_category/type filter')

    # Filter test permits (requestor marked as a test entry)
    if 'requestor' in permits_df.columns:
        before = len(permits_df)
        permits_df = permits_df[~permits_df['requestor'].apply(
            lambda v: 'ניסיון' in _clean(v)
        )]
        dropped = before - len(permits_df)
        if dropped:
            print(f'[INFO] Dropped {dropped} test permits (ניסיון requestor)')

    report_rows = []
    matched_permit_numbers: List[str] = []  # all permits that matched a BO project

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

        # 1. Gush-helka — collect ALL candidates across all pairs, then pick best
        gh_candidates: List[int] = []
        for pair in permit_gh_pairs:
            for idx in gh_index.get(pair, []):
                if idx not in gh_candidates:
                    gh_candidates.append(idx)
        if gh_candidates:
            plausible = [
                idx for idx in gh_candidates
                if _is_temporally_plausible(permit, projects_df.loc[idx])
            ]
            if plausible:
                matched_idx = _pick_best_candidate(plausible, permit, projects_df)
                match_method = 'gush_helka'

        # 2. Address fallback
        if matched_idx is None:
            for idx, proj_row in projects_df.iterrows():
                if am.match(proj_row.get('שם פרויקט', ''), permit.get('full_address', ''), proj_row.get('עיר', city_hebrew)) \
                        and _is_temporally_plausible(permit, proj_row):
                    matched_idx = idx
                    match_method = 'address'
                    break

        # --- Apply use-case logic ---
        if matched_idx is not None:
            matched_permit_numbers.append(_clean(permit.get('request_number', '')))
            proj = projects_df.loc[matched_idx]

            db_status_raw = str(proj.get('סטטוס פרויקט', '') or '').strip()

            # Finished/occupied projects: minor alterations are irrelevant. Genuine new
            # construction (a new project on the same parcel) surfaces as untracked so a
            # new BO entry can be created; everything else is silently dropped.
            if db_status_raw in ('הסתיים', 'אוכלס'):
                if (_is_relevant_type(_clean(permit.get('request_type', '')))
                        or _is_relevant_type(_clean(permit.get('bakasha_description', '')))):
                    if (_is_recent(permit.get('request_date'))
                            and not _is_public_use(permit)
                            and not _is_below_unit_minimum(permit)):
                        scraped_status = _clean(permit.get('permit_status', ''))
                        scraped_date   = _clean(permit.get('permit_status_date', ''))
                        report_rows.append(_make_row(
                            flag='untracked',
                            proj=None, permit=permit, match_method='',
                            db_status='', scraped_status=scraped_status,
                            scraped_status_date=scraped_date, type_confirmed=True,
                            request_url=_permit_url(_clean(permit.get('request_number', ''))),
                        ))
                continue

            db_status_norm = DB_STATUS_NORM.get(db_status_raw, '')

            scraped_status = _clean(permit.get('permit_status', ''))
            scraped_date   = _clean(permit.get('permit_status_date', ''))
            request_type   = _clean(permit.get('request_type', ''))
            type_known     = bool(request_type)
            type_relevant  = _is_relevant_type(request_type)

            # Manual review: matched permit has a flagged event — surface after applying
            # the same project-criteria filters used for other branches.
            # Exception: הוצאת היתר בניה is confirmed as היתר when תאריך הפקת היתר was
            # present on the page (scraped_status == 'היתר'). Fall through to normal logic.
            manual_review_event = _clean(permit.get('manual_review_event', ''))
            hitir_confirmed = (manual_review_event == 'הוצאת היתר בניה'
                               and scraped_status == 'היתר')
            if manual_review_event and not hitir_confirmed:
                if not type_relevant:
                    continue
                if _is_public_use(permit):
                    continue
                # Waive unit minimum when the matched project is a תמ"א 38 project
                project_sug_bnia = _clean(proj.get('סוג בנייה', ''))
                if 'תמ"א 38' not in project_sug_bnia and _is_below_unit_minimum(permit):
                    continue
                report_rows.append(_make_row(
                    flag='manual_review',
                    proj=proj, permit=permit,
                    match_method=match_method,
                    db_status=db_status_raw,
                    scraped_status=scraped_status,
                    scraped_status_date=scraped_date,
                    request_url=_permit_url(_clean(permit.get('request_number', ''))),
                ))
                continue

            project_sug_bnia = _clean(proj.get('סוג בנייה', ''))
            waive_unit_min = 'תמ"א 38' in project_sug_bnia

            if db_status_raw == 'טרום בקשה' and (type_relevant or not type_known) \
                    and _is_recent(permit.get('request_date')) \
                    and not _is_public_use(permit) \
                    and (waive_unit_min or not _is_below_unit_minimum(permit)):
                report_rows.append(_make_row(
                    flag='new_permit',
                    proj=proj,
                    permit=permit,
                    match_method=match_method,
                    db_status=db_status_raw,
                    scraped_status=scraped_status,
                    scraped_status_date=scraped_date,
                    type_confirmed=type_known,
                    request_url=_permit_url(_clean(permit.get('request_number', ''))),
                ))

            elif _is_upgrade(db_status_norm, scraped_status) \
                    and _scraped_date_is_actionable(permit, proj) \
                    and (_is_relevant_type(_clean(permit.get('request_type', '')))
                         or _is_relevant_type(_clean(permit.get('bakasha_description', '')))) \
                    and not _is_public_use(permit) \
                    and (waive_unit_min or not _is_below_unit_minimum(permit)):
                report_rows.append(_make_row(
                    flag='status_advanced',
                    proj=proj,
                    permit=permit,
                    match_method=match_method,
                    db_status=db_status_raw,
                    scraped_status=scraped_status,
                    scraped_status_date=scraped_date,
                    type_confirmed=True,
                    request_url=_permit_url(_clean(permit.get('request_number', ''))),
                ))
            # else unchanged: match found, nothing new -> skip

        else:
            # No matching project — check for manual review event first
            manual_review_event = _clean(permit.get('manual_review_event', ''))
            # הוצאת היתר בניה is confirmed when תאריך הפקת היתר was on the page
            hitir_confirmed = (manual_review_event == 'הוצאת היתר בניה'
                               and _clean(permit.get('permit_status', '')) == 'היתר')
            if manual_review_event and not hitir_confirmed:
                if (_is_relevant_type(_clean(permit.get('request_type', '')))
                        and _is_recent(permit.get('request_date'))):
                    scraped_status = _clean(permit.get('permit_status', ''))
                    scraped_date   = _clean(permit.get('permit_status_date', ''))
                    report_rows.append(_make_row(
                        flag='manual_review',
                        proj=None, permit=permit,
                        match_method='',
                        db_status='', scraped_status=scraped_status,
                        scraped_status_date=scraped_date,
                        request_url=_permit_url(_clean(permit.get('request_number', ''))),
                    ))
                continue

            # Only flag permits with a confirmed relevant type,
            # filed within the last year, that are not public buildings or below unit minimum.
            if not _is_relevant_type(_clean(permit.get('request_type', ''))):
                continue
            if not _is_recent(permit.get('request_date')):
                continue
            if _is_public_use(permit):
                continue
            if _is_below_unit_minimum(permit):
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
                request_url=_permit_url(_clean(permit.get('request_number', ''))),
                type_confirmed=True,   # type_relevant was required to reach here
            ))

    report_df = pd.DataFrame(report_rows)
    if not report_df.empty:
        report_df.to_excel(output_path, index=False)
        print(f'[OK] Report written to {output_path} ({len(report_df)} rows)')
    else:
        print('[OK] No flagged items found.')

    _print_summary(report_df)

    if matched_cache_path and matched_permit_numbers:
        import json, os
        os.makedirs(os.path.dirname(matched_cache_path) or '.', exist_ok=True)
        with open(matched_cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'city': city_hebrew,
                'matched_permit_numbers': matched_permit_numbers,
            }, f, ensure_ascii=False, indent=2)
        print(f'[OK] Matched permit cache saved to {matched_cache_path} ({len(matched_permit_numbers)} permits)')

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
    request_url: str = '',
) -> dict:
    return {
        'flag':               flag,
        'city':               str(proj['עיר']) if proj is not None else '',
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
        'request_type':        _clean(permit.get('request_type', '')),
        'shimush_ikari':        _clean(permit.get('shimush_ikari', '')),
        'unit_count':           _clean(permit.get('unit_count', '')),
        'manual_review_event':  _clean(permit.get('manual_review_event', '')),
        'bakasha_description':  _clean(permit.get('bakasha_description', '')),
        'requestor':           _clean(permit.get('requestor', '')),
        'permit_block_lot':   _clean(permit.get('block_lot', '')),
        'request_url':         request_url,
    }


def _print_summary(df: pd.DataFrame):
    if df.empty:
        return
    counts = df['flag'].value_counts()
    print('[Summary]')
    for flag in ['new_permit', 'status_advanced', 'untracked', 'manual_review']:
        print(f'  {flag}: {counts.get(flag, 0)}')
