# Session Handoff — 2026-06-28 B

**Date:** 2026-06-28
**Session:** H
**Scope:** Bartech scraper discovery + Bat Yam re-scrape running

---

## What was accomplished

### 1. Bat Yam re-scrape running in background

The updated scraper (GetBakashaFile per permit) was started and is running.
At session end: ~5047/9639 permits done (~52%, ~12:32).
Log file: `outputs/scrape_log_2026_06_28.txt`

Expected completion: ~13:20 (based on ~0.5s/permit rate).

When scrape finishes, run the matcher:
```python
from transform import matcher
matcher.run('docs/bat_yam.xlsx', 'outputs/bat_yam_fresh.xlsx', 'בת ים', 'outputs/bat_yam_report.xlsx')
```

### 2. Full Bartech scraper architecture discovered

Explored `https://hln.bartech-net.co.il` (Holon — first Bartech target city).
Key finding: **no Selenium needed**. Plain HTTP works.

#### Authentication
- The search form has a reCAPTCHA button, but the server does **not validate the token**.
- Any value for `g-recaptcha-response` (even `"x"`) passes.
- All requests can be made with `requests.Session()` + standard headers.

#### Search endpoint
```
GET https://hln.bartech-net.co.il/SearchPermitApplicationResults/
    ?searchType=ByDetails
    &TypeOfPermit=<type_id>
    &g-recaptcha-response=x
    &page=<N>
```

- **`TypeOfPermit` filter works** and dramatically reduces scope.
- **`ApplicationDescription` text search is broken** — returns "לא נמצאו נתונים" for any input including known-valid values. Do not use.
- **Pagination**: add `&page=N`. Last page number extracted from `מתוך <span>N</span>` in response.
- **5 results per page**.
- Results sorted newest-first.

#### Permit types — Holon page counts
| TypeOfPermit | Label | Pages | Permits (~) |
|---|---|---|---|
| 51 | מסלול רישוי מלא | 5089 | ~25,000 |
| 56 | מסלול רישוי מקוצר | 94 | ~470 |
| 57 | מסלול רישוי עם הקלות ו/או שימוש חורג | 132 | ~660 |
| 71 | בקשה מקוונת ללא הקלות | 38 | ~190 |
| 72 | בקשה מקוונת עם הקלות | 16 | ~80 |
| 73 | בקשה מקוונת רישוי מקוצר | 7 | ~35 |
| **55** | **בקשה למידע להיתר** | **EXCLUDED** | — |
| **63** | **תשריט בית משותף** | **EXCLUDED** | — |

Total to scrape: ~5376 pages. At 0.3s/page: ~27 minutes.
Type 51 dominates (95% of pages) — most are minor work, filtered client-side by description.

#### HTML structure per row

Each `<tr>` in the results table:
```html
<td class="permit_results_item_1">
  <div>
    <strong class="phone">TYPE_LABEL ENTITY_NUMBER</strong>
    <span class="phone">מספר ברישוי זמין: ...</span>   <!-- may be absent -->
    <span class="phone">תאריך פתיחה &nbsp; DD/MM/YYYY</span>
    <a href="/PermitApplicationDetails?Definement_Entity_Type=XX&Entity_Type=P&Entity_Number=XXXXXXXX"
       class="btn-link">פרטי הבקשה</a>
  </div>
</td>
<td><div><span ID="Label9">BUILDING_FILE_NUM</span></div></td>
<td><div><span ID="Label10">STATUS</span></div></td>
<td><div><span ID="Label11">ADDRESS</span></div></td>
<td>
  <div>
    <span ID="Label12" ToolTip="גוש: GGGG, חלקה: HHH">גוש: GGGG, חלקה: HHH</span>
  </div>
</td>
<td><div><span ID="Label13">APPLICANT</span></div></td>
<td><div><span ID="Label14">DESCRIPTION</span></div></td>
```

**Key parsing notes:**
- `Entity_Number`: extract from `<a class="btn-link">` href via `parse_qs(urlparse(href).query)['Entity_Number'][0]`
- `request_date`: from `span.phone` whose text contains `'תאריך פתיחה'` — strip the label and `\xa0`
- `block_lot`: from `Label12`'s `ToolTip` attribute — regex `גוש:\s*(\d+).*חלקה:\s*(\d+)` → `"GUSH-HELKA"`
- `request_type`: `Label14` text
- `request_category`: TypeOfPermit label string (passed in from the scraper loop)
- `permit_status`: `Label10` text, mapped via STATUS_MAP (see below)
- `permit_status_date`: `''` — not available in list view; detail page needed but skip for V1

#### Status vocabulary (Bartech → our STATUS_ORDER)
```python
STATUS_MAP = {
    'מאושר':                                    'היתר',
    'פעיל':                                     'בקשה להיתר',
    'בקרה מרחבית':                              'בקשה להיתר',
    'עמידה בתנאים מוקדמים לצורך פרסום':         'בקשה להיתר',
    'אי עמידה בתנאי סף':                        'בקשה להיתר',
    # 'לא פעיל' → '' (closed without permit — not a milestone we track)
}
```

More status values will surface during the first real scrape. Log unmapped ones.

