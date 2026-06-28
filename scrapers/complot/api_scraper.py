"""
Complot municipal permit scraper -- direct API, no Selenium.

Calls handasi.complot.co.il directly (no CAPTCHA protection on the backend).
Two-step process:
  1. GetBakashotByNumber  -> full permit list (~520 rows for Bat Yam)
  2. GetTikFile           -> per unique building_id, returns permit status per request

Output schema matches ComplotScraper so matcher.py works unchanged.
"""

import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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

# Map event description substrings to status vocabulary.
# Keys are matched as substrings; first match wins. Ordered from most to least specific.
EVENT_TO_STATUS: Dict[str, str] = {
    # טופס 4
    'הפקת תעודת גמר':              'טופס 4',
    'מסירת תעודת גמר':             'טופס 4',        # completion certificate delivered to applicant
    # היתר
    'מתן היתר למבקש':              'היתר',
    'הפקת היתר בניה לחתימות':     'היתר',
    'היתר היסטורי':                'היתר',
    'מסירת היתר(בסמכות מהנדס)':   'היתר',          # permit delivered under engineer's authority
    # היתר בתנאים
    'החלטה לאשר בתנאי/ם':         'היתר בתנאים',   # committee decision: approved with conditions
    # בקשה להיתר
    'פתיחת בקשה':                  'בקשה להיתר',    # covers 'להיתר', 'היסטורית', plain
    'בקשה ללא היתר':               'בקשה להיתר',   # request processed but no permit issued
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


class ComplotPermitsAPI:
    """
    API-based permit scraper for Complot municipal sites.

    Usage:
        scraper = ComplotPermitsAPI(site_id=81, city_name_hebrew='bet yam')
        scraper.year_filter = [2025, 2026]
        permits = scraper.scrape()
    """

    def __init__(self, site_id: int, city_name_hebrew: str,
                 year_filter: Optional[List[int]] = None,
                 b_params: Optional[List[int]] = None):
        self.site_id = site_id
        self.city_name = city_name_hebrew
        self.year_filter = year_filter
        # Each value is passed as &b= to GetBakashotByNumber (substring match on permit number).
        # Querying one value per year and deduplicating covers the full permit history.
        self.b_params = b_params if b_params is not None else list(range(2011, 2027))
        self.max_requests: Optional[int] = None  # set to int for testing
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._tik_headers_logged = False

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def scrape(self) -> List[Dict]:
        """
        Returns permit dicts with keys:
          request_number, request_date, full_address, city, block_lot,
          request_type, project_description, requestor,
          permit_status, permit_status_date, permit_issued_num, scrape_status
        """
        _log(f'Fetching permit list for site_id={self.site_id} (b={self.b_params[0]}..{self.b_params[-1]})...')
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

        # Unique building_ids in the order they first appear
        seen_bids: Dict[str, None] = {}
        for p in permit_list:
            if p.get('building_id'):
                seen_bids[p['building_id']] = None
        building_ids = list(seen_bids)

        _log(f'Fetching {len(building_ids)} unique building files (GetTikFile)...')

        # building_id -> {permit_num: (event, event_date, issued_num, issued_date)}
        building_data: Dict[str, Dict[str, Tuple[str, str, str, str]]] = {}
        for i, bid in enumerate(building_ids):
            _log(f'  [{i+1}/{len(building_ids)}] GetTikFile t={bid}')
            try:
                building_data[bid] = self._get_tik_file(bid)
            except Exception as e:
                _log(f'  [ERROR] GetTikFile {bid}: {e}')
                building_data[bid] = {}
            time.sleep(1.0)  # ~1 req/sec -- polite

        _log('Merging list + building data...')
        permits = [self._merge_permit(p, building_data) for p in permit_list]
        _log(f'Done. {len(permits)} permits assembled.')
        return permits

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    def _get_permit_list(self) -> List[Dict]:
        # Keyed by permit_num to deduplicate across b= queries (substring matching causes overlap).
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

    def _get_tik_file(self, building_id: str) -> Dict[str, Tuple[str, str, str, str]]:
        params = {
            'appname':   'cixpa',
            'prgname':   'GetTikFile',
            'siteid':    self.site_id,
            't':         building_id,
            'arguments': 'siteid,t',
        }
        resp = self._session.get(API_BASE, params=params, timeout=30)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        return self._parse_tik_file(resp.text)

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
                cells[0].get_text(strip=True)
            )
            if not permit_num:
                continue

            building_id = row_data.get('תיק בניין', '').strip()
            gush  = row_data.get('גוש',  '').strip()
            helka = row_data.get('חלקה', '').strip()
            block_lot = f'{gush}-{helka}' if gush and helka else gush

            permits.append({
                'permit_num':   str(permit_num).strip(),
                'building_id':  building_id,
                'request_date': row_data.get('תאריך הגשה', '').strip(),
                'requestor':    row_data.get('שם המבקש',  '').strip(),
                'address':      row_data.get('כתובת',     '').strip(),
                'block_lot':    block_lot,
            })

        return permits

    def _parse_tik_file(self, html: str) -> Dict[str, Tuple[str, str, str, str]]:
        """
        Returns dict: permit_num -> (best_event, event_date, issued_num, issued_date)
        Picks the highest-milestone event row per permit number.
        """
        soup = BeautifulSoup(html, 'html.parser')
        # Find the requests table by its characteristic header, not by id (id is absent)
        table = _find_table_with_header(soup, 'ארוע אחרון להצגה')
        if table is None:
            table = soup.find('table', id='table-requests') or _find_data_table(soup)
        if table is None:
            return {}

        headers = _extract_headers(table)
        if not self._tik_headers_logged:
            _log(f'  TikFile headers: {headers}')
            self._tik_headers_logged = True

        permit_col    = _find_col(headers, ['מספר בקשה'])
        date_col      = _find_col(headers, ['תאריך הגשה'])
        event_col     = _find_col(headers, ['ארוע אחרון להצגה', 'ארוע אחרון'])
        issued_col    = _find_col(headers, ['היתר'])
        issued_dt_col = _find_col(headers, ['תאריך היתר'])

        # permit_num -> (rank, event, event_date, issued_num, issued_date)
        best: Dict[str, Tuple[int, str, str, str, str]] = {}

        for row in table.select('tbody tr'):
            cells = row.find_all('td')
            if not cells:
                continue

            def _cell(col_name: Optional[str]) -> str:
                if col_name is None:
                    return ''
                try:
                    idx = headers.index(col_name)
                    return cells[idx].get_text(strip=True) if idx < len(cells) else ''
                except (ValueError, IndexError):
                    return ''

            permit_num = _cell(permit_col)
            event      = _cell(event_col)
            event_date = _cell(date_col)
            issued     = _cell(issued_col)
            issued_dt  = _cell(issued_dt_col)

            if not permit_num:
                continue

            status = _map_event(event)
            rank = STATUS_ORDER.index(status) if status in STATUS_ORDER else -1

            prev = best.get(permit_num)
            if prev is None or rank > prev[0]:
                best[permit_num] = (rank, event, event_date, issued, issued_dt)

        return {
            num: (ev, dt, iss, iss_dt)
            for num, (_, ev, dt, iss, iss_dt) in best.items()
        }

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def _merge_permit(self, raw: Dict,
                      building_data: Dict[str, Dict]) -> Dict:
        permit_num = raw['permit_num']
        bid = raw.get('building_id', '')
        tik = building_data.get(bid, {})

        event, event_date, issued, issued_dt = tik.get(permit_num, ('', '', '', ''))

        # Fallback: if this building has only one permit entry and the lookup missed,
        # the API may have returned the permit under a slightly different key format.
        if not event and len(tik) == 1:
            event, event_date, issued, issued_dt = next(iter(tik.values()))

        permit_status = _map_event(event)
        # Prefer the permit-issue date when available, otherwise the event date
        permit_status_date = issued_dt if issued_dt else event_date

        scrape_status = 'success' if permit_num and raw.get('address') else 'partial'

        _log(f'  {permit_num}: status={permit_status or "-"} '
             f'bid={bid} event=[{event[:40] if event else ""}]')

        return {
            'request_number':      permit_num,
            'request_date':        raw.get('request_date', ''),
            'full_address':        raw.get('address', ''),
            'city':                self.city_name,
            'block_lot':           raw.get('block_lot', ''),
            'request_type':        '',   # not in list view; requires GetBakashaFile (blocked)
            'project_description': '',
            'requestor':           raw.get('requestor', ''),
            'permit_status':       permit_status,
            'permit_status_date':  permit_status_date,
            'permit_issued_num':   issued,
            'scrape_status':       scrape_status,
        }

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

def _find_table_with_header(soup: BeautifulSoup, header_text: str):
    """Return the first table that has a <th> containing header_text."""
    for table in soup.find_all('table'):
        for th in table.find_all('th'):
            if header_text in th.get_text(strip=True):
                return table
    return None


def _find_data_table(soup: BeautifulSoup):
    """Return first table with at least 3 header cells, else first table with rows."""
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
