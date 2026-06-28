"""
Test whether GetBakashaFile (permit detail page) is accessible without auth.
If accessible, it provides:
  - תיאור הבקשה  -> request_type  (e.g. 'תמ"א 38- הריסה ובנייה')
  - per-permit events table -> accurate scraped_status + date

Test permit: 20211734, site_id=81 (Bat Yam / Complot)
"""
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
from bs4 import BeautifulSoup

API_BASE = "https://handasi.complot.co.il/magicscripts/mgrqispi.dll"
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
}

TEST_PERMITS = ['20211734', '201177']  # known permits with visible detail pages

session = requests.Session()
session.headers.update(HEADERS)

# First: warm up session via GetBakashotByNumber (same as scraper does)
print('Warming up session via GetBakashotByNumber...')
warmup = session.get(API_BASE, params={
    'appname': 'cixpa', 'prgname': 'GetBakashotByNumber',
    'siteid': 81, 'grp': 0, 't': 0, 'b': 2021, 'l': 'false',
    'arguments': 'siteId,grp,t,b,l',
}, timeout=30)
print(f'  Warmup status: {warmup.status_code}, length: {len(warmup.text)}')

for permit_num in TEST_PERMITS:
    print(f'\n--- GetBakashaFile for permit {permit_num} ---')
    resp = session.get(API_BASE, params={
        'appname':   'cixpa',
        'prgname':   'GetBakashaFile',
        'siteid':    81,
        't':         permit_num,
        'arguments': 'siteid,t',
    }, timeout=30)
    print(f'HTTP {resp.status_code}, length: {len(resp.text)}')

    resp.encoding = 'utf-8'
    text = resp.text

    # Check for access denial
    if any(phrase in text for phrase in ['לא ניתן', 'שגיאה', 'error', 'Error', 'login', 'התחבר']):
        print('[BLOCKED] Response contains denial/error phrase')
        print(f'First 500 chars: {text[:500]}')
        continue

    soup = BeautifulSoup(text, 'html.parser')

    # Look for תיאור הבקשה
    for tag in soup.find_all(string=lambda t: t and 'תיאור' in t and 'בקשה' in t):
        parent = tag.find_parent()
        sibling = parent.find_next_sibling() if parent else None
        val = sibling.get_text(strip=True) if sibling else '(no sibling)'
        print(f'  תיאור הבקשה field: [{val}]')

    # Look for event tables
    tables = soup.find_all('table')
    print(f'  Tables found: {len(tables)}')
    for i, tbl in enumerate(tables):
        headers = [th.get_text(strip=True) for th in tbl.find_all('th')]
        if any('אירוע' in h or 'ארוע' in h for h in headers):
            print(f'  Table {i} (events): headers={headers}')
            for row in tbl.select('tbody tr')[:5]:
                cells = [td.get_text(strip=True) for td in row.find_all('td')]
                print(f'    row: {cells}')

    # Dump a snippet if nothing found
    if not tables:
        print(f'  No tables. First 800 chars:\n{text[:800]}')
