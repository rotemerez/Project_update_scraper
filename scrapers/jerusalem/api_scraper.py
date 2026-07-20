"""
Jerusalem municipal permit scraper -- direct REST API, no Selenium.

Two separate backend hosts, found via static JS bundle analysis
(ykpubdata.jerusalem.muni.il, React SPA) and confirmed with live network
captures from the office network on 2026-07-16:

  1. jergisinfohub.jerusalem.muni.il -- GIS info-hub REST API behind the
     "מידע תכנוני מקיף" search page. CONFIRMED LIVE:
       GET /Services/api/MetaDataObjectsDetails/1?gush=X&helka=Y&street=&house=&taba=&migrash=
     returns the רישוי בניה (gisObjectName="RishuiBniya") list for a parcel --
     one row per תיק, fields: tik_num, taarih_ptiha (open date), sug_bakasha
     (request type), r_status/r_taarih_status (רישוי status + date),
     p_taarih_status (פיקוח date, no status text), shimush, mevakesh, address.

  2. jerbasicserviceapi.jerusalem.muni.il -- generic stored-procedure executor
     used by the React SPA's per-תיק drill-down pages:
       POST /api/Db/ExecuteGetJSON
       body: {"ProcName": <int>, "Cnn": "cnnGisYk", "Parameters": {...}}
     Proc IDs mapped from the JS bundle (see outputs/debug_jerusalem_main.js):
       242700437 fetchTikRushiData                      -- תיק search (CONFIRMED
                 LIVE for exact misparTik lookup, schema: ID/tik_num/status_code/
                 teurStatus/taarih_status/sugbakasha_code/teurSugbakasha/mahut_bakasha)
       242700473 getProcessesContentPikuahBniaData(TikNum) -- פיקוח stage table.
                CONFIRMED LIVE: rows have stepCodeText (stage description,
                e.g. "פתיחת תיק פיקוח", "ביקור באתר -אינטרנט", "הופק טופס 2",
                "מסירת טופס 4"), stepStatusText ("מתוכנן"/"בוצע"),
                planDateStr, execDateStr.
       242700475 getProcessesTitlePikuahBniaData(TikNum)
       242700451 getProcessesContentData(SystemID, TikNum)  -- רישוי stage table
       242700448 getProcessesTitleData(SystemID, TikNum)

Both hosts were transiently blocked by an Akamai WAF during initial recon
(2026-07-16, non-office network) but responded fine on retest minutes later
without any network change on our end -- looks like a burst rate-limit, not a
persistent office-only gate. If a future run hits repeated 403s, throttle
requests and retry before assuming office-IP access is required.

No citywide "recent permits" feed exists -- every proc/endpoint requires a
search key (gush/helka, street, תיק number, or תב"ע number). Primary strategy
is to iterate (gush, helka) pairs already tracked in the projects export
(scrape_parcels). A secondary sweep_by_tik_number() walks תיק numbers
sequentially (format "YYYY/NNNN.SS", confirmed live) via fetchTikRushiData to
catch permits not yet in the projects export -- but that proc's thin schema
(ID/tik_num/status_code/teurStatus/taarih_status/sugbakasha_code/
teurSugbakasha/mahut_bakasha) has no gush/helka/address/mevakesh, so sweep
results are necessarily partial (status only) until a parcel lookup can be
cross-referenced by hand.

Output schema (same as Complot/Bartech):
  request_number, request_date, full_address, city, block_lot, migrash,
  request_type, request_category, requestor, bakasha_description,
  shimush_ikari, unit_count,
  permit_status, permit_status_date, scrape_status
"""

import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

GIS_HOST = 'https://jergisinfohub.jerusalem.muni.il'
RISHUI_BNIYA_PATH = '/Services/api/MetaDataObjectsDetails/1'

API_HOST = 'https://jerbasicserviceapi.jerusalem.muni.il'
EXECUTE_GET_JSON_PATH = '/api/Db/ExecuteGetJSON'

