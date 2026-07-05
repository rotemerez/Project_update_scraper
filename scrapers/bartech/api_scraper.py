"""
Bartech municipal permit scraper -- direct API, no Selenium.

Calls the Bartech planning portal directly (no CAPTCHA enforcement).
Two-step process:
  1. SearchPermitApplicationResults -> full permit list (all pages per TypeOfPermit)
  2. PermitApplicationDetails       -> per-permit detail page: stages, request_type, gush/helka

Output schema (same as Complot):
  request_number, request_date, full_address, city, block_lot,
  request_type, request_category, requestor, bakasha_description,
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
DETAIL_PATH  = '/PermitApplicationDetails'

PERMIT_TYPES: Dict[int, str] = {
    51: 'מסלול רישוי מלא',
    56: 'מסלול רישוי מקוצר',
    57: 'מסלול רישוי עם הקלות ו/או שימוש חורג',
    71: 'בקשה מקוונת ללא הקלות',
    72: 'בקשה מקוונת עם הקלות',
    73: 'בקשה מקוונת רישוי מקוצר',
}

_KNOWN_CLOSED = {'לא פעיל', 'סגירת בקשה - פג תוקף החלטה'}

# List-page status → our vocabulary (fallback when stages give nothing)
STATUS_MAP: Dict[str, str] = {
    # טופס 4
    'היתר/טופס 4':                                         'טופס 4',
    'טופס 4':                                              'טופס 4',
    'היתר/תעודת גמר':                                      'טופס 4',
    'טופס איכלוס':                                         'טופס 4',
    'גמר בניה':                                             'היתר',
    'גמר בניה - ביקורת ראשית':                             'טופס 4',
    # היתר
    'מאושר':                                                'היתר',
    'היתר':                                                 'היתר',
    'היתר/תחילת עבודות':                                   'היתר',
    'העברת היתר לפיקוח על הבני':                           'היתר',
    'מסירת א. תחילת עבודות':                               'היתר',
    'הפקת תעודת גמר':                                      'היתר',
    'בקשה לתעודת גמר':                                     'היתר',
    'טופס 4 להרצת מערכות':                                 'היתר',
    'תנאים לטופס איכלוס':                                  'היתר',
    'בדיקת המבנה לטופס 4':                                 'היתר',
    'יסודות':                                              'היתר',
    'מהלך בנית השלד':                                      'היתר',
    'גמר שלד':                                             'היתר',
    'עבודות גמרים':                                        'היתר',
    'הודעה על תחילת עבודה':                                'היתר',
    # היתר בתנאים
    'החלטה לאשר':                                          'היתר בתנאים',
    'החלטה לאשר בועדה':                                    'היתר בתנאים',
    'הפקת אגרה':                                           'היתר בתנאים',
    # בקשה להיתר
    'פעיל':                                                 'בקשה להיתר',
    'הגשה':                                                 'בקשה להיתר',
    'עמידה בתנאים מוקדמים':                                'בקשה להיתר',
    'עמידה בתנאים מוקדמים לצורך פרסום':                   'בקשה להיתר',
    'אי עמידה בתנאי סף':                                   'בקשה להיתר',
    'אי עמידה בתנאים מוקדמים':                             'בקשה להיתר',
    'אי עמידה בתנאים מוקדמים לצורך פרסום':                'בקשה להיתר',
    'פתיחת בקשה להיתר':                                    'בקשה להיתר',
    'שובץ לישיבת ועדה':                                     'בקשה להיתר',
    'בדיקה גליון דרישות':                                  'בקשה להיתר',
    'החלטה לדחות':                                         'בקשה להיתר',
    'ישיבת ועדת משנה לתכנון':                              'בקשה להיתר',
    'ישיבת מליאת חברי הועדה':                              'בקשה להיתר',
}

# Priority order: higher index = more significant (same as Complot)
STATUS_ORDER = ['בקשה להיתר', 'היתר בתנאים', 'היתר', 'טופס 4']

# Detail-page stage descriptions → our vocabulary (substring match, ordered most→least specific)
STAGE_TO_STATUS: Dict[str, str] = {
    # טופס 4
    'טופס 4':                                              'טופס 4',
    'היתר/טופס 4':                                         'טופס 4',
    'היתר/תעודת גמר':                                      'טופס 4',
    'טופס איכלוס':                                         'טופס 4',
    # היתר
    'מסירת היתר':                                          'היתר',
    'הפקת אישור לתחילת עבודות':                            'היתר',
    'סגירת בקשה להיתר שנמסר':                             'היתר',
    'גמר בניה':                                            'היתר',
    'אישור לת. גמר, פיקוח בניה':                          'היתר',
    'הפקת טופס 2':                                         'היתר',
    'הפקת תעודת גמר':                                      'היתר',
    'בקשה לתעודת גמר':                                     'היתר',
    'טופס 4 להרצת מערכות':                                 'היתר',
    'תנאים לטופס איכלוס':                                  'היתר',
    'בדיקת המבנה לטופס 4':                                 'היתר',
    'גמר שלד':                                             'היתר',
    'יסודות':                                              'היתר',
    'מהלך בנית השלד':                                      'היתר',
    'עבודות גמרים':                                        'היתר',
    'הודעה על תחילת עבודה':                                'היתר',
    # היתר בתנאים — use shorter prefix so both 'החלטה לאשר' and 'החלטה לאשר הבקשה' match
    'החלטה לאשר':                                          'היתר בתנאים',
    'הפקת אגרה':                                           'היתר בתנאים',
    # בקשה להיתר
    'ישיבת רשות רישוי':                                    'בקשה להיתר',
    'שיבוץ לועדה':                                         'בקשה להיתר',
    'פתיחת בקשה':                                          'בקשה להיתר',
    'שליחת מכתב החלטת ועדה':                               'בקשה להיתר',
    'הגשת בקשה להיתר במערכת רישוי זמין':                  'בקשה להיתר',
    'שיבוץ בקשה לישיבה':                                   'בקשה להיתר',
    'ישיבת הועדה המקומית לתכנון ולבניה':                   'בקשה להיתר',
    'שליחת מכתבי החלטה':                                   'בקשה להיתר',
    'ישיבת ועדת משנה לתכנון':                              'בקשה להיתר',
    'ישיבת מליאת חברי הועדה':                              'בקשה להיתר',
    'החלטה לדחות':                                         'בקשה להיתר',
    'בדיקה גליון דרישות':                                  'בקשה להיתר',
    'הגשת בקשה להיתר מקוונת לאחר פרסום':                  'בקשה להיתר',
    'הוגשה בקשה לבדיקה ראשונית':                          'בקשה להיתר',
}

# Stage descriptions we know don't map to tracked milestones — suppresses log noise.
# Populated from observed data; add more after each new-city run.
_UNMAPPED_STAGES = {
    # Consultant referrals
    'הועבר להתייחסות יועץ תברואה', 'הועבר להתייחסות יועץ תנועה',
    'הועבר להתייחסות יועץ נגישות', 'הועבר להתייחסות יועץ מדידות',
    'הועבר להתייחסות יועץ גנים ונוף', 'הועבר להתייחסות יועץ רישוי',
    'הועבר להתייחסות יועץ איכות סביבה', 'הועבר להתייחסות תאגיד המים',
    'הועבר להתייחסות לאגף תשתיות עירוניות', 'הועבר להתייחסות - אדר\' תב"ע',
    'הועבר להתייחסות יחידת איכות הסביבה',
    'מתן התייחסות - יועץ תאגיד המים', 'מתן התייחסות - יועץ תברואה',
    'מתן התייחסות - יועץ איכות הסביבה',
    'דרישה להתייחסות - השבחה', 'דרישה להתייחסות - יועץ איכות סביבה',
    'דרישה להתייחסות - יועץ תשתיות עירוניות', 'דרישה להתייחסות - יועץ מדידות',
    'דרישה להתייחסות - יועץ גנים ונוף', 'דרישה להתייחסות - יועץ תברואה',
    'דרישה להתייחסות - יועץ נגישות', 'דרישה להתייחסות - יועץ תאגיד המים',
    'דרישה להתייחסות - יועץ תנועה', 'דרישה להתייחסות - יועץ רישוי',
    # Technical checks
    'תברואה - הערות יועץ', 'תברואה - מאושר',
    'ניקוז - תכנית מאושרת', 'קבלת התייחסות - אגף תשתיות עירוניות ניקוז',
    'אישור כבישים ותנועה', 'הערות לכבישים ותנועה',
    'אינסטלציה-תכנית מאושרת', 'הערות לתכנית אינסטלציה',
    'אדריכל-מאושר', 'הועבר לחזות העיר', 'הועבר להתיחסות - עיצוב עירוני',
    'הועבר לאביבית לבקרה מרחבית',
    'פיקוח - לבדיקת התאמה למציאות', 'הועבר לבדיקת הפיקוח – רישוי זמין',
    'בדיקת התאמה למציאות - מתאים', 'בדיקת התאמה למציאות - לא מתאים',
    'פיקוח התאמה למציאות - נבדק',
    'בדיקת בוחנות-גליון דרישות', 'לבדיקת בוחנות',
    'בדיקת שמאית העירייה', 'בדיקת תנאים מוקדמים בשלב בקרת תכן - אישור',
    'סיום בקרה מרחבית - רישוי זמין', 'בקרת תכן תקינה',
    'אשור היחידה לאיכות הסביבה', 'הערות היחידה לאיכות הסביבה',
    # Fee / financial
    'חישוב אגרה', 'תשלום אגרה', 'אגרה נבדקה ואושרה',
    'מסירת חשבון אגרות והיטלים', 'מסירת חשבון אגרות',
    'גמר תשלום היטל השבחה', 'גמר הכנת שומה - שמאי חוץ', 'להכנת שומה - שמאי חוץ',
    'קבלת פטור משומה (רגיל)', 'הועבר למחלקת השבחה',
    'תשלום פקדון', 'הפקת פקדון',
    'קבלת פטור/אישור פיקוד העורף', 'קבלת כתב שיפוי',
    # Documentation / routing
    'חתימת מנהל אגף על תכנית',
    'הזנת פרטי שטחים ויח"ד בבקשה להיתר',
    'מספר חתימות', 'סוג בעלות', 'הועבר לבדיקת טיוטת היתר',
    'ממתין להשלמת מסמכים', 'סיכום פגישה או שיחת טלפון',
    'שינוי אחראי בקשה', 'הוחזר למתכנן לתיקון',
    # Rishuy Zamin internal
    'רישוי זמין - נבדקה ונדחתה בקשה בתנאים מוקדמים',
    'רישוי זמין - נבדקה ואושרה בקשה בתנאים מוקדמים (הפצה לגורמים)',
    'רישוי זמין - העברת בקשה למידענית',
    # Permit issued but may not be signed yet — reviewer: not a tracked milestone
    'הפקת היתר', 'הוצא היתר', 'הוצאת היתר בניה',
    # Construction track admin
    'פתיחת תיק מפקח',
    # Information request
    'פתיחת בקשה למידע', 'הפקת דף מידע', 'הועבר ליועצים לצרכי מידע',
    'מסירת מידע',
    # Krayot (vkrayot.co.il) — Rishuy Zamin workflow and committee steps
    'קבלת בקשה (עמידה בתנאים מוקדמים)',
    'קבלת תיקונים מעורך הבקשה', 'העברה לתיקונים לעורך הבקשה',
    'דחיית הבקשה (אינה עומדת בתנאים מוקדמים)',
    'העברת תוכנית לעיריה', 'קבלת תוכנית מהעיריה',
    'פירסום הקלה',
    'בקשה עומדת בתנאים מוקדמים לצורך הפקת נוסח פרסום',
    'בקשה אינה עומדת בתנאים מוקדמים לצורך הפקת נוסח פרסום',
    'בדיקת חבות היטל השבחה',
    'אישור תשלום אגרות עירייה ותאגיד המים',
    'בקרת תכן אינה תקינה', 'בקרה מרחבית תקינה', 'בקרה מרחבית אינה תקינה',
    'הגשת בקשה לבקרת תכן',
    'הפקת מסמך לשחרור ערבות',
    'בקשה לטופס תחילת עבודות',
    'פירסום שימוש חורג',
    'מקלט',
    'לאחר פרסום עמידה בתנאים מוקדמים',
    'לאחר פרסום אי עמידה בתנאים מוקדמים',
    'קבלת בקשה (כולל נוסח פרסום)',
    'קבלת מסמכים ראשוניים',
    'הכנת התיק לועדה',
    # Krayot — warranty release workflow
    'שחרור ערבות ע"י מפקח/ת', 'בקשה לשחרור ערבות',
    'קבלת טפסים לשחרור ערבויות', 'מתן תנאים לשחרור ערבות',
    # Krayot — admin / post-construction docs
    'הפקת טופס אישור לטאבו', 'הפקת טופס דרישות',
    'פתיחת תיק בנין', 'סיום טיפול', 'איכסון בארכיב',
    'הגשת תוכנית ידנית', 'שליחת השומה למבקש',
    'השלמת דרישות להיתר - נספח', 'השלמת מסמכים', 'השלמת מסמכים סופית',
    'אישור מנהל, 100% הסכמות בעלי נכס להריסה', 'אישור עירייה עקרוני',
    'מתווה',
    # Krayot — spatial / technical checks (distinct from בקרה מרחבית already listed)
    'בדיקה מרחבית תקינה', 'בדיקה מרחבית אינה תקינה', 'בדיקה טכנית',
    # Krayot — field inspections
    'ביקור מפקח בשטח', 'בדיקת המפקח בשטח', 'סיור המפקח',
    'מכתב - דוח פיקוח', 'דוח מהנדס חיצוני שלב א', 'דוח מהנדס חיצוני שלב ב',
    # Krayot — suspension / cancellation (not a tracked milestone)
    'ביטול היתר', 'החלטה להשהות',
    'ועדת בדיקה תצא לשטח ותביא המלצתה בפני מליאת הועדה',
    'תוכנית מאושרת בסמכות מהנדס',  # engineer-authority approval — reviewer not yet confirmed
    # Krayot — legal / enforcement
    'ישיבה', 'הגשת כתב אישום', 'דיון מישפטי', 'פתיחת תיק פלילי',
    'צו הפסקה מנהלי', 'התראה מיכה',
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


def _map_stage(stage_desc: str) -> str:
    for keyword, status in STAGE_TO_STATUS.items():
        if keyword in stage_desc:
            return status
    return ''


def _extract_dl_field(soup: BeautifulSoup, label_text: str) -> str:
    """Extract value from <dt>label</dt><dd>value</dd> pattern."""
    for dt in soup.find_all('dt'):
        if label_text in dt.get_text(strip=True):
            dd = dt.find_next_sibling('dd')
            if dd:
                return dd.get_text(strip=True)
    return ''


def _parse_detail(html: str) -> Dict:
    """
    Parse the PermitApplicationDetails page.

    Returns:
      request_type        - תאור הבקשה (construction description)
      bakasha_description - מהות הבקשה (free-text nature of request)
      detail_block_lot    - gush-helka from detail page (more accurate than list page)
      permit_status       - highest-ranked status across all stage tables
      permit_status_date  - date of that stage
    """
    soup = BeautifulSoup(html, 'html.parser')

    request_type = _extract_dl_field(soup, 'תאור הבקשה')

    # מהות הבקשה uses <span>label</span> + plain text in a single <td>
    bakasha_description = ''
    for td in soup.find_all('td'):
        span = td.find('span')
        if span and 'מהות הבקשה' in span.get_text(strip=True):
            bakasha_description = td.get_text(strip=True).replace('מהות הבקשה:', '').strip()
            break

    # Gush/helka from detail page
    detail_block_lot = ''
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        if not rows:
            continue
        header_cells = [td.get_text(strip=True) for td in rows[0].find_all(['td', 'th'])]
        if 'מספר גוש' not in header_cells or 'מספר חלקה' not in header_cells:
            continue
        gush_idx = header_cells.index('מספר גוש')
        helka_idx = header_cells.index('מספר חלקה')
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if len(cells) > max(gush_idx, helka_idx):
                gush = cells[gush_idx]
                helka = cells[helka_idx]
                if gush and helka:
                    detail_block_lot = f'{gush}-{helka}'
                    break
        if detail_block_lot:
            break

    # Scan ALL stages tables (מסלול רישוי + שלבי בניה + any other tracks)
    best_status = ''
    best_date = ''
    best_rank = -1

    for table in soup.find_all('table'):
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if 'סטטוס שלב' not in headers:
            continue
        all_rows = table.find_all('tr')
        if len(all_rows) < 2:
            continue
        header_row = [cell.get_text(strip=True) for cell in all_rows[0].find_all(['td', 'th'])]
        try:
            desc_idx = header_row.index('תאור שלב')
            date_idx = header_row.index('תאריך')
        except ValueError:
            continue

        for row in all_rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if len(cells) <= max(desc_idx, date_idx):
                continue
            stage_desc = cells[desc_idx]
            stage_date = cells[date_idx]

            status = _map_stage(stage_desc)
            rank = STATUS_ORDER.index(status) if status in STATUS_ORDER else -1
            if rank > best_rank:
                best_rank = rank
                best_status = status
                best_date = stage_date

            if stage_desc and stage_desc not in _UNMAPPED_STAGES and not status:
                _log(f'  [NEW STAGE] Unmapped: [{stage_desc}]')

    return {
        'request_type':        request_type,
        'bakasha_description': bakasha_description,
        'detail_block_lot':    detail_block_lot,
        'permit_status':       best_status,
        'permit_status_date':  best_date,
    }


class BartechPermitsAPI:
    def __init__(self, base_url: str, city_name_hebrew: str,
                 permit_types: Optional[Dict[int, str]] = None,
                 min_year: Optional[int] = None):
        self.base_url = base_url.rstrip('/')
        self.city_name = city_name_hebrew
        self.permit_types = permit_types if permit_types is not None else PERMIT_TYPES
        self.min_year = min_year   # exclude permits older than this year from list and detail phases
        self.max_pages: Optional[int] = None  # set to int for testing

        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._session.headers['Referer'] = f'{self.base_url}/SearchPermitApplication'

    def scrape(self) -> List[Dict]:
        # Phase 1: collect all permits from list pages.
        # Permits older than min_year are skipped entirely (not added to seen).
        # Permits with no parseable date (year == 0) are always kept.
        seen: Dict[str, Dict] = {}
        for type_id, type_label in self.permit_types.items():
            _log(f'TypeOfPermit={type_id} ({type_label})...')
            permits = self._scrape_type(type_id, type_label)
            new = 0
            skipped = 0
            for p in permits:
                if self.min_year:
                    yr = _permit_year(p)
                    if yr > 0 and yr < self.min_year:
                        skipped += 1
                        continue
                if p['request_number'] not in seen:
                    new += 1
                seen.setdefault(p['request_number'], p)
            if skipped:
                _log(f'  -> {len(permits)} rows, {new} new, {skipped} skipped (pre-{self.min_year}) '
                     f'(total unique: {len(seen)})')
            else:
                _log(f'  -> {len(permits)} rows, {new} new (total unique: {len(seen)})')

        # Phase 2: enrich each unique permit with detail page data.
        # All permits in seen are already >= min_year (filtered in phase 1).
        all_permits = list(seen.values())
        detail_permits = all_permits
        _log(f'\nFetching detail pages for {len(all_permits)} unique permits...')
        total = len(detail_permits)
        for i, permit in enumerate(detail_permits):
            entity_num  = permit['request_number']
            def_type    = permit.pop('_definement_type', list(self.permit_types.keys())[0])
            detail_html = self._fetch_detail(entity_num, def_type)
            if detail_html:
                detail = _parse_detail(detail_html)
                # Stages-based status overrides list-page status when available
                if detail['permit_status']:
                    permit['permit_status']      = detail['permit_status']
                    permit['permit_status_date'] = detail['permit_status_date']
                # request_type from detail is more accurate (construction description)
                if detail['request_type']:
                    permit['request_type'] = detail['request_type']
                if detail['bakasha_description']:
                    permit['bakasha_description'] = detail['bakasha_description']
                # Detail page gush/helka overrides list-page value when available
                if detail['detail_block_lot']:
                    permit['block_lot'] = detail['detail_block_lot']
            if (i + 1) % 200 == 0:
                _log(f'  [{i + 1}/{total}] detail pages fetched')
            time.sleep(0.2)

        _log(f'Detail phase complete.')
        return all_permits

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
            rows = self._parse_page(html, type_label, type_id)
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

    def _fetch_detail(self, entity_num: str, definement_type) -> str:
        params = {
            'Definement_Entity_Type': definement_type,
            'Entity_Type': 'P',
            'Entity_Number': entity_num,
        }
        try:
            resp = self._session.get(
                f'{self.base_url}{DETAIL_PATH}', params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return resp.text
        except Exception as e:
            _log(f'  [WARN] detail {entity_num}: {e}')
            return ''

    def _parse_page(self, html: str, type_label: str, type_id: int) -> List[Dict]:
        soup = BeautifulSoup(html, 'html.parser')
        permits = []
        for td in soup.select('td.permit_results_item_1'):
            tr = td.find_parent('tr')
            if not tr:
                continue
            permit = _parse_row(tr, type_label, type_id, self.city_name)
            if permit:
                permits.append(permit)
        return permits


def _parse_row(tr, type_label: str, type_id: int, city: str) -> Optional[Dict]:
    first_td = tr.find('td', class_='permit_results_item_1')
    if not first_td:
        return None

    link = first_td.find('a', class_='btn-link')
    entity_num = ''
    definement_type = type_id
    if link and link.get('href'):
        parsed_qs = parse_qs(urlparse(link['href']).query)
        entity_num = parsed_qs.get('Entity_Number', [''])[0]
        raw_def = parsed_qs.get('Definement_Entity_Type', [''])[0]
        if raw_def:
            definement_type = raw_def

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
        'bakasha_description': '',
        'permit_status':      STATUS_MAP.get(status_raw, ''),
        'permit_status_date': '',
        'scrape_status':      'success' if full_address else 'partial',
        '_definement_type':   definement_type,  # removed before returning from scrape()
    }


def _permit_year(permit: Dict) -> int:
    """Extract year from request_date (DD/MM/YYYY). Returns 0 on parse failure."""
    raw = permit.get('request_date', '')
    if raw and len(raw) >= 10:
        try:
            return int(raw[-4:])
        except ValueError:
            pass
    return 0


def _parse_block_lot(tooltip: str) -> str:
    gush = re.search(r'גוש:\s*(\d+)', tooltip)
    helka = re.search(r'חלקה:\s*(\d+)', tooltip)
    if gush and helka:
        return f'{gush.group(1)}-{helka.group(1)}'
    return ''


def _extract_last_page(html: str) -> Optional[int]:
    m = re.search(r'מתוך <span>(\d+)</span>', html)
    return int(m.group(1)) if m else None
