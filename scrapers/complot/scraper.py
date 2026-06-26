"""
Complot municipal permit scraper (Selenium / undetected-chromedriver).

Adapted from the municipal-permit-scraper repo with one addition:
  _extract_permit_status() reads the "אירועים" events history table and
  returns the highest approval milestone reached, plus its date.

Proven patterns preserved:
  - Browser restart every 100 requests (prevents memory/state degradation)
  - Download-button approach to get all request numbers at once
  - 5-strategy fallback for gush-helka extraction
  - Random delays (5-12 s) between requests
  - JavaScript force-hide for modal overlays
"""

import os
import re
import sys
import time
import random
import glob
from datetime import datetime
from typing import Dict, List, Tuple

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    import pandas as pd
except ImportError as e:
    raise ImportError(
        f"Missing dependency: {e}\n"
        "Run: pip install undetected-chromedriver selenium pandas openpyxl"
    )


# Map from event description substrings to our status vocabulary.
# Add more entries here as new mappings are discovered.
EVENT_TO_STATUS: Dict[str, str] = {
    'פתיחת בקשה':         'בקשה להיתר',
    'מתן היתר למבקש':     'היתר',        # matches both "למבקש" and "למבקשה"
    'הפקת תעודת גמר':     'טופס 4',
}

STATUS_ORDER = ['בקשה להיתר', 'היתר בתנאים', 'היתר', 'טופס 4']