PROC_PIKUAH_CONTENT = 242700473  # getProcessesContentPikuahBniaData(TikNum)
PROC_TIK_RUSHI = 242700437       # fetchTikRushiData -- exact-match misparTik lookup

CITY = 'ירושלים'

# r_status (רישוי בניה list, jergisinfohub) -> our vocabulary. Populated from
# observed data; add more after each run (see _log '[NEW STATUS]').
STATUS_MAP: Dict[str, str] = {
    'הגשה מקוונת הושלמה':               'בקשה להיתר',
    'נפתח תיק רישוי':                   'בקשה להיתר',
    'חידוש טיפול בבקשה':                'בקשה להיתר',
    'נדונה בוועדת המשנה':               'בקשה להיתר',
    'נדונה ברשות הרישוי':               'בקשה להיתר',
    'נדונה בועדת ערר':                  'בקשה להיתר',  # under appeal -- still open, not a forward milestone
    'התקבל ערר':                        'בקשה להיתר',  # appeal received -- still open
    'שולמה מקדמה':                      'בקשה להיתר',
    'תום תקופת פרסום':                  'בקשה להיתר',
    'נוסח פרסום אושר':                  'בקשה להיתר',
    'תחילת פרסום הבקשה להקלה':          'בקשה להיתר',
    'פורסמה בקשה להקלה':                'בקשה להיתר',
    'ממתין לאישור נוסח פרסום':          'בקשה להיתר',
    'התקבלה בקשה לדיון המועצה':         'בקשה להיתר',
    'השלמת הודעות לפני תקנה 36':        'בקשה להיתר',
    'תחילת הודעות לפני תקנה 36':        'בקשה להיתר',
    'הוכנה טיוטת היתר בניה':            'היתר בתנאים',
    'אושר ע"י מהנדס העיר':              'היתר בתנאים',
    'התקבל תיק ורוד / מסמכים חתומים':   'היתר',  # signed-documents handoff, pre-issuance
    'הופק-הוצא היתר בניה':              'היתר',
    'הופק היתר מוארך':                  'היתר',  # extended permit issued
    'הבקשה נסגרה':                      '',  # closed without a permit -- not a tracked milestone
    'הבקשה נגנזה':                      '',  # shelved/archived without a permit -- not a tracked milestone
}

STATUS_ORDER = ['בקשה להיתר', 'היתר בתנאים', 'היתר', 'טופס 4']

# תהליך פיקוח stepCodeText -> טופס 4 milestone (colleague: "'מסירת טופס 4'
# שים לב לסטטוס בוצע לעומת מתוכנן / חתימה על תעודת גמר"). Confirmed live
# schema (2026-07-16): stepCodeText values seen include "פתיחת תיק פיקוח",
# "ביקור באתר -אינטרנט", "הופק טופס 2" -- none of which are טופס 4, so this
# list is still built from the colleague's description + earlier screenshots,
# not yet a live-confirmed טופס 4 row. Add variants here as they're observed.
PIKUAH_OCCUPANCY_STAGE_SUBSTRINGS = ['מסירת טופס 4', 'הפקת טופס 4', 'תעודת גמר']

_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    ),
    'Origin': 'https://ykpubdata.jerusalem.muni.il',
    'Referer': 'https://ykpubdata.jerusalem.muni.il/',
}


def _log(msg):
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)


