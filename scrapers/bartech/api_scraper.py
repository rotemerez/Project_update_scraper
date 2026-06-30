"""
Bartech municipal permit scraper -- direct API, no Selenium.

Calls the Bartech planning portal directly (no CAPTCHA enforcement).
Iterates SearchPermitApplicationResults for each included TypeOfPermit.

Output schema (same as Complot):
  request_number, request_date, full_address, city, block_lot,
  request_type, request_category, requestor,
  permit_status, permit_status_date, scrape_status
"""

import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

RESULTS_PATH = '/SearchPermitApplicationResults/'

PERMIT_TYPES: Dict[int, str] = {
    51: 'מסלול רישוי מלא',
    56: 'מסלול רישוי מקוצר',
    57: 'מסלול רישוי עם הקלות ו/או שימוש חורג',
    71: 'בקשה מקוונת ללא הקלות',
    72: 'בקשה מקוונת עם הקלות',
    73: 'בקשה מקוונת רישוי מקוצר',
}

_KNOWN_CLOSED = {'לא פעיל', 'סגירת בקשה - פג תוקף החלטה'}

STATUS_MAP: Dict[str, str] = {
    'מאושר':                                       'היתר',
    'העברת היתר לפיקוח על הבני':                   'היתר',
    'גמר בניה':                                    'היתר',
    'מסירת א. תחילת עבודות':                       'היתר',
    'פעיל':                                        'בקשה להיתר',
    'בקרה מרחבית':                                 'בקשה להיתר',
    'בקרה מרחבית - הוחזר לעורך':                   'בקשה להיתר',
    'עמידה בתנאים מוקדמים לצורך פרסום':            'בקשה להיתר',
    'אי עמידה בתנאי סף':                           'בקשה להיתר',
    'החלטה לאשר בועדה':                            'בקשה להיתר',
    'פתיחת בקשה להיתר':                            'בקשה להיתר',
    'שובץ לישיבת ועדה':                             'בקשה להיתר',
    # Closed without permit — intentionally omitted (maps to '')
    # 'לא פעיל'
    # 'סגירת בקשה - פג תוקף החלטה'
}

_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    ),
}


def _log(msg):
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)


class BartechPermitsAPI:
    def __init__(self, base_url: str, city_name_hebrew: str,
                 permit_types: Optional[Dict[int, str]] = None):
        self.base_url = base_url.rstrip('/')
        self.city_name = city_name_hebrew
        self.permit_types = permit_types if permit_types is not None else PERMIT_TYPES
        self.max_pages: Optional[int] = None  # set to int for testing
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._session.headers['Referer'] = f'{self.base_url}/SearchPermitApplication'

    def scrape(self) -> List[Dict]:
        seen: Dict[str, Dict] = {}
        for type_id, type_label in self.permit_types.items():
            _log(f'TypeOfPermit={type_id} ({type_label})...')
            permits = self._scrape_type(type_id, type_label)
            new = sum(1 for p in permits if p['request_number'] not in seen)
            for p in permits:
                seen.setdefault(p['request_number'], p)
            _log(f'  -> {len(permits)} rows, {new} new (total unique: {len(seen)})')
        return list(seen.values())

    def _scrape_type(self, type_id: int, type_label: str) -> List[Dict]:
        permits = []
        page = 1
        last_page = None
        while True:
            if self.max_pages and page > self.max_pages:
                break
            html, lp = self._fetch_page(type_id, page)
            if last_page is None and lp:
                last_page = lp
                _log(f'  {last_page} pages total')
            if not html or 'לא נמצאו נתונים' in html:
                break
            rows = self._parse_page(html, type_label)
            if not rows:
                break
            permits.extend(rows)
            _log(f'  [{type_id}] page {page}/{last_page or "?"}: {len(rows)} rows')
            if last_page and page >= last_page:
                break
            page += 1
            time.sleep(0.3)
        return permits

    def _fetch_page(self, type_id: int, page: int):
        params = {
            'searchType': 'ByDetails',
            'TypeOfPermit': type_id,
            'g-recaptcha-response': 'x',
            'page': page,
        }
        try:
            resp = self._session.get(
                f'{self.base_url}{RESULTS_PATH}', params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
        except Exception as e:
            _log(f'  [WARN] page {page} type {type_id}: {e}')
            return '', None
        return resp.text, _extract_last_page(resp.text)

    def _parse_page(self, html: str, type_label: str) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        permits = []
        for td in soup.select('td.permit_results_item_1'):
            tr = td.find_parent('tr')
            if not tr:
                continue
            permit = _parse_row(tr, type_label, self.city_name)
            if permit:
                permits.append(permit)
        return permits


def _parse_row(tr, type_label: str, city: str) -> Optional[Dict]:
    first_td = tr.find('td', class_='permit_results_item_1')
    if not first_td:
        return None

    link = first_td.find('a', class_='btn-link')
    entity_num = ''
    if link and link.get('href'):
        entity_num = parse_qs(urlparse(link['href']).query).get('Entity_Number', [''])[0]

    request_date = ''
    for span in first_td.find_all('span', class_='phone'):
        text = span.get_text(strip=True)
        if 'תאריך פתיחה' in text:
            request_date = text.replace('תאריך פתיחה', '').replace('\xa0', '').strip()
            break

    def label(lid):
        el = tr.find(id=lid)
        return el.get_text(strip=True) if el else ''

    status_raw = label('Label10')
    full_address = label('Label11')
    requestor = label('Label13')
    request_type = label('Label14')

    label12 = tr.find(id='Label12')
    block_lot = ''
    if label12:
        # BS4 html.parser lowercases attribute names; try both cases
        tooltip = label12.get('tooltip', '') or label12.get('ToolTip', '')
        raw_text = label12.get_text(strip=True)
        block_lot = _parse_block_lot(tooltip) or _parse_block_lot(raw_text) or raw_text

    if not entity_num:
        return None

    if status_raw and status_raw not in STATUS_MAP and status_raw not in _KNOWN_CLOSED:
        _log(f'  [NEW STATUS] Unmapped: [{status_raw}]')

    return {
        'request_number':     entity_num,
        'request_date':       request_date,
        'full_address':       full_address,
        'city':               city,
        'block_lot':          block_lot,
        'request_type':       request_type,
        'request_category':   type_label,
        'requestor':          requestor,
        'permit_status':      STATUS_MAP.get(status_raw, ''),
        'permit_status_date': '',
        'scrape_status':      'success' if full_address else 'partial',
    }


def _parse_block_lot(tooltip: str) -> str:
    gush = re.search(r'גוש:\s*(\d+)', tooltip)
    helka = re.search(r'חלקה:\s*(\d+)', tooltip)
    if gush and helka:
        return f'{gush.group(1)}-{helka.group(1)}'
    return ''


def _extract_last_page(html: str) -> Optional[int]:
    m = re.search(r'מתוך <span>(\d+)</span>', html)
    return int(m.group(1)) if m else None
