"""
Tel Aviv municipal permit scraper -- plain ArcGIS REST API, no browser, no reCAPTCHA.

Confirmed live 2026-07-17. Two independent public, unauthenticated endpoints:

  1. gisn.tel-aviv.gov.il/arcgis/rest/services/WM/IView2WM/MapServer/772
     "בקשות והיתרי בניה" -- an ArcGIS Feature Layer (standard /query REST API,
     supportsPagination=true, maxRecordCount=2000, 10,538 total rows as of
     first recon). This is the primary permit-request source: one row per
     (request, building) pair -- a request touching multiple buildings
     (corner lots) gets one row per building, same request data duplicated.
     Fields used: request_num, open_request/permission_date (epoch ms),
     occupation/finished (string DD/MM/YYYY), yechidot_diyur, sug_bakasha,
     tochen_bakasha, addresses, ms_tik_binyan.

     permit_status is derived from which date fields are populated, NOT from
     building_stage -- building_stage is a per-BUILDING rollup of "last
     licensing activity" (i.e. it reflects whatever the most advanced permit
     on that building is, not necessarily *this* request), so it would
     over-report status for older/superseded requests on an active building.
     The date fields are per-request and unambiguous:
       occupation filled      -> 'טופס 4'
       else permission_date   -> 'היתר'
       else open_request      -> 'בקשה להיתר'
     (no source field maps to the intermediate 'היתר בתנאים' tier here.)

  2. handasa.tel-aviv.gov.il WCF list service -- resolves a building's גוש/חלקה
     from its תיק בניין number (layer 772's ms_tik_binyan field), found via a
     live DevTools capture of the (also public) building-archive site at
     archive-binyan.tel-aviv.gov.il (which just redirects to handasa.tel-aviv.gov.il):
       GET https://handasa.tel-aviv.gov.il/_vti_bin/TlvSP2013PublicSite/TlvList.svc/
           GetListItemsByFieldFilterStringWithQuery/{encoded_site_base}/{list_title}/
           null/LinkTitle/{tik_binyan}/null
     Confirmed anonymous (no cookies/session needed), returns `[]` (HTTP 200)
     for an unknown תיק בניין rather than erroring. The response's
     EngFolderBlocksParcels field is a comma-joined "{gush}_{helka}" list (one
     entry per address on the building, often literally duplicated) -- parsed
     into (gush, helka) pairs and formatted as the project's "gush-helka;
     gush-helka" scraped-data convention (see transform/gush_helka.py) so the
     matcher's primary gush-helka matching path applies (no need to lean on
     address-only matching for this city).

     One WCF call per *distinct* ms_tik_binyan value (cached), not per permit
     row -- the same building recurs across many permits filed over the years.

Output schema (same as every other city's scraper):
  request_number, request_date, full_address, city, block_lot, migrash,
  request_type, request_category, requestor, bakasha_description,
  shimush_ikari, unit_count, permit_status, permit_status_date, scrape_status
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

CITY = 'תל אביב יפו'

LAYER_QUERY_URL = 'https://gisn.tel-aviv.gov.il/arcgis/rest/services/WM/IView2WM/MapServer/772/query'
LAYER_OUT_FIELDS = [
    'request_num', 'open_request', 'permission_date', 'permission_num',
    'yechidot_diyur', 'sug_bakasha', 'tochen_bakasha', 'finished', 'occupation',
    'addresses', 'ms_tik_binyan',
]
PAGE_SIZE = 2000

# WCF endpoint -- path segments confirmed live via DevTools capture of
# archive-binyan.tel-aviv.gov.il's building-metadata lookup (2026-07-17).
WCF_BASE = 'https://handasa.tel-aviv.gov.il/_vti_bin/TlvSP2013PublicSite/TlvList.svc'
WCF_SITE_BASE_ENCODED = 'https;3A;2F;2Fhandasa.tel-aviv.gov.il;2F'
WCF_LIST_TITLE_ENCODED = '%D7%9E%D7%90%D7%A4%D7%99%D7%99%D7%A0%D7%99%20%D7%AA%D7%99%D7%A7%20%D7%91%D7%A0%D7%99%D7%99%D7%9F'

_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    ),
}


def _log(msg):
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)


def _epoch_ms_to_ddmmyyyy(val) -> str:
    if not val:
        return ''
    try:
        return datetime.fromtimestamp(int(val) / 1000, tz=timezone.utc).strftime('%d/%m/%Y')
    except (ValueError, OSError, OverflowError):
        return ''


class TelAvivGisAPI:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._gush_helka_cache: Dict[str, str] = {}

    # -- layer 772: permit requests -------------------------------------------

    def _fetch_page(self, offset: int) -> List[Dict]:
        params = {
            'where': '1=1',
            'outFields': ','.join(LAYER_OUT_FIELDS),
            'returnGeometry': 'false',
            'f': 'json',
            'resultOffset': offset,
            'resultRecordCount': PAGE_SIZE,
            'orderByFields': 'oid_permit',
        }
        resp = self._session.get(LAYER_QUERY_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            raise RuntimeError(f'ArcGIS query error at offset={offset}: {data["error"]}')
        return [f['attributes'] for f in data.get('features', [])]

    def fetch_all_raw_rows(self) -> List[Dict]:
        rows: List[Dict] = []
        offset = 0
        while True:
            page = self._fetch_page(offset)
            if not page:
                break
            rows.extend(page)
            _log(f'  Fetched {len(rows)} rows so far (offset={offset})')
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return rows

    # -- WCF building -> gush/helka lookup ------------------------------------

    def _resolve_gush_helka(self, tik_binyan: str) -> str:
        if tik_binyan in self._gush_helka_cache:
            return self._gush_helka_cache[tik_binyan]
        url = (f'{WCF_BASE}/GetListItemsByFieldFilterStringWithQuery/'
               f'{WCF_SITE_BASE_ENCODED}/{WCF_LIST_TITLE_ENCODED}/null/LinkTitle/{tik_binyan}/null')
        try:
            resp = self._session.get(url, timeout=30)
            resp.raise_for_status()
            items = resp.json()
        except Exception as e:
            _log(f'  [WARN] WCF lookup failed for tik_binyan={tik_binyan}: {e}')
            self._gush_helka_cache[tik_binyan] = ''
            return ''

        pairs = set()
        for item in items:
            for field in item.get('Fields', []):
                if field.get('InternalName') == 'EngFolderBlocksParcels':
                    raw = field.get('Value', '') or ''
                    for part in raw.split(','):
                        part = part.strip()
                        if '_' in part:
                            gush, _, helka = part.partition('_')
                            gush, helka = gush.strip(), helka.strip()
                            if gush and helka:
                                pairs.add((gush, helka))
        result = '; '.join(f'{g}-{h}' for g, h in sorted(pairs))
        self._gush_helka_cache[tik_binyan] = result
        return result

    # -- merge + map -----------------------------------------------------------

    def _merge_by_request_num(self, raw_rows: List[Dict]) -> Dict[str, List[Dict]]:
        groups: Dict[str, List[Dict]] = {}
        for row in raw_rows:
            request_num = row.get('request_num')
            if request_num is None:
                continue
            groups.setdefault(str(request_num), []).append(row)
        return groups

    def _permit_status(self, row: Dict) -> Tuple[str, str]:
        occupation = (row.get('occupation') or '').strip()
        if occupation:
            return 'טופס 4', occupation
        if row.get('permission_date'):
            return 'היתר', _epoch_ms_to_ddmmyyyy(row['permission_date'])
        if row.get('open_request'):
            return 'בקשה להיתר', _epoch_ms_to_ddmmyyyy(row['open_request'])
        return '', ''

    def _map_group(self, request_num: str, rows: List[Dict]) -> Dict:
        primary = rows[0]

        addresses = []
        for row in rows:
            for addr in (row.get('addresses') or '').split(','):
                addr = addr.strip()
                if addr and addr not in addresses:
                    addresses.append(addr)

        tik_binyans = sorted({
            str(row['ms_tik_binyan']) for row in rows
            if row.get('ms_tik_binyan')
        })
        gh_pairs = [self._resolve_gush_helka(tb) for tb in tik_binyans]
        block_lot = '; '.join(p for p in gh_pairs if p)

        permit_status, permit_status_date = self._permit_status(primary)

        return {
            'request_number':      request_num,
            'request_date':        _epoch_ms_to_ddmmyyyy(primary.get('open_request')),
            'full_address':        ', '.join(addresses),
            'city':                CITY,
            'block_lot':           block_lot,
            'migrash':             '',
            'request_type':        (primary.get('sug_bakasha') or '').strip(),
            'request_category':    '',
            'requestor':           '',
            'bakasha_description': (primary.get('tochen_bakasha') or '').strip(),
            'shimush_ikari':       '',
            'unit_count':          str(primary.get('yechidot_diyur') or ''),
            'permit_status':       permit_status,
            'permit_status_date':  permit_status_date,
            'scrape_status':       'success' if addresses else 'partial',
        }

    def scrape_all(self) -> List[Dict]:
        raw_rows = self.fetch_all_raw_rows()
        _log(f'[INFO] {len(raw_rows)} raw rows fetched, merging by request_num')
        groups = self._merge_by_request_num(raw_rows)
        _log(f'[INFO] {len(groups)} distinct request_num groups -- resolving gush/helka per building')

        permits = []
        total = len(groups)
        for i, (request_num, rows) in enumerate(groups.items()):
            permits.append(self._map_group(request_num, rows))
            if (i + 1) % 500 == 0:
                _log(f'  [{i + 1}/{total}] permits mapped '
                     f'({len(self._gush_helka_cache)} distinct buildings resolved so far)')
            time.sleep(0.05)
        return permits
