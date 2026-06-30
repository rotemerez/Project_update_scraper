"""
Complot municipal permit scraper -- direct API, no Selenium.

Calls handasi.complot.co.il directly (no CAPTCHA protection on the backend).
Two-step process:
  1. GetBakashotByNumber  -> full permit list (all unique permits for a city)
  2. GetBakashaFile       -> per-permit detail page: request_type, request_category, events

Output schema:
  request_number, request_date, full_address, city, block_lot,
  request_type      (from תיאור הבקשה  on detail page -- construction description)
  request_category  (from סוג הבקשה   on detail page -- e.g. 'בקשה מקדמית', 'היתר בניה')
  requestor, permit_status, permit_status_date, scrape_status
"""

import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd
except ImportError as e:
    raise ImportError(
        f"Missing dependency: {e}\n"
        "Run: pip install requests beautifulsoup4 pandas openpyxl"
    )


API_BASE = "https://handasi.complot.co.il/magicscripts/mgrqispi.dll"

# Map event description text to status vocabulary.
# Keys matched as exact substrings; first match wins. Ordered most-to-least specific.
EVENT_TO_STATUS: Dict[str, str] = {
    # טופס 4
    'הפקת תעודת גמר':                           'טופס 4',
    'מסירת תעודת גמר':                          'טופס 4',
    # היתר
    'מתן היתר למבקש':                           'היתר',
    'הפקת היתר בניה לחתימות':                  'היתר',
    'היתר היסטורי':                             'היתר',
    'מסירת היתר(בסמכות מהנדס)':                'היתר',
    # היתר בתנאים
    'החלטה לאשר בתנאי/ם':                       'היתר בתנאים',
    # בקשה להיתר
    'פתיחת בקשה להיתר':                         'בקשה להיתר',
    'פתיחת בקשה':                               'בקשה להיתר',   # catches 'היסטורית' and plain variants
    'בקשה ללא היתר':                            'בקשה להיתר',
}

# Known event strings that are intentionally not mapped -- admin/processing steps
# or permit-closed events that don't represent a milestone we track.
# Listed here so we don't need to re-investigate them.
_UNMAPPED_EVENTS = {
    'סיום טיפול בבקשה להיתר ללא הוצאת היתר',  # closed without permit -- not a trackable milestone
    'הערות לקליטה',
    'שינוי לבקשה',
    'הפקת דרישות',
    'מידע תכנוני',
    'פגם בבקשה',
    'דחיית בקשה',
    'ביטול בקשה',
    'קבלת אישור מחלקה',
    'אישור שכנים',
    'פרסום הבקשה',
    'העברה ליחידה אחרת',
    # fee/admin processing steps
    'מסירת היתר',
    'הכנת היתר טיוטא לחתימות בלבד',
    'תשלום אגרת בניה',
    'חישוב אגרת בניה',
    'אישור העברת בקשה לחישובי אגרות',
    # scheduling/scanning admin
    'הוסר מסדר היום',
    'החזרת תיק מסריקה',
    # form 2 / betterment levy admin
    'הפקת טופס 2',
    'בדיקת שמאי פנימי להיטל השבחה',
    # licensing authority / inspector / committee admin
    'הדפסת מכתבי החלטה',
    'מיועד לישיבת רשות רישוי',
    'המתנה לבדיקת מפקח',
    'הבקשה מתאימה למציאות',
    'הבקשה לא מתאימה למציאות',
    'בדיקת מפקח לבקשה להיתר',
    'ביטול היתר',
    'תשלום אגרת תאגיד',
    'חישוב אגרת תאגיד',
    'ישיבת מליאת הועדה',
    'ישיבת ועדת משנה',
    'ישיבת רשות רישוי',
    'החלטה לאשר',
    'בקשה עברה לשלב בקרת תכן',
    'בקשה הועברה לבקרה מרחבית (45 יום)',
    'השלמת תנאי סף בקשה להיתר - מחלקת מידע',
    # בקשה למידע workflow events (information requests -- not trackable permit milestones)
    'ביטול בקשה למידע',
    'קבלת נתונים מרישוי זמין',
    'העברת תיק המידע למערכת רישוי זמין',
    'העברת תיק מידע לאישור',
    'הכנת טיוטא תיק מידע',
    'השלמת בקשה למידע להתייחסות אסטרטגיה',
    'העברת בקשה למידע להתייחסות מח\' אסטרטגיה',
    'השלמת התייחסות מחלקת רישוי - חלופת שקד',
    'העברה להתייחסות מחלקת רישוי - חלופת שקד',
    'העברת בקשה למידען',
    'דחיית בקשה למידע - אי עמידה בתנאי סף',
    'קבלת התייחסות למידע היחידה לקיימות ואיכות הסביבה ובנייה ירוקה',
    # deposit / Rishuy Zamin intake admin
    'תשלום פיקדון',
    'הפקת פקדון לתשלום',
    'עודכנו פרטי לקוח ונכס / נמסר פיקדון לתשלום',
    'קליטת בקשה מרישוי זמין(1)',
    'קליטת בקשה מרישוי זמין(2)',
    'קליטת בקשה מרישוי זמין(3)',
    'דחיית בקשה בתנאי סף - מח\' מידע (1)',
    'דחיית בקשה בתנאי סף - מח\' מידע(2)',
    'דחיית בקשה בתנאי סף - מח\' מידע(3)',
    'הבקשה נסגרה ברישוי זמין בגרסה שניה על העורך לפתוח בקשה חדשה ברישוי זמין',
    # dangerous-building declaration events (separate municipal process, not a permit milestone)
    'פתיחת תיק מבנה מסוכן',
    'תאריך פניה לבדיקת מבנה מסוכן',
    'תאריך סיור מהנדס הכרזה מבנה מסוכן',
    'המבנה מוכרז כמבנה מסוכן',
    'תאריך שליחת חו"ד מסוכנות לבעלי הנכס',
}