if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def _log(msg: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')


class ComplotScraper:
    """
    Scraper for a single Complot-based municipal permit website.

    Usage:
        scraper = ComplotScraper(city_name_hebrew='בת ים',
                                 url='https://batyam.complot.co.il/iturbakashot/')
        scraper.max_requests = 20  # optional test limit
        permits = scraper.scrape()
    """

    def __init__(self, city_name_hebrew: str, url: str, headless: bool = False,
                 year_filter: List[int] = None):
        self.city_name = city_name_hebrew
        self.base_url = url.rstrip('/')
        self.origin = url.split('#')[0].rstrip('/')  # base URL without hash, for detail page navigation
        self.headless = headless
        self.year_filter = year_filter  # e.g. [2025, 2026] — filters by תאריך הגשה year
        self.max_requests = None  # set to int for testing

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def scrape(self) -> List[Dict]:
        """
        Run a full scrape. Returns a list of permit dicts, each with:
          request_number, request_date, full_address, city, block_lot,
          request_type, project_description, requestor,
          permit_status, permit_status_date, scrape_status
        """
        driver = None
        try:
            driver = self._init_driver()
            _log(f'Navigating to {self.base_url}')
            driver.get(self.base_url)
            time.sleep(10)

            self._close_modals(driver)
            self._click_show_all(driver)

            request_numbers = self._download_request_list(driver)
            if not request_numbers:
                _log('[ERROR] No request numbers obtained via download button.')
                return []

            _log(f'Found {len(request_numbers)} request numbers')

            if self.max_requests:
                request_numbers = request_numbers[:self.max_requests]
                _log(f'Limiting to {self.max_requests} for testing')

            permits = []
            for i, raw_number in enumerate(request_numbers):
                if i > 0 and i % 100 == 0:
                    _log(f'[Browser restart at {i+1}/{len(request_numbers)}]')
                    driver.quit()
                    time.sleep(2)
                    driver = self._init_driver()
                    time.sleep(3)

                clean = self._clean_number(raw_number)
                if not clean:
                    continue

                url = f'{self.origin}#request/{clean}'
                _log(f'[{i+1}/{len(request_numbers)}] {clean}')
                driver.get(url)

                # Wait for permit detail content to appear
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.ID, 'table-gushim-helkot'))
                    )
                except Exception:
                    pass

                time.sleep(2)
                time.sleep(random.uniform(3, 6))

                permit = self._extract_permit(driver, clean)
                if permit:
                    permits.append(permit)

            return permits

        except Exception as e:
            _log(f'[ERROR] Scrape failed: {e}')
            raise
        finally:
            if driver:
                driver.quit()

    # ------------------------------------------------------------------
    # Permit extraction
    # ------------------------------------------------------------------

    def _extract_permit(self, driver, request_number: str) -> Dict:
        permit = {'request_number': request_number, 'city': self.city_name}

        # Save DOM of first permit for inspection
        if not getattr(self, '_debug_html_saved', False):
            try:
                debug_path = f'outputs/debug_{self.city_name}_permit.html'
                os.makedirs('outputs', exist_ok=True)
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                _log(f'  [DEBUG] Page HTML saved to {debug_path}')
                self._debug_html_saved = True
            except Exception:
                pass

        # ID-verification lock screen
        try:
            driver.find_element(By.XPATH,
                "//h2[contains(text(),'צפייה בפרטי בקשה')] | "
                "//div[contains(text(),'נדרש להזין את מספר תעודת')]")
            _log(f'  [locked]')
            permit['scrape_status'] = 'locked'
            return permit
        except NoSuchElementException:
            pass

        # Address and date from top navbar info divs
        try:
            info_divs = driver.find_elements(By.CLASS_NAME, 'top-navbar-info-desc')
            value_divs = [d for d in info_divs
                          if 'result-title' not in (d.get_attribute('class') or '')]
            if value_divs and value_divs[0].text.strip().isdigit():
                value_divs = value_divs[1:]
            if len(value_divs) >= 2:
                permit['full_address'] = value_divs[0].text.strip()
                permit['request_date'] = value_divs[1].text.strip()
        except Exception:
            pass

        # Gush-helka (multiple pairs possible)
        permit['block_lot'] = '; '.join(self._find_gush_helka(driver))

        # Standard table fields
        permit['request_type'] = self._find_table_value(driver, 'תיאור הבקשה')
        permit['project_description'] = self._extract_description(driver)
        permit['requestor'] = self._find_table_value(driver, 'מבקש')

        # Permit status from events history
        permit['permit_status'], permit['permit_status_date'] = self._extract_permit_status(driver)

        # Scrape quality
        filled = sum(bool(permit.get(f)) for f in
                     ['request_date', 'full_address', 'block_lot', 'request_type', 'requestor'])
        permit['scrape_status'] = 'success' if filled >= 3 else ('partial' if filled > 0 else 'fail')

        quality = (f"G:{bool(permit.get('block_lot'))} "
                   f"T:{bool(permit.get('request_type'))} "
                   f"D:{bool(permit.get('project_description'))} "
                   f"S:{permit.get('permit_status') or '-'}")
        _log(f'  [{quality}]')

        return permit

    def _extract_permit_status(self, driver) -> Tuple[str, str]:
        """
        Read the אירועים (events) section and return the highest-milestone
        status found, plus that event's date.
        Returns ('', '') when the section is absent or unreadable.
        """
        try:
            # Strategy 1: direct ID lookup (Bat Yam / standard Complot layout)
            table = None
            try:
                table = driver.find_element(By.CSS_SELECTOR, '#table-events table')
            except NoSuchElementException:
                pass

            # Strategy 2: header-text XPath fallback for other Complot variants
            if table is None:
                header = None
                for xpath in [
                    "//h3[contains(text(),'אירועים')]",
                    "//h4[contains(text(),'אירועים')]",
                    "//*[contains(@class,'panel-title') and contains(.,'אירועים')]",
                    "//*[contains(@class,'section-title') and contains(.,'אירועים')]",
                    "//*[contains(@id,'events')]//table",
                ]:
                    try:
                        header = driver.find_element(By.XPATH, xpath)
                        break
                    except NoSuchElementException:
                        continue

                if header is None:
                    return ('', '')

                # Expand if collapsed
                try:
                    driver.execute_script('arguments[0].scrollIntoView(true);', header)
                    driver.execute_script('arguments[0].click();', header)
                    time.sleep(2)
                except Exception:
                    pass

                try:
                    table = driver.find_element(By.XPATH,
                        "//h3[contains(text(),'אירועים')]/following::table[1]")
                except Exception:
                    pass

            if table is None:
                return ('', '')

            rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
            best_status = ''
            best_date = ''
            best_rank = -1

            for row in rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) < 3:
                    continue

                # RTL table DOM order: cells[0]=סוג אירוע, [1]=תיאור, [2]=תאריך אירוע, [3]=תאריך סיום
                description = cells[1].text.strip()
                event_date = cells[2].text.strip()

                for keyword, status in EVENT_TO_STATUS.items():
                    if keyword in description:
                        rank = STATUS_ORDER.index(status) if status in STATUS_ORDER else -1
                        if rank > best_rank:
                            best_rank = rank
                            best_status = status
                            best_date = event_date
                        break

            return (best_status, best_date)

        except Exception as e:
            _log(f'  [status error] {e}')
            return ('', '')

    # ------------------------------------------------------------------
    # Request list retrieval (download button approach)
    # ------------------------------------------------------------------

    def _download_request_list(self, driver) -> List[str]:
        """
        Click the Excel download button on the results page, then parse the
        downloaded file to get all request numbers.
        Returns empty list on failure (hard fail — no table fallback).
        """
        time.sleep(5)

        try:
            driver.save_screenshot(f'debug_download_{self.city_name}.png')
        except Exception:
            pass

        download_btn = None
        for selector in [
            "button.dt-excel-button, button.buttons-excel, button.buttons-excel.buttons-html5",
            "button[aria-label*='Excel']",
            ".glyphicon-floppy-disk, .fa-floppy-o",
            "button[title*='Excel'], button[title*='שמיר']",
        ]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, selector)
                # For icon elements, go up to the parent button
                download_btn = el if el.tag_name == 'button' else el.find_element(By.XPATH, '..')
                break
            except Exception:
                continue

        # Fallback: scan all buttons for Excel-related HTML
        if download_btn is None:
            try:
                for btn in driver.find_elements(By.TAG_NAME, 'button'):
                    html = btn.get_attribute('outerHTML') or ''
                    if 'excel' in html.lower() or 'floppy' in html.lower() or 'שמיר' in html:
                        download_btn = btn
                        break
            except Exception:
                pass

        if download_btn is None:
            _log('[ERROR] Download button not found. Check debug screenshot.')
            return []

        _log('Clicking download button...')
        # Scroll button into view then use JS click to bypass sticky header interception
        driver.execute_script('arguments[0].scrollIntoView({block:"center"});', download_btn)
        time.sleep(1)
        driver.execute_script('arguments[0].click();', download_btn)
        time.sleep(10)

        downloads = (
            glob.glob(os.path.expanduser('~/Downloads/*.xlsx')) +
            glob.glob(os.path.expanduser('~/Downloads/*.xls')) +
            glob.glob(os.path.expanduser('~/Downloads/*.csv'))
        )
        if not downloads:
            _log('[ERROR] No downloaded file found in ~/Downloads')
            return []

        latest = max(downloads, key=os.path.getctime)
        _log(f'Parsing {os.path.basename(latest)}')

        try:
            if latest.endswith('.csv'):
                df = pd.read_csv(latest)
            else:
                # Row 0 is a title ("Exported data"); row 1 contains real column headers
                df = pd.read_excel(latest, header=1)
                # If that still gives unnamed columns, the title row may not exist
                if all(str(c).startswith('Unnamed') for c in df.columns):
                    df = pd.read_excel(latest, header=0)
        except Exception as e:
            _log(f'[ERROR] Could not parse downloaded file: {e}')
            return []

        # --- DIAGNOSTIC: write column structure to file ---
        os.makedirs('outputs', exist_ok=True)
        diag_path = f'outputs/debug_excel_{self.city_name}.txt'
        try:
            with open(diag_path, 'w', encoding='utf-8') as fh:
                fh.write(f'Columns: {list(df.columns)}\n\n')
                fh.write(df.head(10).to_string())
            _log(f'Excel diagnostic written to {diag_path}')
        except Exception:
            pass
        _log(f'Excel columns ({len(df.columns)}): {[str(c) for c in df.columns]}')
        # --------------------------------------------------

        # Detect permit number column by header name; fall back to column index 1
        number_col = None
        for candidate in ['מספר הבקשה', 'מספר בקשה', 'מספר בקשה(רישוי זמין)', "מס' בקשה", 'בקשה', 'מספר']:
            if candidate in df.columns:
                number_col = candidate
                _log(f'Using column for permit numbers: {number_col}')
                break

        if number_col is not None:
            working_df = df.dropna(subset=[number_col])
        else:
            _log('Permit number column not identified by name -- falling back to column index 1')
            working_df = df.dropna(subset=[df.columns[1]])
            number_col = df.columns[1]

        # Filter by submission year if requested
        if self.year_filter:
            date_col = next((c for c in df.columns if 'תאריך' in str(c)), None)
            if date_col:
                parsed = pd.to_datetime(working_df[date_col], dayfirst=True, errors='coerce')
                mask = parsed.dt.year.isin(self.year_filter)
                before = len(working_df)
                working_df = working_df[mask]
                _log(f'Year filter {self.year_filter}: {before} -> {len(working_df)} permits')
            else:
                _log('[WARN] year_filter set but no date column found — skipping filter')

        numbers = [str(n) for n in working_df[number_col].tolist()]
        _log(f'Extracted {len(numbers)} request numbers from download')
        return numbers

    # ------------------------------------------------------------------
    # Field extraction helpers
    # ------------------------------------------------------------------

    def _find_table_value(self, driver, header_text: str) -> str:
        """5-strategy fallback to find a value given its column header text."""
        # Strategy 1: th + following-sibling td
        try:
            xpath = f"//th[contains(text(),'{header_text}')]/following-sibling::td[1]"
            return driver.find_element(By.XPATH, xpath).text.strip()
        except Exception:
            pass

        # Strategy 2: td.title + following-sibling td
        try:
            xpath = f"//td[contains(@class,'title') and contains(text(),'{header_text}')]/following-sibling::td[1]"
            return driver.find_element(By.XPATH, xpath).text.strip()
        except Exception:
            pass

        # Strategy 3: th in same row, get last td
        try:
            xpath = f"//th[contains(text(),'{header_text}')]/../td[last()]"
            return driver.find_element(By.XPATH, xpath).text.strip()
        except Exception:
            pass

        # Strategy 4: label-like div
        try:
            xpath = f"//div[contains(@class,'result-title') and contains(text(),'{header_text}')]/following-sibling::*[1]"
            return driver.find_element(By.XPATH, xpath).text.strip()
        except Exception:
            pass

        # Strategy 5: any element containing header text
        try:
            xpath = f"//*[contains(text(),'{header_text}')]/following-sibling::*[1]"
            return driver.find_element(By.XPATH, xpath).text.strip()
        except Exception:
            pass

        return ''

    def _find_gush_helka(self, driver) -> List[str]:
        """
        Expand the gush-helka section and collect all GUSH-HELKA pairs.
        Returns list of strings like ["7128-259", "7128-264"].
        """
        pairs = []

        # Dismiss cap-banner if present
        try:
            banner = driver.find_element(By.ID, 'cap-banner')
            for btn in banner.find_elements(By.CSS_SELECTOR, 'button,.close'):
                btn.click()
                time.sleep(0.5)
                break
        except Exception:
            pass

        try:
            table = driver.find_element(By.ID, 'table-gushim-helkot')

            # Expand if not visible
            if not table.is_displayed():
                try:
                    section = driver.find_element(By.ID, 'gushim-helkot')
                    driver.execute_script('arguments[0].click();', section)
                    time.sleep(2)
                except Exception:
                    pass

            rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) >= 3:
                    gush = cells[1].text.strip()
                    helka = cells[2].text.strip()
                    if gush and helka and gush.isdigit() and helka.isdigit():
                        pairs.append(f'{gush}-{helka}')

        except Exception:
            pass

        return pairs

    def _extract_description(self, driver) -> str:
        """Extract מהות הבקשה project description with multiple fallback strategies."""
        # Method 1: table-condensed sibling of h3's parent div
        try:
            table = driver.find_element(By.XPATH,
                "//h3[contains(text(),'מהות הבקשה')]/parent::div"
                "/following-sibling::*[contains(@class,'table-condensed')]")
            texts = [td.text.strip() for td in table.find_elements(By.TAG_NAME, 'td')
                     if td.text.strip()]
            if texts and 'לא נמצאו נתונים' not in ' '.join(texts):
                return ' '.join(texts)
        except Exception:
            pass

        # Method 2: following-sibling table
        try:
            table = driver.find_element(By.XPATH,
                "//h3[contains(text(),'מהות הבקשה')]/following-sibling::table[1]")
            texts = [td.text.strip() for td in table.find_elements(By.TAG_NAME, 'td')
                     if td.text.strip()]
            if texts and 'לא נמצאו נתונים' not in ' '.join(texts):
                return ' '.join(texts)
        except Exception:
            pass

        # Method 3: any table-condensed
        try:
            for table in driver.find_elements(By.CSS_SELECTOR, 'table.table-condensed'):
                texts = [td.text.strip()
                         for td in table.find_elements(By.CSS_SELECTOR, 'tbody td')
                         if td.text.strip()]
                if texts and 'לא נמצאו נתונים' not in ' '.join(texts):
                    return ' '.join(texts)
        except Exception:
            pass

        return ''

    # ------------------------------------------------------------------
    # Page interaction helpers
    # ------------------------------------------------------------------

    def _init_driver(self):
        _log('Launching Chrome...')
        import subprocess
        chrome_version = None
        try:
            result = subprocess.run(
                ['reg', 'query',
                 r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon', '/v', 'version'],
                capture_output=True, text=True
            )
            for line in result.stdout.splitlines():
                if 'version' in line.lower():
                    chrome_version = int(line.strip().split()[-1].split('.')[0])
                    break
        except Exception:
            pass
        kwargs = dict(suppress_welcome=True, headless=self.headless, no_sandbox=True)
        if chrome_version:
            _log(f'Detected Chrome major version: {chrome_version}')
            kwargs['version_main'] = chrome_version
        return uc.Chrome(**kwargs)

    def _close_modals(self, driver):
        try:
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(1)
        except Exception:
            pass
        try:
            driver.execute_script("""
                ['modalOverlay','modalIframe'].forEach(function(id){
                    var el = document.getElementById(id);
                    if(el){ el.style.display='none'; el.style.visibility='hidden'; }
                });
                document.body.classList.remove('modal-open');
                document.querySelectorAll('[data-dismiss="modal"],.modal-close,.close')
                    .forEach(function(b){ try{b.click();}catch(e){} });
            """)
            time.sleep(1)
        except Exception:
            pass

    def _click_show_all(self, driver):
        link = None
        for xpath in [
            "//a[contains(@href,'getUnlimitedSearch')]",
            "//a[contains(text(),'ללחוץ כאן')]",
            "//a/strong[contains(text(),'ללחוץ')]/parent::a",
        ]:
            try:
                link = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, xpath)))
                break
            except Exception:
                continue

        if link is None:
            _log("'Show all' link not found - may already be showing all results")
            return

        try:
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(link)).click()
        except Exception:
            try:
                driver.execute_script('arguments[0].click();', link)
            except Exception:
                return

        _log('Waiting for full results to load...')
        time.sleep(10)

    def _clean_number(self, raw: str) -> str:
        """Strip Hebrew label prefixes; preserve slashes, hyphens, and digits in the number itself."""
        raw = str(raw).strip()
        for label in ['מספר הבקשה ברישוי זמין', 'מספר הבקשה:', 'מספר בקשה:', "מס' בקשה:", 'בקשה מספר']:
            raw = raw.replace(label, '').strip()
        return raw