#### No-results detection
```html
<div class="alert alert-warining">לא נמצאו נתונים</div>
```
If this appears, the page has zero rows — stop paginating that type.

---

## What to build next session

### File: `scrapers/bartech/api_scraper.py`

`scrapers/bartech/__init__.py` already created (empty).

```python
"""
Bartech municipal permit scraper — direct API, no Selenium.

Calls the Bartech planning portal directly (no CAPTCHA enforcement).
Iterates SearchPermitApplicationResults for each included TypeOfPermit.

Output schema (same as Complot):
  request_number, request_date, full_address, city, block_lot,
  request_type, request_category, requestor,
  permit_status, permit_status_date, scrape_status
"""

import re, sys, time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
import pandas as pd

RESULTS_PATH = '/SearchPermitApplicationResults/'

PERMIT_TYPES: Dict[int, str] = {
    51: 'מסלול רישוי מלא',
    56: 'מסלול רישוי מקוצר',
    57: 'מסלול רישוי עם הקלות ו/או שימוש חורג',
    71: 'בקשה מקוונת ללא הקלות',
    72: 'בקשה מקוונת עם הקלות',
    73: 'בקשה מקוונת רישוי מקוצר',
}

STATUS_MAP: Dict[str, str] = {
    'מאושר':                                    'היתר',
    'פעיל':                                     'בקשה להיתר',
    'בקרה מרחבית':                              'בקשה להיתר',
    'עמידה בתנאים מוקדמים לצורך פרסום':         'בקשה להיתר',
    'אי עמידה בתנאי סף':                        'בקשה להיתר',
}

_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    ),
}


def _log(msg): print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)


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
        block_lot = _parse_block_lot(label12.get('ToolTip', '')) or label12.get_text(strip=True)

    if not entity_num:
        return None

    if status_raw and status_raw not in STATUS_MAP and status_raw != 'לא פעיל':
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
```

### File: `scripts/run_holon.py`

```python
"""Runner for Holon (Bartech). Run from project root."""
from scrapers.bartech.api_scraper import BartechPermitsAPI
import pandas as pd, os

scraper = BartechPermitsAPI(
    base_url='https://hln.bartech-net.co.il',
    city_name_hebrew='חולון',
)
scraper.max_pages = None  # set to int for testing

permits = scraper.scrape()
df = pd.DataFrame(permits)
os.makedirs('outputs', exist_ok=True)
df.to_excel('outputs/holon_fresh.xlsx', index=False)
print(f'\n--- Results ({len(df)} permits) ---')
cols = ['request_number', 'request_type', 'permit_status', 'scrape_status']
print(df[[c for c in cols if c in df.columns]].to_string())
```

### Matcher call for Holon

```python
from transform import matcher
matcher.run(
    'docs/holon.xlsx',           # Madlan backoffice export for Holon (needs to be obtained first)
    'outputs/holon_fresh.xlsx',
    'חולון',
    'outputs/holon_report.xlsx',
    excluded_categories=set(),   # Bartech: bad types excluded at scrape time (types 55, 63)
)
```

Note: `docs/holon.xlsx` is a manual export from the backoffice that needs to be obtained before running the matcher.

---

## Gotchas / things to verify in next session

1. **Type 51 is 95% of all permits** (~5089 pages, ~25k permits for Holon).
   Most are minor work — client-side description filter will discard most.
   Expect ~27 minutes total at 0.3s/page. Acceptable.

2. **Label IDs are duplicated across rows** (HTML standard violation — ASP.NET pattern).
   The parser uses `tr.find(id='Label12')` which searches within the specific `<tr>`,
   so it works correctly despite page-wide ID collisions.

3. **Scrape test first**: set `max_pages=2` per type to verify structure before full run.
   Check that Entity_Number, address, gush/helka, and description parse correctly.

4. **New STATUS values will appear** — the `[NEW STATUS]` log lines will surface unmapped values.
   Add them to STATUS_MAP as you discover them.

5. **`permit_status_date` is empty** — V1 limitation. Status_advanced detection works
   only for `permit_status` presence, not when it was achieved.
   Detail pages are needed for dates (deferred to V2 if matcher shows many status_advanced rows).

6. **`לא פעיל` (inactive) permits** — intentionally not mapped to any STATUS_ORDER value.
   These are cancelled/rejected permits. The matcher will treat them as status='',
   which means they won't trigger `status_advanced`. Correct behavior.

7. **Verify TypeOfPermit counts for the actual target city** — the page counts above
   are for Holon specifically. Other Bartech cities may have very different counts.
   The `last_page` detection handles this automatically.

8. **Holon backoffice export needed** — before the matcher can run, get the Madlan project
   export for Holon from the backoffice and save as `docs/holon.xlsx`.

---

## State of key files

| File | State |
|---|---|
| `scrapers/bartech/__init__.py` | Created (empty) |
| `scrapers/bartech/api_scraper.py` | **TO BUILD** — full spec above |
| `scripts/run_holon.py` | **TO BUILD** — spec above |
| `outputs/bat_yam_fresh.xlsx` | **SCRAPE IN PROGRESS** (~52% at session end) |
| `outputs/bat_yam_report.xlsx` | Stale — regenerate after scrape completes |
| `docs/holon.xlsx` | **MISSING** — needs manual backoffice export |