class JerusalemPermitsAPI:
    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._unmapped_statuses_seen = set()

    # -- blocked-vs-not-found handling ---------------------------------------
    #
    # A raw fetch method returns (outcome, data): 'ok' means a genuine backend
    # response (data may legitimately be empty -- a real "nothing here").
    # 'blocked'/'error' means the request itself failed (WAF/rate-limit 403,
    # timeout, malformed response) and tells us NOTHING about whether real
    # data exists -- confirmed live 2026-07-17: a burst of concurrent requests
    # tripped a 403 block on jerbasicserviceapi.jerusalem.muni.il that the
    # sweep's miss-streak counter silently absorbed as hundreds of genuine
    # "not found" results, corrupting an entire year's sweep. Every caller
    # must treat blocked/error as inconclusive, never as a confirmed miss --
    # same distinction already enforced in scrapers/tel_aviv/scraper.py.

    def _with_retry(self, raw_fetch, label: str, max_retries: int = 3):
        outcome, data = 'error', None
        for attempt in range(1, max_retries + 1):
            outcome, data = raw_fetch()
            if outcome == 'ok':
                return outcome, data
            cooldown = min(30, 5 * attempt)
            _log(f'  [RETRY {attempt}/{max_retries}] {label}: {outcome} -- backing off {cooldown}s')
            time.sleep(cooldown)
        _log(f'  [GIVE UP] {label} still {outcome} after {max_retries} retries -- inconclusive, not a confirmed miss')
        return outcome, data

    def scrape_parcels(self, parcel_pairs: List[Tuple[str, str]]) -> List[Dict]:
        """
        Fetch רישוי בניה rows for each (gush, helka) pair, map to the common
        schema, then enrich each with the תהליך פיקוח stage table looking for
        an occupancy (טופס 4) date/status.
        """
        seen: Dict[str, Dict] = {}
        for gush, helka in parcel_pairs:
            outcome, rows = self._with_retry(
                lambda: self._fetch_rishui_bniya(gush, helka), f'gush={gush} helka={helka}')
            if outcome != 'ok':
                _log(f'  [WARN] gush={gush} helka={helka}: giving up, not a confirmed empty result -- skipping')
                continue
            for raw in rows:
                permit = self._map_row(raw, gush, helka)
                if permit['request_number']:
                    seen.setdefault(permit['request_number'], permit)
            _log(f'  Parcel {gush}-{helka}: {len(rows)} rows (total unique: {len(seen)})')
            time.sleep(0.3)
        return self._enrich_with_pikuah(list(seen.values()))

    def _fetch_rishui_bniya(self, gush, helka) -> Tuple[str, List[Dict]]:
        params = {'street': '', 'house': '', 'gush': gush, 'helka': helka, 'taba': '', 'migrash': ''}
        try:
            resp = self._session.get(f'{GIS_HOST}{RISHUI_BNIYA_PATH}', params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            outcome = 'blocked' if status in (403, 429) else 'error'
            _log(f'  [WARN] gush={gush} helka={helka}: {e}')
            return outcome, []
        except Exception as e:
            _log(f'  [WARN] gush={gush} helka={helka}: {e}')
            return 'error', []
        if data.get('gisObjectName') != 'RishuiBniya':
            _log(f'  [WARN] gush={gush} helka={helka}: unexpected gisObjectName={data.get("gisObjectName")!r}')
        return 'ok', data.get('gisDataObject', [])

    def _map_row(self, raw: Dict, gush, helka) -> Dict:
        r_status = (raw.get('r_status', '') or '').strip()
        if r_status and r_status not in STATUS_MAP and r_status not in self._unmapped_statuses_seen:
            self._unmapped_statuses_seen.add(r_status)
            _log(f'  [NEW STATUS] Unmapped r_status: [{r_status}]')

        return {
            'request_number':      raw.get('tik_num', '') or '',
            'request_date':        raw.get('taarih_ptiha', '') or '',
            'full_address':        (raw.get('address', '') or '').strip(),
            'city':                CITY,
            'block_lot':           f'{gush}-{helka}',
            'migrash':             '',
            'request_type':        raw.get('sug_bakasha', '') or '',
            'request_category':    '',
            'requestor':           raw.get('mevakesh', '') or '',
            'bakasha_description': '',
            'shimush_ikari':       raw.get('shimush', '') or '',
            'unit_count':          '',
            'permit_status':       STATUS_MAP.get(r_status, ''),
            'permit_status_date':  raw.get('r_taarih_status', '') or '',
            'scrape_status':       'success' if raw.get('address') else 'partial',
            '_tik_num':            raw.get('tik_num', '') or '',
        }

    def _enrich_with_pikuah(self, permits: List[Dict]) -> List[Dict]:
        total = len(permits)
        for i, permit in enumerate(permits):
            tik_num = permit.pop('_tik_num', '')
            if not tik_num:
                continue
            outcome, stages = self._with_retry(
                lambda: self._fetch_pikuah_stages(tik_num), f'pikuah stages tik={tik_num}')
            if outcome != 'ok':
                _log(f'  [WARN] pikuah stages tik={tik_num}: giving up -- occupancy status left as-is, not confirmed absent')
            else:
                occ_status, occ_date = _pikuah_occupancy(stages)
                if occ_status:
                    permit['permit_status'] = occ_status
                    permit['permit_status_date'] = occ_date
            if (i + 1) % 200 == 0:
                _log(f'  [{i + 1}/{total}] pikuah stages fetched')
            time.sleep(0.2)
        return permits

    def _fetch_pikuah_stages(self, tik_num: str) -> Tuple[str, List[Dict]]:
        body = {
            'ProcName': PROC_PIKUAH_CONTENT,
            'Cnn': 'cnnGisYk',
            'Parameters': {'TikNum': tik_num},
        }
        try:
            resp = self._session.post(f'{API_HOST}{EXECUTE_GET_JSON_PATH}', json=body, timeout=30)
            resp.raise_for_status()
            return 'ok', (resp.json() or [])
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            outcome = 'blocked' if status in (403, 429) else 'error'
            _log(f'  [WARN] pikuah stages tik={tik_num}: {e}')
            return outcome, []
        except Exception as e:
            _log(f'  [WARN] pikuah stages tik={tik_num}: {e}')
            return 'error', []

    def sweep_by_tik_number(self, years: List[int], max_number: int = 9999,
                             sub_indices: Tuple[int, ...] = (0, 1),
                             miss_streak_limit: int = 30,
                             known_tik_nums: Optional[set] = None) -> List[Dict]:
        """
        Walk תיק numbers sequentially per year ("YYYY/NNNN.SS", confirmed live
        format) via fetchTikRushiData to discover permits not present in the
        projects export. Skips numbers already covered by scrape_parcels()
        (pass its result's request_number set as known_tik_nums) -- still
        walks past them for streak-counting purposes, since a known number
        existing doesn't tell us whether nearby unknown ones do.

        Each (year, number) tries every sub_indices entry unconditionally (a
        תיק can start at .00 or .01 -- both seen live, e.g. historical filings
        that skip straight to .01 with no .00) rather than stopping at the
        first miss. Moves to the next year after miss_streak_limit consecutive
        numbers with zero hits across all subs.

        Results are necessarily partial: fetchTikRushiData's schema has no
        gush/helka/address/mevakesh (see module docstring) -- block_lot and
        full_address are left blank rather than guessed, and scrape_status is
        always 'partial' so these rows are visibly flagged for manual
        parcel lookup before they can be matched against tracked projects.

        A blocked/error fetch (WAF rate-limit, timeout) is retried with
        backoff and, if still unresolved, treated as INCONCLUSIVE -- it
        affects the miss streak neither way (not a hit, not a miss). Every
        inconclusive תיק number is logged (`[GIVE UP]` per number, a summary
        count at the end) for manual re-checking, rather than being silently
        absorbed as a genuine "not found" the way a plain empty-list return
        would be. Confirmed live 2026-07-17: a rate-limit block produced
        hundreds of real 403s that the old code counted as consecutive
        misses, ending two years' sweeps early on fabricated "nothing here"
        data.
        """
        known_tik_nums = known_tik_nums or set()
        results: List[Dict] = []
        inconclusive: List[str] = []
        for year in years:
            streak = 0
            found_count = 0
            for number in range(1, max_number + 1):
                hit_this_number = False
                any_inconclusive = False
                for sub in sub_indices:
                    tik_num = f'{year}/{number:04d}.{sub:02d}'
                    if tik_num in known_tik_nums:
                        hit_this_number = True
                        continue
                    outcome, rows = self._with_retry(
                        lambda: self._fetch_tik_rushi(tik_num), f'tikRushi {tik_num}')
                    time.sleep(0.2)
                    if outcome != 'ok':
                        any_inconclusive = True
                        inconclusive.append(tik_num)
                        continue
                    if not rows:
                        continue  # this sub-index doesn't exist -- a later one still might
                                  # (e.g. old filings that start at .01 with no .00, see docstring)
                    hit_this_number = True
                    for raw in rows:
                        results.append(self._map_thin_row(raw))
                        found_count += 1
                if hit_this_number:
                    streak = 0
                elif any_inconclusive:
                    pass  # inconclusive -- doesn't count toward the streak either way
                else:
                    streak += 1
                    if streak >= miss_streak_limit:
                        _log(f'  [{year}] stopping at #{number}: {miss_streak_limit} consecutive misses '
                             f'({found_count} found this year)')
                        break
            else:
                _log(f'  [{year}] reached max_number={max_number} ({found_count} found this year)')
        if inconclusive:
            _log(f'[WARN] {len(inconclusive)} תיק numbers were inconclusive (blocked/error even after '
                 f'retries) across the whole sweep -- re-check these manually, they are NOT confirmed misses')
        return results

    def _fetch_tik_rushi(self, mispar_tik: str) -> Tuple[str, List[Dict]]:
        body = {
            'ProcName': PROC_TIK_RUSHI,
            'Cnn': 'cnnGisYk',
            'Parameters': {
                'misparTik': mispar_tik, 'gush': None, 'helka': None,
                'rehovCode': None, 'mispBait': None, 'mezahe': None,
                'migrash': None, 'systemId': '26400046',
            },
        }
        try:
            resp = self._session.post(f'{API_HOST}{EXECUTE_GET_JSON_PATH}', json=body, timeout=30)
            resp.raise_for_status()
            return 'ok', (resp.json() or [])
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            outcome = 'blocked' if status in (403, 429) else 'error'
            _log(f'  [WARN] tikRushi {mispar_tik}: {e}')
            return outcome, []
        except Exception as e:
            _log(f'  [WARN] tikRushi {mispar_tik}: {e}')
            return 'error', []

    def _map_thin_row(self, raw: Dict) -> Dict:
        status_text = (raw.get('teurStatus', '') or '').strip()
        if status_text and status_text not in STATUS_MAP and status_text not in self._unmapped_statuses_seen:
            self._unmapped_statuses_seen.add(status_text)
            _log(f'  [NEW STATUS] Unmapped teurStatus: [{status_text}]')

        return {
            'request_number':      raw.get('tik_num', '') or '',
            'request_date':        '',  # not in this endpoint's schema -- see module docstring
            'full_address':        '',
            'city':                CITY,
            'block_lot':           '',
            'migrash':             '',
            'request_type':        raw.get('teurSugbakasha', '') or '',
            'request_category':    '',
            'requestor':           '',
            'bakasha_description': raw.get('mahut_bakasha', '') or '',
            'shimush_ikari':       '',
            'unit_count':          '',
            'permit_status':       STATUS_MAP.get(status_text, ''),
            'permit_status_date':  raw.get('taarih_status', '') or '',
            'scrape_status':       'partial',  # always -- no parcel/address data from this endpoint
        }


def _pikuah_occupancy(stages: List[Dict]) -> Tuple[str, str]:
    """
    Scan raw פיקוח stage rows (getProcessesContentPikuahBniaData) for the
    טופס 4 milestone. Only counts a stage whose status is 'בוצע' (done), not
    'מתוכנן' (planned) -- per colleague's explicit note. Returns ('', '')
    rather than guessing when nothing recognizable is found.
    """
    for stage in stages:
        desc = stage.get('stepCodeText', '') or ''
        status = stage.get('stepStatusText', '') or ''
        date = stage.get('execDateStr', '') or ''
        if not desc or status != 'בוצע':
            continue
        if any(sub in desc for sub in PIKUAH_OCCUPANCY_STAGE_SUBSTRINGS):
            return 'טופס 4', date
    return '', ''