STATUS_ORDER = ['בקשה להיתר', 'היתר בתנאים', 'היתר', 'טופס 4']

_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
}


def _log(msg: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')


def _map_event(event: str) -> str:
    for keyword, status in EVENT_TO_STATUS.items():
        if keyword in event:
            return status
    return ''


def _earlier_date(a: str, b: str) -> bool:
    """Return True if date string a is chronologically earlier than b (DD/MM/YYYY or DD.MM.YYYY)."""
    for fmt in ('%d/%m/%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(a, fmt) < datetime.strptime(b, fmt)
        except ValueError:
            continue
    return False


class ComplotPermitsAPI:
    """
    API-based permit scraper for Complot municipal sites.

    Usage:
        scraper = ComplotPermitsAPI(site_id=81, city_name_hebrew='בת ים')
        permits = scraper.scrape()
    """

    def __init__(self, site_id: int, city_name_hebrew: str,
                 year_filter: Optional[List[int]] = None,
                 b_params: Optional[List[int]] = None):
        self.site_id = site_id
        self.city_name = city_name_hebrew
        self.year_filter = year_filter
        self.b_params = b_params if b_params is not None else list(range(2011, 2027))
        self.max_requests: Optional[int] = None  # set to int for testing
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def scrape(self) -> List[Dict]:
        """
        Returns permit dicts with keys:
          request_number, request_date, full_address, city, block_lot,
          request_type, request_category, requestor,
          permit_status, permit_status_date, scrape_status
        """
        _log(f'Fetching permit list for site_id={self.site_id}...')
        permit_list = self._get_permit_list()
        if not permit_list:
            _log('[ERROR] Empty permit list -- aborting.')
            return []

        _log(f'Got {len(permit_list)} unique permits after deduplication')

        if self.year_filter:
            before = len(permit_list)
            permit_list = [p for p in permit_list if self._passes_year_filter(p['request_date'])]
            _log(f'Year filter {self.year_filter}: {before} -> {len(permit_list)} permits')

        if self.max_requests:
            permit_list = permit_list[:self.max_requests]
            _log(f'Limiting to {self.max_requests} for testing')

        _log(f'Fetching detail page (GetBakashaFile) for {len(permit_list)} permits...')
        permits = []
        for i, raw in enumerate(permit_list):
            permit_num = raw['permit_num']
            _log(f'  [{i+1}/{len(permit_list)}] GetBakashaFile {permit_num}')
            try:
                detail = self._get_bakasha_file(permit_num)
            except Exception as e:
                _log(f'  [ERROR] GetBakashaFile {permit_num}: {e}')
                detail = {'request_type': '', 'request_category': '', 'event': '', 'event_date': ''}
            permits.append(self._merge_permit(raw, detail))
            time.sleep(0.5)

        _log(f'Done. {len(permits)} permits assembled.')
        return permits

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def _get_permit_list(self) -> List[Dict]:
        seen: Dict[str, Dict] = {}
        for b in self.b_params:
            params = {
                'appname':   'cixpa',
                'prgname':   'GetBakashotByNumber',
                'siteid':    self.site_id,
                'grp':       0,
                't':         0,
                'b':         b,
                'l':         'false',
                'arguments': 'siteId,grp,t,b,l',
            }
            try:
                resp = self._session.get(API_BASE, params=params, timeout=60)
                resp.raise_for_status()
                resp.encoding = 'utf-8'
            except Exception as e:
                _log(f'  [WARN] GetBakashotByNumber b={b} failed: {e}')
                continue

            _save_debug_html(resp.text, f'permit_list_b{b}')
            rows = self._parse_permit_list(resp.text)
            new = sum(1 for r in rows if r['permit_num'] not in seen)
            for r in rows:
                seen.setdefault(r['permit_num'], r)
            _log(f'  b={b}: {len(rows)} rows, {new} new (total unique: {len(seen)})')
            time.sleep(1.0)

        return list(seen.values())

    def _get_bakasha_file(self, permit_num: str) -> Dict:
        params = {
            'appname':   'cixpa',
            'prgname':   'GetBakashaFile',
            'siteid':    self.site_id,
            't':         permit_num,
            'arguments': 'siteid,t',
        }
        resp = self._session.get(API_BASE, params=params, timeout=30)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        return self._parse_bakasha_file(resp.text)

    # ------------------------------------------------------------------
    # HTML parsers
    # ------------------------------------------------------------------

    def _parse_permit_list(self, html: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        table = _find_data_table(soup)
        if table is None:
            _log('[WARN] No data table found in GetBakashotByNumber response')
            return []

        headers = _extract_headers(table)
        _log(f'  List table headers: {headers}')

        permits = []
        for row in table.select('tbody tr'):
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            row_data = {
                headers[i]: cells[i].get_text(strip=True)
                for i in range(min(len(headers), len(cells)))
            }

            permit_num = (
                row_data.get('מספר בקשה(רישוי זמין)') or
                row_data.get('מספר בקשה') or
                row_data.get("מס' בקשה") or
                next(cells[0].stripped_strings, '')
            )
            if not permit_num:
                continue
            # Local permit number is YYYY#### (8 digits starting with 20YY).
            # The list page sometimes appends the national רישוי זמין ID — strip it.
            _m = re.match(r'(20\d{6})', str(permit_num).strip())
            if _m:
                permit_num = _m.group(1)

            gush  = row_data.get('גוש',  '').strip()
            helka = row_data.get('חלקה', '').strip()
            block_lot = f'{gush}-{helka}' if gush and helka else gush

            permits.append({
                'permit_num':   str(permit_num).strip(),
                'request_date': row_data.get('תאריך הגשה', '').strip(),
                'requestor':    row_data.get('שם המבקש',  '').strip(),
                'address':      row_data.get('כתובת',     '').strip(),
                'block_lot':    block_lot,
            })

        return permits

    def _parse_bakasha_file(self, html: str) -> Dict:
        """
        Extract from permit detail page:
          request_type         - תיאור הבקשה (construction description)
          request_category     - סוג הבקשה   (permit category)
          bakasha_description  - מהות הבקשה  (free-text nature of request)
          event                - most recent mappable event description
          event_date           - date of that event
          applicant_name       - מבקש row from בעלי עניין table
          migrash              - מספר מגרש from גושים וחלקות table
        """
        soup = BeautifulSoup(html, 'html.parser')

        request_type        = _extract_field(soup, 'תיאור הבקשה')
        request_category    = _extract_field(soup, 'סוג הבקשה')
        bakasha_description = _extract_field(soup, 'מהות הבקשה')

        # Events table: find by 'תיאור אירוע' header
        event_table = _find_table_with_header(soup, 'תיאור אירוע')
        best_event = ''
        best_event_date = ''
        best_rank = -1
        first_event_date = ''

        if event_table:
            headers = _extract_headers(event_table)
            desc_col = _find_col(headers, ['תיאור אירוע'])
            date_col = _find_col(headers, ['תאריך אירוע'])

            for row in event_table.select('tbody tr'):
                cells = row.find_all('td')

                def _cell(col_name: Optional[str]) -> str:
                    if col_name is None:
                        return ''
                    try:
                        idx = headers.index(col_name)
                        return cells[idx].get_text(strip=True) if idx < len(cells) else ''
                    except (ValueError, IndexError):
                        return ''

                event_desc = _cell(desc_col)
                event_date = _cell(date_col)

                if event_date:
                    if not first_event_date or _earlier_date(event_date, first_event_date):
                        first_event_date = event_date

                status = _map_event(event_desc)
                rank = STATUS_ORDER.index(status) if status in STATUS_ORDER else -1
                if rank > best_rank:
                    best_rank = rank
                    best_event = event_desc
                    best_event_date = event_date

                if event_desc and event_desc not in _UNMAPPED_EVENTS and not status:
                    _log(f'  [NEW EVENT] Unmapped: [{event_desc}]')

        # Applicant: find מבקש row in בעלי עניין table
        applicant_name = ''
        stakeholder_table = _find_table_with_header(soup, 'סוג בעל עניין')
        if stakeholder_table:
            sh_headers = _extract_headers(stakeholder_table)
            type_col = _find_col(sh_headers, ['סוג בעל עניין'])
            name_col = _find_col(sh_headers, ['שם בעל עניין'])
            if type_col and name_col:
                type_idx = sh_headers.index(type_col)
                name_idx = sh_headers.index(name_col)
                for row in stakeholder_table.select('tbody tr'):
                    cells = row.find_all('td')
                    if len(cells) > max(type_idx, name_idx):
                        role = cells[type_idx].get_text(strip=True)
                        if 'מבקש' in role:
                            applicant_name = cells[name_idx].get_text(strip=True)
                            break

        # Gush / helka / migrash: from גושים וחלקות table
        # The detail page is authoritative — the list page sometimes returns the wrong parcel.
        migrash = ''
        detail_block_lot = ''
        parcel_table = _find_table_with_header(soup, 'מספר גוש')
        if parcel_table:
            p_headers = _extract_headers(parcel_table)
            gush_col    = _find_col(p_headers, ['מספר גוש'])
            helka_col   = _find_col(p_headers, ['מספר חלקה'])
            migrash_col = _find_col(p_headers, ['מספר מגרש'])
            gush_idx    = p_headers.index(gush_col)    if gush_col    else None
            helka_idx   = p_headers.index(helka_col)   if helka_col   else None
            migrash_idx = p_headers.index(migrash_col) if migrash_col else None
            for row in parcel_table.select('tbody tr'):
                cells = row.find_all('td')
                if migrash_idx is not None and len(cells) > migrash_idx:
                    migrash = cells[migrash_idx].get_text(strip=True)
                if gush_idx is not None and helka_idx is not None \
                        and len(cells) > max(gush_idx, helka_idx):
                    gush  = cells[gush_idx].get_text(strip=True)
                    helka = cells[helka_idx].get_text(strip=True)
                    if gush and helka:
                        detail_block_lot = f'{gush}-{helka}'
                break  # take first parcel row

        return {
            'request_type':        request_type,
            'request_category':    request_category,
            'bakasha_description': bakasha_description,
            'event':               best_event,
            'event_date':          best_event_date,
            'first_event_date':    first_event_date,
            'applicant_name':      applicant_name,
            'migrash':             migrash,
            'detail_block_lot':    detail_block_lot,
        }

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def _merge_permit(self, raw: Dict, detail: Dict) -> Dict:
        permit_status = _map_event(detail.get('event', ''))
        scrape_status = 'success' if raw.get('permit_num') and raw.get('address') else 'partial'
        # Prefer applicant_name from detail page (structured role table) over list-page requestor
        requestor = detail.get('applicant_name') or raw.get('requestor', '')

        return {
            'request_number':      raw['permit_num'],
            'request_date':        raw.get('request_date', ''),
            'full_address':        raw.get('address', ''),
            'city':                self.city_name,
            'block_lot':           detail.get('detail_block_lot') or raw.get('block_lot', ''),
            'migrash':             detail.get('migrash', ''),
            'request_type':        detail.get('request_type', ''),
            'request_category':    detail.get('request_category', ''),
            'bakasha_description': detail.get('bakasha_description', ''),
            'requestor':           requestor,
            'permit_status':       permit_status,
            'permit_status_date':  detail.get('event_date', ''),
            'first_event_date':    detail.get('first_event_date', ''),
            'scrape_status':       scrape_status,
        }

    # ------------------------------------------------------------------
    # Targeted refresh (incremental mode)
    # ------------------------------------------------------------------

    def scrape_targeted(self, permit_records: List[Dict]) -> List[Dict]:
        """
        Refresh detail-page fields for a known list of permits without re-fetching
        the permit list. Identity fields (address, block_lot, request_date, city)
        are preserved from the input records; status/events are refreshed via
        GetBakashaFile.

        Used by the incremental runner for Phase A (re-checking matched permits).
        """
        if self.max_requests:
            permit_records = permit_records[:self.max_requests]
        _log(f'[targeted] Refreshing {len(permit_records)} permits via GetBakashaFile...')
        results = []
        for i, record in enumerate(permit_records):
            permit_num = str(record.get('request_number', '')).strip()
            if not permit_num:
                continue
            _log(f'  [{i+1}/{len(permit_records)}] GetBakashaFile {permit_num}')
            try:
                detail = self._get_bakasha_file(permit_num)
            except Exception as e:
                _log(f'  [WARN] {permit_num}: {e} -- keeping cached status')
                # Preserve last-known status so the permit still appears in matcher
                detail = {
                    'request_type':        record.get('request_type', ''),
                    'request_category':    record.get('request_category', ''),
                    'bakasha_description': record.get('bakasha_description', ''),
                    'applicant_name':      record.get('requestor', ''),
                    'migrash':             record.get('migrash', ''),
                    'detail_block_lot':    record.get('block_lot', ''),
                    'event':               record.get('permit_status', ''),
                    'event_date':          record.get('permit_status_date', ''),
                    'first_event_date':    record.get('first_event_date', ''),
                }
            results.append(self._merge_permit(
                {
                    'permit_num':   permit_num,
                    'request_date': record.get('request_date', ''),
                    'address':      record.get('full_address', ''),
                    'block_lot':    record.get('block_lot', ''),
                    'requestor':    record.get('requestor', ''),
                },
                detail,
            ))
            time.sleep(0.5)
        _log(f'[targeted] Done. {len(results)} permits refreshed.')
        return results

    # ------------------------------------------------------------------
    # Year filter
    # ------------------------------------------------------------------

    def _passes_year_filter(self, date_str: str) -> bool:
        if not date_str or not self.year_filter:
            return True
        for fmt in ('%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(date_str, fmt).year in self.year_filter
            except ValueError:
                continue
        return False


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _extract_field(soup: 'BeautifulSoup', label_text: str) -> str:
    """Find a label cell by exact text and return the text of the next sibling cell."""
    for tag in soup.find_all(string=lambda t: t and t.strip() == label_text):
        parent = tag.find_parent()
        if parent:
            sibling = parent.find_next_sibling()
            if sibling:
                val = sibling.get_text(strip=True)
                if val:
                    return val
    return ''


def _find_table_with_header(soup: 'BeautifulSoup', header_text: str):
    for table in soup.find_all('table'):
        for th in table.find_all('th'):
            if header_text in th.get_text(strip=True):
                return table
    return None


def _find_data_table(soup: 'BeautifulSoup'):
    for table in soup.find_all('table'):
        if len(table.find_all('th')) >= 3:
            return table
    for table in soup.find_all('table'):
        if table.select('tbody tr'):
            return table
    return None


def _extract_headers(table) -> List[str]:
    ths = table.find_all('th')
    if ths:
        return [th.get_text(strip=True) for th in ths]
    first_row = table.find('tr')
    if first_row:
        return [td.get_text(strip=True) for td in first_row.find_all('td')]
    return []


def _find_col(headers: List[str], candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in headers:
            return c
    return None


def _save_debug_html(html: str, label: str):
    path = f'outputs/debug_api_{label}.html'
    if os.path.exists(path):
        return
    try:
        os.makedirs('outputs', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        _log(f'  [DEBUG] HTML saved to {path}')
    except Exception:
        pass
