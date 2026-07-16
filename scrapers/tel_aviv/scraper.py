"""
Tel Aviv (רישוי בנייה מקוון) municipal permit scraper -- browser automation.

Unlike Complot/Bartech (plain `requests`), Tel Aviv's public search API is
gated by a gateway-enforced Google reCAPTCHA Enterprise v3 token
(`X-Client-Assertion` header) that cannot be bypassed with a placeholder
value -- confirmed via recon: docs/tlv_permit_api_findings.md,
docs/tlv_permit_api_findings2.md. This scraper drives the real Angular
search form with a visible Chrome browser so the page's own JS mints a
valid token, then captures the resulting XHR response via an injected
XMLHttpRequest prototype wrapper (the JSON response has more fields than
the rendered results table).

IMPORTANT: must run non-headless. Confirmed by live dry-run: a headless
session gets a syntactically valid but server-rejected token (`400 Invalid
assertion`); the identical query in a real window succeeds (`200`).

Known schema gap: request_date, request_category, requestor,
bakasha_description, shimush_ikari, unit_count are not present in the
public search response -- they live behind an Azure B2C login-gated detail
page (`/api/ResidentLicensing/Request/{id}` returns 401 unauthenticated).
Left blank rather than fabricated, per project data-integrity rules.
"""
import json
import random
import time
import winreg
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import setuptools  # noqa: F401  -- provides distutils shim on Python 3.12+/3.13
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SEARCH_URL = 'https://rishuybniya.tel-aviv.gov.il/resident-licensing/licensing-request-pages/request-search'
TARGET_URL_FRAGMENT = 'ResidentLicensing/Request/getRequest'

FORM_FIELDS = [
    'licenseId', 'submissionId', 'streetCode', 'houseNumber',
    'entrance', 'blockNumber', 'parcelNumber',
]

_CAPTURE_SCRIPT = """
window.__capturedResponses = [];
(function() {
    const origOpen = XMLHttpRequest.prototype.open;
    const origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function(method, url) {
        this.__capturedUrl = url;
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function(body) {
        this.addEventListener('load', function() {
            if (this.__capturedUrl && this.__capturedUrl.indexOf('%s') !== -1) {
                window.__capturedResponses.push({
                    url: this.__capturedUrl, status: this.status, body: this.responseText
                });
            }
        });
        return origSend.apply(this, arguments);
    };
})();
""" % TARGET_URL_FRAGMENT

# Status vocabulary is unmapped -- only 2 real values seen in recon so far
# ("בדיקה מרחבית מחלקת רישוי", "פניה נדחתה"). New values surface via the
# [NEW STATUS] log line below; classify and add here once enough real scrape
# data exists, same iterative pattern as Bartech's STATUS_MAP.
STATUS_MAP: Dict[str, str] = {}


