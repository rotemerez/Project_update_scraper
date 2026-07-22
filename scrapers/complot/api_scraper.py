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
    'הפקת תעודת גמר':                                              'טופס 4',
    'מסירת תעודת גמר':                                             'טופס 4',
    'תעודת גמר':                                                   'טופס 4',  # standalone — catch-all after more specific variants
    'הפקת טופס 4 מותלה':                                           'טופס 4',
    'הפקת טופס נלווה לטופס 4':                                     'טופס 4',
    'הפקת טופס 4':                                                  'טופס 4',
    'מסירת טופס 4':                                                 'טופס 4',
    # היתר
    'מתן היתר למבקש':                                              'היתר',
    'מסירת היתר(בסמכות מהנדס)':                                   'היתר',
    'מסירת היתר':                                                  'היתר',
    'הפקת טופס 2':                                                 'היתר',
    'בדיקת פיקוח כללית בשטח':                                     'היתר',
    'מסירת היתר בניה !':                                           'היתר',
    'חתימת היתר בניה':                                             'היתר',
    'חתימת היתר':                                                  'היתר',
    'הפקת אישור תחילת עבודות':                                     'היתר',
    'אישור המפקח לתחילת עבודות':                                   'היתר',
    # היתר בתנאים
    'החלטה לאשר בתנאי/ם':                       'היתר בתנאים',
    'הפקת היתר בניה לחתימות':                  'היתר בתנאים',
    'הפקת היתר בניה':                          'היתר בתנאים',
    'הכנת היתר טיוטא לחתימות בלבד':            'היתר בתנאים',
    'תשלום אגרת בניה':                          'היתר בתנאים',
    'חישוב אגרת בניה':                          'היתר בתנאים',
    'החלטה לאשר':                               'היתר בתנאים',
    'אושר בועדה':                               'היתר בתנאים',
    'מאשרים בתנאים':                            'היתר בתנאים',
    'העברה להוצאת היתר':                        'היתר בתנאים',
    'החלטה להמליץ למחוזית לאשר':               'היתר בתנאים',  # local committee recommends district approval
    # בקשה להיתר
    'פתיחת בקשה להיתר':                         'בקשה להיתר',
    'פתיחת בקשה':                               'בקשה להיתר',   # catches 'היסטורית' and plain variants
    'ישיבת ועדת משנה':                          'בקשה להיתר',
    'ישיבת רשות רישוי':                         'בקשה להיתר',
    'הפקת מכתבי החלטה':                         'בקשה להיתר',
    'שיבוץ לועדת משנה':                         'בקשה להיתר',
    'שיבוץ לרשות רישוי':                        'בקשה להיתר',
    'שיבוץ לישיבת ועדה':                        'בקשה להיתר',
    'בהכנה לוועדה':                             'בקשה להיתר',
    'ישיבת ועדת רשות רישוי':                    'בקשה להיתר',
}