def _log(msg: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')


def _detect_chrome_major_version() -> Optional[int]:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Google\Chrome\BLBeacon')
        version, _ = winreg.QueryValueEx(key, 'version')
        return int(version.split('.')[0])
    except OSError:
        return None


class TelAvivPermitsBrowserScraper:
    """Browser-automation scraper for Tel Aviv's public permit search."""

    def __init__(self, city_name_hebrew: str = 'תל אביב יפו', restart_every: int = 100):
        self.city_name = city_name_hebrew
        self.restart_every = restart_every
        self._query_count = 0
        self._form_loaded_once = False
        self.driver = None

    # -- browser lifecycle ---------------------------------------------------

    def _init_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--window-size=1400,1000')
        version_main = _detect_chrome_major_version()
        driver = (uc.Chrome(options=options, version_main=version_main)
                  if version_main else uc.Chrome(options=options))
        driver.set_page_load_timeout(30)
        return driver

    def _restart_driver(self):
        _log(f'[Browser restart at query {self._query_count}]')
        self.close()
        time.sleep(2)
        self.driver = self._init_driver()
        self._form_loaded_once = False

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # -- form interaction -----------------------------------------------------

    def _load_search_form(self):
        """
        Get back to the search form before every query. Angular replaces the
        form with a results view after a search completes, so the previous
        query's form elements go stale -- a persistent single-page-form
        approach fails on the second query onward (confirmed by smoke test).

        Prefers clicking the results page's own "חיפוש חדש" (new search)
        button -- an in-app Angular route change, not a full page reload --
        over `driver.get()`. A real user doing several searches in one visit
        clicks "new search"; they don't reload the whole SPA bundle each
        time, and reCAPTCHA Enterprise's risk scoring degrades faster the
        more automated a session's traffic pattern looks (confirmed live:
        repeated full reloads in a tight loop got rejected after the first
        couple of queries). Falls back to a full `driver.get()` for the very
        first load of a session and after a browser restart.
        """
        if self._form_loaded_once and self._click_button_by_text('חיפוש חדש'):
            time.sleep(1.5)
        else:
            self.driver.get(SEARCH_URL)
            self._form_loaded_once = True
        WebDriverWait(self.driver, 30).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        WebDriverWait(self.driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[formcontrolname="entrance"]'))
        )
        # The field being present in the DOM doesn't mean Angular's reactive
        # FormGroup has finished wiring/default-populating it yet -- filling
        # too early either lands before binding exists or gets silently
        # overwritten by Angular's own init logic (observed live: field
        # visibly stayed at "0" despite send_keys appearing to succeed).
        time.sleep(2)
        self.driver.execute_script(_CAPTURE_SCRIPT)

    def _click_button_by_text(self, text: str) -> bool:
        for b in self.driver.find_elements(By.TAG_NAME, 'button'):
            if b.text.strip() == text:
                self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', b)
                time.sleep(0.2)
                try:
                    b.click()
                except Exception:
                    self.driver.execute_script('arguments[0].click();', b)
                return True
        return False

    def _fill_field(self, name: str, value: str):
        value = str(value)
        el = self.driver.find_element(By.CSS_SELECTOR, f'[formcontrolname="{name}"]')
        el.clear()
        el.send_keys(value)
        if el.get_attribute('value') == value:
            return
        # send_keys didn't stick (observed live: Angular's own form-init can
        # race and overwrite a too-early fill back to "0") -- fall back to
        # setting .value directly and dispatching the events Angular's
        # matInput listens on, then verify again.
        self.driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            el, value,
        )
        if el.get_attribute('value') != value:
            raise RuntimeError(
                f'Failed to fill formcontrolname="{name}" with "{value}" '
                f'(value stuck at "{el.get_attribute("value")}")'
            )

    def _click_search(self):
        if self._click_button_by_text('הבנתי'):
            time.sleep(1)
        if not self._click_button_by_text('איתור'):
            raise RuntimeError('Search button not found on page')

    def _submit_and_capture(self, timeout: int = 20) -> Optional[dict]:
        self.driver.execute_script('window.__capturedResponses = [];')
        self._click_search()
        deadline = time.time() + timeout
        while time.time() < deadline:
            captured = self.driver.execute_script('return window.__capturedResponses;')
            if captured:
                return captured[0]
            time.sleep(0.4)
        return None

    def _maybe_restart(self):
        self._query_count += 1
        if self.restart_every and self._query_count % self.restart_every == 0:
            self._restart_driver()

    # -- record parsing ---------------------------------------------------

    def _parse_response(self, response: Optional[dict], block_lot_hint: str = '') -> Tuple[str, List[Dict]]:
        """
        Classify a captured response and extract records.

        Returns (outcome, records):
          'ok'      -- a genuine backend response; `records` may legitimately
                       be empty (a real "no permit at this parcel/number").
          'blocked' -- the reCAPTCHA gateway rejected the request (Missing/
                       Invalid assertion). This is NOT a real "not found" --
                       treating it as one would silently truncate a scan at a
                       false ceiling (confirmed live: 8/8 rejected queries
                       were logged as "0 permits found" before this fix).
          'error'   -- no response captured, or any other malformed/failed
                       response (e.g. a downstream 500).
        """
        if response is None:
            return 'error', []
        if response.get('status') == 400 and isinstance(response.get('body'), str) \
                and 'assertion' in response['body'].lower():
            _log(f'[BLOCKED] reCAPTCHA gateway rejected the request: {response["body"]}')
            return 'blocked', []
        try:
            body = json.loads(response['body'])
        except (KeyError, ValueError, TypeError):
            _log(f'[WARN] Unparseable response body: {response}')
            return 'error', []
        if response.get('status') != 200 or body.get('status') != 1:
            _log(f'[WARN] Search failed: HTTP {response.get("status")}, body {body}')
            return 'error', []

        data = body.get('data', {})
        records = [self._to_permit_dict(row, block_lot_hint)
                   for row in data.get('residentLicenseRequest', [])]
        # data['requestDataList'] = information/online-submission requests --
        # not part of the permit process itself, not carried into the
        # matcher's permit schema.
        return 'ok', records

    def _to_permit_dict(self, row: dict, block_lot_hint: str) -> Dict:
        request_number = row.get('licenseNumber') or row.get('dataNumber') or ''
        raw_status = row.get('requestStatus', '')
        mapped_status = STATUS_MAP.get(raw_status)
        if raw_status and mapped_status is None:
            _log(f'[NEW STATUS] "{raw_status}" -- not yet classified in STATUS_MAP')
        return {
            'request_number':      request_number,
            'request_date':        '',       # not in public search response (needs B2C login)
            'full_address':        row.get('address', ''),
            'city':                self.city_name,
            'block_lot':           block_lot_hint,
            'request_type':        row.get('requestType', ''),
            'request_category':    '',       # not in public search response
            'requestor':           '',       # not in public search response
            'bakasha_description': '',       # not in public search response
            'shimush_ikari':       '',       # not in public search response
            'unit_count':          '',       # not in public search response
            'permit_status':       mapped_status or '',
            'permit_status_date':  '',       # not in public search response
            'scrape_status':       'success' if request_number else 'partial',
        }

    # -- retry-aware querying -----------------------------------------------

    def _query(self, fields: Dict[str, str], block_lot_hint: str = '',
               max_retries: int = 3) -> Tuple[str, List[Dict]]:
        """
        Fill `fields` and search, retrying with backoff if the anti-bot gate
        rejects the request ('blocked') or the call otherwise fails
        ('error'). A 'blocked'/'error' outcome reflects the gate/network, not
        the query itself, so it must never be reported to the caller as a
        genuine "not found" -- callers should treat an exhausted retry as
        inconclusive, not as a confirmed miss.

        A Selenium-level exception mid-attempt (form reload timing out, a
        stale element after a slow page transition, etc.) is treated the
        same way as a 'blocked'/'error' response -- confirmed live: an
        uncaught TimeoutException from `_load_search_form()` on a retry
        attempt killed an entire multi-hour scrape run instead of just that
        one query. The driver is restarted before retrying since an
        exception mid-fill can leave the page in a state the next attempt
        can't recover from otherwise.
        """
        outcome, records = 'error', []
        for attempt in range(1, max_retries + 1):
            try:
                self._load_search_form()
                for name, value in fields.items():
                    self._fill_field(name, value)
                response = self._submit_and_capture()
                outcome, records = self._parse_response(response, block_lot_hint=block_lot_hint)
            except WebDriverException as exc:
                _log(f'[ERROR] Selenium exception on attempt {attempt} for {fields}: {exc}')
                outcome, records = 'error', []
                self._restart_driver()
            else:
                self._maybe_restart()
            if outcome == 'ok':
                time.sleep(random.uniform(10, 25))
                return outcome, records
            cooldown = random.uniform(30, 75) * attempt
            _log(f'[RETRY {attempt}/{max_retries}] outcome={outcome} for {fields} '
                 f'-- backing off {cooldown:.0f}s')
            time.sleep(cooldown)
        _log(f'[GIVE UP] {fields} still {outcome} after {max_retries} retries -- '
             f'treating as inconclusive, not a confirmed miss')
        return outcome, records

    # -- public API ---------------------------------------------------------

    def scrape_parcels(self, parcel_pairs: List[Tuple[str, str]]) -> Dict[str, Dict]:
        """Targeted lookup by known (gush, helka) pairs -- for existing Madlan projects."""
        if self.driver is None:
            self.driver = self._init_driver()
        seen: Dict[str, Dict] = {}
        for gush, helka in parcel_pairs:
            outcome, records = self._query(
                {'blockNumber': gush, 'parcelNumber': helka},
                block_lot_hint=f'{gush}-{helka}',
            )
            if outcome != 'ok':
                _log(f'[WARN] Could not resolve gush={gush} helka={helka} -- skipping, not a confirmed empty result')
                continue
            for record in records:
                seen.setdefault(record['request_number'], record)
        return seen

    def scrape_license_ids(self, license_ids: List[int]) -> Dict[str, Dict]:
        """
        Targeted lookup by an explicit list of licenseId values -- used to
        gap-fill: after `scrape_parcels()` finds the real license numbers for
        known projects, query every licenseId *between* the found min/max
        that parcel search didn't already surface (catches permits for
        projects not yet in Madlan whose number falls within the known
        range), without re-querying the ones already found.
        """
        if self.driver is None:
            self.driver = self._init_driver()
        seen: Dict[str, Dict] = {}
        for license_id in license_ids:
            outcome, records = self._query({'licenseId': str(license_id)})
            if outcome != 'ok':
                _log(f'[WARN] Could not resolve licenseId={license_id} -- skipping, not a confirmed empty result')
                continue
            for record in records:
                seen.setdefault(record['request_number'], record)
        return seen

    def scan_license_range(self, start: int, consecutive_miss_limit: int = 20,
                            max_queries: Optional[int] = None) -> Dict[str, Dict]:
        """
        Scan licenseId upward from `start` (format 20YY#### e.g. 20260624) --
        intended to be called with `start` = one past the highest licenseId
        already found by `scrape_parcels()`/`scrape_license_ids()`, to pick
        up new permits filed since. Stops only after `consecutive_miss_limit`
        sequential *genuine* not-found results -- the real sequence has gaps
        (confirmed in recon: 625/626 missing while 620-624 present), so
        stopping at the first miss would truncate the scan early.
        Gate-blocked/failed queries do NOT count toward the miss threshold
        (see `_query`) -- they're retried with backoff instead, since
        counting them would produce a false ceiling.
        """
        if self.driver is None:
            self.driver = self._init_driver()
        seen: Dict[str, Dict] = {}
        license_id = start
        consecutive_misses = 0
        queries = 0
        inconclusive: List[int] = []
        while consecutive_misses < consecutive_miss_limit:
            if max_queries and queries >= max_queries:
                _log(f'[INFO] Reached max_queries={max_queries}, stopping scan')
                break
            outcome, records = self._query({'licenseId': str(license_id)})
            queries += 1
            if outcome != 'ok':
                inconclusive.append(license_id)
                license_id += 1
                continue
            for record in records:
                seen.setdefault(record['request_number'], record)
            consecutive_misses = 0 if records else consecutive_misses + 1
            license_id += 1
        _log(f'[INFO] Scan stopped at licenseId={license_id} after {consecutive_misses} '
             f'consecutive genuine misses ({queries} queries, {len(seen)} permits found, '
             f'{len(inconclusive)} inconclusive: {inconclusive})')
        return seen