# Known event strings that are intentionally not mapped -- admin/processing steps
# or permit-closed events that don't represent a milestone we track.
# Listed here so we don't need to re-investigate them.
_UNMAPPED_EVENTS = {
    'סיום טיפול בבקשה להיתר ללא הוצאת היתר',  # closed without permit -- not a trackable milestone
    'בקשה ללא היתר',                             # closed -- permit without issuance
    'היתר היסטורי',                              # historical permit -- pre-digital, no milestone value
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
    'אישור העברת בקשה לחישובי אגרות',
    # scheduling/scanning admin
    'הוסר מסדר היום',
    'החזרת תיק מסריקה',
    # betterment levy admin
    'בדיקת שמאי פנימי להיטל השבחה',
    # licensing authority / inspector / committee admin
    'הדפסת מכתבי החלטה',
    'מיועד לישיבת רשות רישוי',
    'המתנה לבדיקת מפקח',
    'הבקשה מתאימה למציאות',
    'הבקשה לא מתאימה למציאות',
    'בדיקת מפקח לבקשה להיתר',
    'תשלום אגרת תאגיד',
    'חישוב אגרת תאגיד',
    'ישיבת מליאת הועדה',
    'ישיבת מליאת הועדה המקומית',
    'ישיבת מליאה',
    # ישובי הברון — admin/routing events
    'פתיחת תיק',
    'שליחת מכתבי החלטה',
    'החלטה לדחות את הדיון',
    'החלטה לא לאשר',
    'בדיקת מפקח',
    'תיק הועבר לבדיקת מפקח',
    'אישור מחלקת השבחה להפקת היתר',
    'התיק הועבר לדיון',
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
    # appeals / legal — outcome unknown, not a trackable milestone
    'דיון בועדת ערר',
    # inspection / admin — Kiryat Ata and similar cities
    'בטיפול אתי',          # "being handled by Eti" — staff routing note
    'בטיפול צחי',          # "being handled by Tzachi" — staff routing note
    'העברת הבקשה לפיקוח',
    'הסכמת השותפים במגרש לבניה',
    'חישוב פיקדון',
    'הוכחת בעלות על הנכס',
    'אישור בעלי הנכס + תז',
    'ישיבת רשות רישוי מקומית',
    'מפת קווי בנין',
    'מפת מודד מוסמך מעודכנת',
    # dangerous-building declaration events (separate municipal process, not a permit milestone)
    'פתיחת תיק מבנה מסוכן',
    'תאריך פניה לבדיקת מבנה מסוכן',
    'תאריך סיור מהנדס הכרזה מבנה מסוכן',
    'המבנה מוכרז כמבנה מסוכן',
    'תאריך שליחת חו"ד מסוכנות לבעלי הנכס',
    # Kiryat Ata — additional admin/routing events
    'בדיקה ראשונית', 'בדיקה טכנית',
    'בטיפול גלית', 'בטיפול המבקש', 'בטיפול המתכנן',  # staff routing
    'בקשה לא פעילה',
    'ביטול מתן שירותי חשמל, מים וטלפון',
    'הדמיה',
    'הסכמת שכנים בגבול המשותף',
    'העברה לבודק/ת תוכניות', 'העברה לבקרה מרחבית',
    'העברה להתייחסות הפיקוח על הבניה', 'העברה להתייחסות חזות עיר', 'העברה להתייחסות תשתיות',
    'הפקת גליון דרישות',
    'השלמת תנאי סף טכניים', 'השלמת תנאי סף להתחלת בדיקה', 'השלמת תנאי סף לכניסה לדיון',
    "חוות דעת - מבנה תמ''א 38 - סרוק",
    'חישוב היטלים',
    "מכתב לפי תקנה 36ב' (2 ב' בעבר)",
    'מסירת פרסום',
    'מפת פיתוח - חניה',
    'סריקת גרמושקה',
    'פרסום',
    'פתיחת תיק בנין',
    'קיימות הקלות בבקשה',
    'רישוי עסקים',
    "שליחת הודעה לשותפים לנכס ע\"פ תקנה 2ב'",
    'שליחת צ`ק ליסט למתכנן',
    'תאריך הגשה ראשונה לפני בדיקת תנאים מוקדמים', 'תאריך עמידה בתנאים מוקדמים',
    'תכנית ממוחשבת',
    'תשריט חלוקה/מפות לרישום',
    'אישור ביצוע פרסום', 'אישור מ.מ.י.', 'אישור תחילת עבודה',
    # מורדות כרמל — admin/inspection/bond/appraiser events
    'בדיקה לשחרור ערבות',
    'פתיחת ערבות',
    'סיום ושחרור ערבות',
    'דוח מפקח',
    'דיווח מפקח בשלבי בניה',
    'דו"ח פיקוח לפני וועדה',
    'דו"ח ביקור לטופס 4',
    'העברת נתונים לשמאי לעריכת שומה',
    'החזרת התיק משמאי',
    'השלמת דרישות בקרת תכן',
    'אי השלמת דרישות בקרת תכן',
    'המתנה לתיקון תכנית אצל העורך',
    'הגשת הבקשה מחדש',
    'העברת תכנית לפיקוח',
    'שיבוץ לישיבת מליאה',
    'הודעה על פרסום הקלה',
    # publication / misc admin
    'גמר פרסום',
    'הוגשה תכנית מתוקנת',
    'הפקת אגרות והיטלים',
    'שיבוץ בקשה לדיון / למאגר',
    # ישובי הברון full-scrape — admin/routing/inspection/financial events
    '-----------תחילת עבודות--------------',
    '(תשלום) לא משחרר את הבקשה',
    '***   ת ש ל ו מ י ם  ***',
    '**** בקשה להיתר ***',
    '**** מסלול ערבויות ****',
    '=========================',
    'אי עמידה בתנאי סף',
    'אישור הג"א',
    'אישור היתר שינויים בסמכות מהנדס',
    'אישור מכון בקרה לתעודת גמר',
    'ארועי  פיקוח  על  הבניה',
    'בדיקה טכנית - אישור', 'בדיקה טכנית - סירוב',
    'בדיקת מפקח הועדה',
    'בדיקת מפקח לאישור תחילת עבודות',
    'בדיקת תוכניות בועדה',
    'בטול בקשה',
    'ביטול/החזר פיקדון',
    'ביקור מפקח באתר',
    'בקשה לחיבור חשמל (טופס 4)',
    'גמר ערבות',
    'דחיית בקשה לאישור תחילת עבודות',
    'דחיית בקשה לת.גמר אי התאמה',
    'דרישה לתשלום הוצאות הריסה',
    'דרישות לטופס 4 מותלה',
    'הארכת ערבות',
    'הבקשה אינה עומדת בתנאי הבקרה המרחבית',
    'הבקשה התקבלה ועברה לבדיקת השלמת תנאים מוקדמים',
    'הבקשה לא עמדה בבדיקת בקרה מרחבית והוחזרה לתיקונים',
    'הבקשה לא עמדה בתנאי החלטת הועדה והוחזרה לעורך הבקשה',
    'הבקשה לא עמדה בתנאים מוקדמים לצורך הפקת נוסח פרסום',
    'הבקשה לשינויים בסמכות מהנדס עומדת בתנאים',
    'הבקשה נדחית עקב אי עמידה בתנאים המוקדמים',
    'הבקשה עמדה בבדיקת בקרה מרחבית',
    'הבקשה עמדה בתנאי החלטת הועדה ועברה לשלב התכן',
    'הבקשה עמדה בתנאים המוקדמים ועברה לבקרה המרחבית',
    'הבקשה עמדה בתנאים מוקדמים(1) לצורך הפקת נוסח פרסום.',
    'הוגש ערר על החלטת ועדה',
    'הוספת/תיקון חץ צפון',
    'הועבר לאחראית אזור',
    'הועבר למזכירת הפיקוח',
    'הועבר לרישוי פעם ראשונה',
    'החזרה משמאי הועדה',
    "החזרת התיק ממח' פיקוח",
    'החזרת תיק למזכירת פיקוח',
    'החזרת תיק פיקוח מהמפקח',
    'המתנה לתיקון תוכנית אצל העורך',
    'העברה לשמאי הועדה',
    'העברת הבקשה לאישור וחתימת מהנדס הועדה',
    'העברת התיק לתובע הועדה',
    'העברת התיק מפיקוח לאחראית איזור',
    'העברת מפת מסד לפיקוח',
    'העברת תיק לרישוי לפי בקשת',
    'העברת תיק פיקוח למפקח',
    'הפקת אישור לרישום בית משותף',
    'הפקת הודעות לגובלים על פרסום הקלה',
    'הפקת היתר שבוטל',
    'הפקת טופס הפנייה למשרדים',
    'הפקת נוסח פרסום להקלה לפי סעיף 149',
    'הפקת נוסח פרסום לפי תקנה 36 ד',
    'השלמת דרישות בקרת התכן',
    'השלמת כלל הדרישות לתעודת גמר',
    'השלמת תכניות הגשה, תיקוני',
    'השלמת תנאים לטופס 4',
    'התיק הועבר לדיון - ועדת משנה',
    'התיק הועבר לדיון - מליאה',
    'התיק הועבר לדיון - משנה להתנגדויות',
    'התיק מוחזר לרישוי',
    'התקבלה בקשה חדשה להיתר במערכת רישוי זמין לבדיקת תנאים מוקדמים',
    'התקבלה בקשה להיתר לבדיקת תנאים מוקדמים',
    'התראה',
    'התראה להתנגדות בתיק בניין',
    'חוות דעת משרד הבריאות',
    'חוות דעת שרותי כבאות',
    'חזרת רשיון עסק ממפקח',
    'חישוב אגרת ביטולים',
    'חישוב אגרת הפרשים',
    'חישוב אגרת מידע/זכויות',
    'חישוב היטל השבחה',
    'טופס המלצה למחוזית',
    'טופס הפנייה למשרדים',
    'ישיבת וועדת משנה', 'ישיבת משנה להתנגדויות',
    'כתיבת סיכום דיון',
    'לא הושלמו דרישות בקרת התכן',
    'מינוי מכון בקרה / השלמת מסמכים לבקרת תכן',
    'מכתב עבודות עפר ויסודות',
    'מכתבי החלטה למתנגדים',
    'מסירת הודעה על חיוב היטל השבחה',
    'מענה וסיכום',
    'משלוח מידע / זכויות למבקש',
    'מתן היתר לשימוש חורג לחמש שנים',
    'מתן היתר לשימוש חורג לשלוש שנים',
    'מתן היתר לשימוש חורג לשנתיים',
    'נתקבלה בקשה לבדיקת עמידה בתנאי החלטת הוועדה',
    'נתקבלה בקשה לבדיקת עמידת תנאים לשלב התכן',
    'נתקבלה בקשה להתרת שינויים בסמכות מהנדס',
    'נתקבלה בקשה לרישום בית משותף',
    'סגירת תיק ללא היתר',
    'סימון',
    'עמידה בתנאי סף',
    'פיקוח יזום',
    'פירוט שטחים לאגרות',
    'פרסום בעתונות', 'פרסום בעתונים',
    'פרסום פרוטוקול באינטרנט',
    'פתיחת תיק רישוי זמין ואי עמידה בתנאים מקדימים',
    'פתיחת תיק רישוי זמין ועמידה בתנאים מקדימים',
    'קבלת בקשה לאישור תחילת עבודות',
    'קבלת בקשה לשחרור ערבות בנקאית',
    'קבלת בקשה לשינויים בסמכות מהנדס',
    'קבלת בקשה לת.גמר',
    'קבלת בקשה לתעודת גמר',
    'קבלת התנגדות',
    'קבלת מפת מסד',
    'קבלת ערבות',
    'קבלת תוכניות מתוקנות',
    'קבלת תיק מידע מרשוי זמין',
    'קליטת בקשה לאישור תחילת עבודות',
    'קליטת בקשה לת. כמר',
    'שונות',
    'שליחת הודעה לשותפים בחלקה לפי תקנה  2ב',
    'שליחת מכתב הערת אזהרה',
    'שליחת מכתב תיקונים לעורך',
    'שליחת נוסח פירסום בדוא"ל',
    'ת.גמר - אישור הפיקוח על הבניה',
    'ת.גמר - בדיקת מפקח',
    'ת.גמר - העברה לבדיקת פיקוח',
    'תוכנית מתוקנת - הועבר לרי',
    'תיק הועבר לבדיקת טופס 4',
    'תשלום אגרת הפרשים',
    'תשלום אגרת מידע/זכויות',
    'תשלום הועבר לבקשה חדשה אגרת פיקדון/אגרה',
    'תשלום/פטור - היטל השבחה',
    # מורדות כרמל triage export (colleague, 2026-07-15/16) — admin/inspection/legal/publication noise
    'החזרת תוכנית לרישוי  בצירוף דו"ח', 'בדיקת תכניות בועדה.', 'מכתב לתפוגה/חילוט ערבות', 'שליחת שומה למבקש',
    'מסירת אישור תחילת עבודה', 'העלאת פרסום באינטרנט', 'הארכת תוקף ערבות לשנה', "דווח מהנדס - בקורת שלב א'",
    'קבלן רשום - עדכון פרטים', 'דווח מהנדס - בקורת שלב ב\'', 'דווח מהנדס - בקורת שלב ג\'', 'הארכת תוקף ערבות לחצי שנה',
    'הגשת בקשה מחדש בקרת תכן', 'דווח אדריכל - בקורת שלב ד', 'עמידה בתנאי סף להפקת נוסח פרסום', 'הודעה להגשת ערר',
    'העברת הבקשה לפיקוח לאחר החלטה', 'הבקשה נמצאת במסלול עם מכון בקרה', 'קבלת תכנית שינויים לבדיקה',
    'היתר שינויים בסמכות מהנדס חתום.', 'תכנית בינוי מאושרת', 'חתימת תוכנית השינויים ע"י המהנדסת',
    'הבקשה אינה עומדת בתנאי סף', 'הגשת בקשה מתוקנת לוועדה', 'הפקת אישור הרצת מערכות', 'מסירת אישור הרצת מערכות',
    'הפקת טופס 4 להרצת מערכות',  # systems commissioning checkpoint, not real טופס 4 -- see _map_event()
    'מודד-סימון קווי בנין+0.00', 'מסירת טופס 2 להרצת מערכות בלבד', 'הגשת מפה מצבית', 'הכנת תיק לדיון בועדה',
    'בקרה מרחבית אינה תקינה', 'מסמך פנימי', 'דוח פיקוח יזום', 'התחלת בניה וגידור', 'ממתין להשלמות',
    'הארכת תוקף החלטת ועדה', 'הודעה על פרסום שימוש חורג', 'התכתבות', 'להוריד מסדר יום', 'חידוש היתר',
    'הפקת טופס 4 לחיבור חשמל', 'בדיקה אדריכלית', 'בקרה מרחבית תקינה', 'העברת תשריט בית משותף למפקח',
    'מכתב לעורך-השלמת דרישות', 'קבלת פרסום חלקי', 'דו"ח ביקור במקום', 'החלטה לפרסם', 'ש ל ב י    ב נ י ה',
    'בדיקת תשריט בית משותף ברישוי', 'קבלת פרסום ב-3 עיתונים', 'שליחת פרסום הודעה לפי סעיף 5 ו 7 לפקודת הקרקעות',
    'אישור פרסום ילקוט פרסומים לפי סעיף 5 ו-7', 'הודעה טלפונית למבקש', 'הודעת מינוי אחראי לביקורת',
    'השלמת פרסום הקלה', 'התחלת תהליך לאישור תחילת עבודות', 'חישוב אגרה עבור דיון', 'סגירת תיק-אי תשלום פיקדון',
    'אי עמידה בתנאי ההיתר', 'אישור פרסום בילקוט פרסומים לפי סעיף 19', 'בדיקה מרחבית תקינה',
    'השלמת עבודות ושחרור ערבות', 'טיפול בהתנגדויות', 'תשריט בית משותף חתום.', 'בדיקת שטחים', 'דו"ח פיקוח מסכם',
    'התנגדות להקלה', 'מודד-ביצוע קווי בנין+0.00', 'מועד ביצוע העבירה', 'מכתב מעו"ד - מסמכים', "פת' בקשה עקרונית",
    'פתיחת תיק לתוכנית בינוי', 'שליחת פרסום בדואר', 'שליחת פרסום הודעה לפי סעיף 19 לפקודת הקרקעות',
    'תזכורת לעורך לאחר הודעה', 'תכנית שינויים אינה בסמכות מהנדס.', '------------------------',
    '----------------------------------', 'אי הופעה לדיון משפטי', 'בדיקה מרחבית אינה תקינה',
    'בדיקת בטון 7 ימים - לקוי', 'דו"ח פיקוח', 'דו"ח פיקוח טרם חתימת ההיתר', 'הארכת ערבות להבטחת ת.היתר',
    'הארכת תוקף ערבות לשנתיים', 'הודעה טלפונית לעורך', 'הודעה על מינוי אחראי לביצוע שלד', 'החלטת ו.מחוזית-לאשר',
    'החלפת ערבות', 'הסרת התנגדות', 'הריסה', 'השלמת הליך להוצאת היתר (2)', 'השלמת טיפול אדריכלי', 'חילוט הערבות',
    'ישיבות', 'מכתב תשובה', 'מעקב עתידי', 'סגירת בקשה ברישוי', 'פניה לעורך לתיאום אדריכלי', 'קיימת ערבות בתיק אחר',
    'תצהיר אחראי לביצוע שלד',
}

# Events that require manual human review — surfaced as flag='manual_review' in the report.
# Not assigned a status rank; do not contribute to permit_status.
_MANUAL_REVIEW_EVENTS = {
    'הוצאת היתר בניה',         # permit issuance — ambiguous; may or may not mean the permit is signed
    'ביטול היתר',               # permit cancellation — project may have stalled
    'החלטת ועדת ערר',           # appeals committee decision — outcome unknown
    'הפקת פרסום תמ"38',         # tama38 publication step — significance unclear
    'עיכוב היתר ע"י ועדת ערר',  # permit delay by appeals committee — project stalled
    # מורדות כרמל triage export (colleague, 2026-07-15/16) — outcome/status not yet knowable from this event alone
    'הגשת בקשה ברישוי זמין', 'החלטה לדחות את הבקשה', 'החלטה לתקן החלטת ועדה', 'דוח פיקוח תשריט בית משותף',
    'החלטת ו. עררים-לדחות ערר', 'העברת פיקדון לבקשה אחרת', 'החזר פיקדון', 'החלטת ו. עררים-לקבל ערר',
    'מסירת תשריט בית משותף', 'ביטול ערר', 'שינוי שם המבקש', 'ביטול בקשה ע"י המבקש', 'דחיית הבקשה והחזר הפיקדון',
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
    # "הרצת מערכות" (systems commissioning/trial-run) is a pre-occupancy technical checkpoint,
    # not a real milestone -- confirmed by colleague review (Ashkelon permit 20220897, 2026-07-22)
    # that a 'הפקת טופס 4 להרצת מערכות' event does NOT mean the building reached true טופס 4
    # (occupancy/completion). Checked before the substring loop so it can never fall through to
    # a less-specific 'טופס 4' key.
    if 'הרצת מערכות' in event:
        return ''
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
                 min_year: Optional[int] = None,
                 year_filter: Optional[List[int]] = None,
                 b_params: Optional[List[int]] = None):
        self.site_id = site_id
        self.city_name = city_name_hebrew
        self.min_year = min_year
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
          request_type, request_category, shimush_ikari, requestor,
          permit_status, permit_status_date, scrape_status
        """
        _log(f'Fetching permit list for site_id={self.site_id}...')
        permit_list = self._get_permit_list()
        if not permit_list:
            _log('[ERROR] Empty permit list -- aborting.')
            return []

        _log(f'Got {len(permit_list)} unique permits after deduplication')

        if self.min_year:
            before = len(permit_list)
            permit_list = [p for p in permit_list if self._passes_min_year(p['request_date'])]
            _log(f'min_year={self.min_year}: {before} -> {len(permit_list)} permits')
        elif self.year_filter:
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
          shimush_ikari        - שימוש עיקרי (main use of the building)
          unit_count           - סך מספר יחידות דיור המבוקשות (requested unit count)
          event                - most recent mappable event description
          event_date           - date of that event
          applicant_name       - מבקש row from בעלי עניין table
          migrash              - מספר מגרש from גושים וחלקות table
        """
        soup = BeautifulSoup(html, 'html.parser')

        request_type        = _extract_field(soup, 'תיאור הבקשה')
        request_category    = _extract_field(soup, 'סוג הבקשה')
        bakasha_description = _extract_section_text(soup, 'מהות הבקשה')
        shimush_ikari       = _extract_field(soup, 'שימוש עיקרי')
        unit_count          = _extract_field(soup, 'סך מספר יחידות דיור המבוקשות')
        permit_issue_date   = _extract_field(soup, 'תאריך הפקת היתר')

        # Events table: find by 'תיאור אירוע' header
        event_table = _find_table_with_header(soup, 'תיאור אירוע')
        best_event = ''
        best_event_date = ''
        best_rank = -1
        first_event_date = ''
        manual_review_event = ''
        manual_review_event_date = ''

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

                # Track manual review events (keep most recent by date)
                if event_desc in _MANUAL_REVIEW_EVENTS:
                    if not manual_review_event_date or _earlier_date(manual_review_event_date, event_date):
                        manual_review_event = event_desc
                        manual_review_event_date = event_date

                status = _map_event(event_desc)
                rank = STATUS_ORDER.index(status) if status in STATUS_ORDER else -1
                if rank > best_rank:
                    best_rank = rank
                    best_event = event_desc
                    best_event_date = event_date

                if event_desc and event_desc not in _UNMAPPED_EVENTS \
                        and event_desc not in _MANUAL_REVIEW_EVENTS and not status:
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
            'shimush_ikari':       shimush_ikari,
            'unit_count':          unit_count,
            'permit_issue_date':   permit_issue_date,
            'manual_review_event': manual_review_event,
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
        permit_status_date = detail.get('event_date', '')
        # תאריך הפקת היתר is a header field that reliably marks permit issuance.
        # Use it to set status=היתר when events don't already show something equal or higher.
        permit_issue_date = detail.get('permit_issue_date', '')
        if permit_issue_date:
            issue_rank = STATUS_ORDER.index('היתר')
            current_rank = STATUS_ORDER.index(permit_status) if permit_status in STATUS_ORDER else -1
            if issue_rank > current_rank:
                permit_status = 'היתר'
                permit_status_date = permit_issue_date
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
            'bakasha_description':  detail.get('bakasha_description', ''),
            'shimush_ikari':        detail.get('shimush_ikari', ''),
            'unit_count':           detail.get('unit_count', ''),
            'manual_review_event':  detail.get('manual_review_event', ''),
            'requestor':            requestor,
            'permit_status':       permit_status,
            'permit_status_date':  permit_status_date,
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
                    'bakasha_description':  record.get('bakasha_description', ''),
                    'shimush_ikari':        record.get('shimush_ikari', ''),
                    'unit_count':           record.get('unit_count', ''),
                    'manual_review_event':  record.get('manual_review_event', ''),
                    'applicant_name':       record.get('requestor', ''),
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

    def _passes_min_year(self, date_str: str) -> bool:
        if not date_str:
            return True  # can't parse — include to avoid silent drops
        for fmt in ('%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(date_str, fmt).year >= self.min_year
            except ValueError:
                continue
        return True

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


_SECTION_STOPS = frozenset(['בעלי עניין', 'גושים וחלקות', 'שלבי הבקשה', 'תאריך אירוע', 'שלבי בניה'])


def _extract_section_text(soup: 'BeautifulSoup', header_text: str) -> str:
    """
    Find a section-header element by exact text and collect the free text that follows it,
    stopping at the next known section boundary.
    Handles both <td>-row and <div>-based page structures.
    """
    for tag in soup.find_all(string=lambda t: t and t.strip() == header_text):
        block = tag.find_parent()
        # Walk up past inline containers to the nearest block element
        while block and block.name in ('span', 'strong', 'em', 'b', 'a', 'label', 'font'):
            block = block.find_parent()
        if block is None:
            continue
        # For table cells, move up to the row so next_siblings are peer rows
        if block.name == 'td':
            row = block.find_parent('tr')
            if row:
                block = row
        parts = []
        for sibling in block.find_next_siblings():
            text = sibling.get_text(separator=' ', strip=True)
            if not text:
                continue
            if any(s in text for s in _SECTION_STOPS):
                break
            parts.append(text)
        if parts:
            return ' '.join(parts)
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
