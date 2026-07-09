"""
Bartech municipal permit scraper -- direct API, no Selenium.

Calls the Bartech planning portal directly (no CAPTCHA enforcement).
Two-step process:
  1. SearchPermitApplicationResults -> full permit list (all pages per TypeOfPermit)
  2. PermitApplicationDetails       -> per-permit detail page: stages, request_type, gush/helka

Output schema (same as Complot):
  request_number, request_date, full_address, city, block_lot,
  request_type, request_category, requestor, bakasha_description,
  shimush_ikari, unit_count,
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
    'היתר/טופס 4/גמר':                                     'טופס 4',
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
    # Hadera
    'פתיחה':                                               'בקשה להיתר',
    'תשלום פקדון':                                         'בקשה להיתר',
    'בוצע פרסום':                                          'בקשה להיתר',
    # מיצפה אפק / זמורה / הראל
    'בקרת תכן תקינה':                                      'בקשה להיתר',
    'ישיבה':                                               'בקשה להיתר',
    'בקשה עומדת בתנאים מוקדמים':                          'בקשה להיתר',
    'לאחר פרסום אי עמידה בתנאים מוקדמים':                'בקשה להיתר',
    'לאחר פרסום עמידה בתנאים מוקדמים':                   'בקשה להיתר',
    'בדיקה מרחבית אינה תקינה':                            'בקשה להיתר',
    'בדיקה מרחבית תקינה':                                 'בקשה להיתר',
    'בדיקת מרחבית תקינה':                                 'בקשה להיתר',
    'בקרת תכן אינה תקינה':                                'בקשה להיתר',
    'תשלום אגרות והיטלים':                                'בקשה להיתר',
    'ביטול היתר':                                         'היתר',
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
    'הגשת בקשה להיתר מקוונת במערכת רישוי זמין':           'בקשה להיתר',
    'הוגשה בקשה לבדיקה ראשונית':                          'בקשה להיתר',
    # Hadera
    'ישיבת ועדה מקומית':                                   'בקשה להיתר',
    'שיבוץ בישיבת ועדה מקומית':                            'בקשה להיתר',
    'שיבוץ בועדת מישנה':                                   'בקשה להיתר',
    'דחיה':                                                'בקשה להיתר',
    'הפקת בקשה לאישור תחילת עבודות':                       'היתר',
    'אישור לתחילת עבודות':                                 'היתר',
    'מתן אישור התחלת עבודה':                               'היתר',
    # זמורה / הראל / מיצפה אפק
    'לאשר עם הקלות':                                       'היתר בתנאים',
    'לאשר בתנאי':                                          'היתר בתנאים',
    'לאשר בהסתיגות':                                       'היתר בתנאים',
    'מתן ת. גמר':                                          'טופס 4',
    'לאשר חידוש היתר':                                     'היתר',
    'חתימת היתר במערכת המקוונת':                           'היתר',
    'מתן טופס 2':                                          'היתר',
    'הודעה על התחלת בניה':                                 'היתר',
    'היתר חתום ע"י מהנדס ויו"ר':                          'היתר',
    'תעודת גמר':                                           'טופס 4',
    'הפקת אישור תחילת עבודות':                             'היתר',
    'מתן צו התחלת עבודה':                                  'היתר',
    'מסירת אישור תחילת עבודות':                            'היתר',
    'צו התחלת עבודות':                                     'היתר',
    'הודעה על התחלת הבניה':                                'היתר',
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
    'תוכנית מאושרת בסמכות מהנדס',
    # Krayot — legal / enforcement
    'ישיבה', 'הגשת כתב אישום', 'דיון מישפטי', 'פתיחת תיק פלילי',
    'צו הפסקה מנהלי', 'התראה מיכה',
    # Hadera — Rishuy Zamin and routing
    'בקשה מוכנה לשיבוץ לישיבה',
    'בקרה מרחבית אינה תקינה - נשלחו הערות לעורך',
    'הבקשה הועברה שלב לבקרה מרחבית במערכת רישוי זמין',
    'הבקשה עומדת בתנאים מוקדמים',
    'בוצע פרסום הקלות',
    'בקשה להיתר - לפני ישיבה הועבר לבדיקת מפקח',
    'העבר לבדיקת מח\' הפיקוח - לפני תשלום פיקדון',
    'תשלום פיקדון', 'חישוב פיקדון',
    'פתיחת תיק',
    'פרסום הקלה/שימוש חורג לפי 149',
    'בדיקת תנאים מוקדמים במערכת רישוי זמין',
    'הגשת בקשה במערכת רישוי זמין',
    'חיוב היטלי סלילה',
    'בדיקת תאגיד המים', 'העברה לתאגיד המים',
    'הפצה לגורמי פנים',
    'בקרת תכן תקינה - העברה לסיכום והפקת דרישת תשלום',
    'בדיקת פיקוח לפני ישיבה',
    'הועבר לחישוב היטל שצ"פ',
    'תשלום אגרת בניה', 'עדכון חשבון אגרות',
    'הכנת אגרה -נמסרה הודעה למבקש', 'חישוב אגרת בניה',
    'נשלח מכתב לשכן המסרב לחתו',
    'הערות - בודק היתרים',
    # מיצפה אפק (vmm.co.il) — local licensing meeting workflow
    'שיבוץ לישיבת רישוי מקומית', 'חישוב פקדון', 'בדיקת מפקח',
    'מתן היתר בניה', 'הפקת היתר בניה',
    'בקרת תכן ע"י הוועדה תקינה - העברה לסיכום להפקת דרישות תשלום',
    'הפקת מכתב החלטה', 'שיחת טלפון עם מבקש הבקשה',
    'הפקת ערבות', 'העברת הבקשה לפיקוח', 'העברה לבודקת היתרים',
    'בקשה עומדת בבדיקת תנאים מוקדמים (קבלת הבקשה)',
    'העברת בקשה לבודקות תוכניות',
    'בקרה מרחבית אינה תקינה נשלחו הערות לעורך',
    'הגשת תיקונים רישוי זמין בשלב בקרה מרחבית',
    'אישור מהנדסת הוועדה לשיבוץ לישיבה',
    'סיום טיפול היטל השבחה', 'העברת הבקשה לשמאי לחישוב השבחה',
    'לסרב',
    'בקרת תכן ע"י הוועדה אינה תקינה - נשלחו הערות לעורך',
    'הגשת אישורים לביצוע בקרת תכן',
    'דו"ח מפקח', 'נשלח נוסח פרסום לעורך הבקשה במייל',
    # זמורה (zmora.org.il) — scanning / refinement / admin
    'בקשה חזרה מסריקה ונקלטה במערכת', 'טיוב בקשה', 'סריקת גרמושקות נוספות',
    'הערות', 'חוסרים', 'ישיבת מליאת הועדה',
    'חו"ד מהנדס הוועדה', 'דוח מפקח לרישוי עסק',
    'קבלת טופס לפטור מהיתר', 'קליטה בלבד ללא בדיקה',
    'הפקת פיקדון', 'קליטת ערבות לבקשה',
    'ניתן פירסום לפי סעיף 149 לחוק', 'גמר פירסום לפי סעיף 149 לחוק',
    'מתן טיוטא לנוסח פרסום',
    'בקשה אינה עומדת בתנאים מוקדמים לצורך הפקת נוסח',
    'הזמנת שומה מכתב דרישות', 'הועבר להיטל השבחה',
    'שיבוץ לישיבת מליאה', 'שיבוץ למכינה למליאה', 'שיבוץ למכינה רישוי',
    'שיבוץ לרשות רישוי',
    'בקרה מרחבית אינה תקינה - בדיקה ראשונה',
    'בקרה מרחבית תקינה - בדיקה ראשונה',
    'בדיקת תנאי סף והעברה לשמאי/מפקח',
    'בקרת תכן תקינה העברה לסיכום והפקת דרישת תשלום',
    'קבלת מסמכים הנדרשים לפני התחלת עבודות בניה ( תחילת עבודות)',
    'העברה לבדיקת מפקח לאישור התחלת בניה',
    'אישור מפקח לתחילת עבודות',
    'עדכון המבקש להחזר פיקדון',
    'השלמת דרישות לתעודת גמר', 'התקבלו התנגדויות לבקשה',
    'סגירת הבקשה עקב סירוב', 'החלטה לסרב',
    'קבלת בקשה לרישיון עסק', 'אישור מהנדס לרישוי עסק',
    'בקרת תכן אינה תקינה - נשלחו הערות לעורך',
    'בקשה לבדיקת מפקח לשחרור ערבות',
    'גמר פרסום תקנה 36 ב',
    'סגירה מנהלית אי קידום הבקשה',
    'סיום טיפול  היטל השבחה',
    'בדיקת מפקח לשחרור ערבות',
    'מכתב בקשה לחידוש היתר',
    'הודעה עפ"י תקנה 36 א',
    'לא תקין-גמר הפרסום',
    'לשוב ולדון לאחר סיור במקרקעין',
    'ישיבת דיון בהתנגדויות',
    'העברה לבודקת תוכניות- שרון',
    'העברה לבודק היתרים - עפר קליינמן',
    'הנחיות  מהנדס הועדה',
    'עדכון המליאה',
    # זמורה — construction inspection track
    'אחרי היתר: קבלת טפסים -לפני בנייה', 'אחרי היתר: קבלת טפסים- במהלך בנייה',
    'אי דיווח על התחלת בניה', 'אי התאמת חוזק בטון לתקן', 'אין צורך בדיווח',
    'ביקורת ראשונה באתר הבניה',
    'בדיקת פיקוח - הכל תקין', 'בדיקת פיקוח - לא תקין - נפתח תיק פיקוח',
    'גמר מקלט/ממ"ד', 'גמר ערבות בנקאית',
    'דוחות ביקורת בטונים', 'דיווח בהתאם לתקנות  – אושר',
    'נבדק ונמצא לא תואם לתקנות', 'נבדק ונמצא תואם לתקנות',
    'נבדקה הבקשה לת.גמר ע"י מפקח בניה',
    'שחרור ערבות בנקאית', 'שלבי בניה', 'מסלול רישוי בניה',
    # זמורה — approval/committee
    'אישור המועצה המקומית', 'אישור מהנדס הועדה להתרת שינויים',
    'אישור משרד התחבורה/מע"צ',
    'אישור תוכנית מתוקנת ע"י מהנדס הועדה',
    'אישור תנאים מוקדמים לצורך הפקת נוסח פרסום בלבד',
    'לאשר בתאום עם המהנדס', 'תאום הבקשה עם מהנדס הועדה',
    'חוות דעת מהנדסת הועדה',
    # זמורה — plans/revisions
    'קבלת תוכנית מתוקנת', 'קבלת תכניות מתוקנות לבקשה להיתר מקוונת',
    'קבלת תכנית מעודכנת- לדיון נוסף',
    'ת. מתוקנת-נבדקה ולא תוקנה כראוי', 'ת.מתוקנות נתקבלו/לבדיקה/א',
    'תכנית מתוקנת-נבדקה ולא תוקנה כנדרש-לא מאושר',
    'השלמה בתכניות',
    # זמורה — appeal/legal/enforcement
    'דיון בועדת ערר', 'דו"ח מפקח על עבירת בניה',
    'דוח ביקור באתר לרישיון עסק', 'דוח מפקח ביקורת לפני דיון',
    'הוגשה עתירה מנהלית', 'התקבל ערר', 'החלטת ועדת ערר',
    'עיכוב ועדת ערר', 'עכוב 30 ימים לערר מתנגד', 'פניה לועדת ערר',
    'התראה אי דיווח לפי סעיף 16 תקנה 5',
    # זמורה — routing/admin/misc
    'ביטול בקשה מנהלי', 'ביטול הערת אזהרה',
    'בקשה לחידוש החלטה', 'בקשה למינוי שמאי מכריע',
    'דחיית בקשה להיתר ע"י מערכת רישוי זמין',
    'הארכת תוקף החלטת ועדה לפי תקנה 46',
    'הגשת בקשה להקלה נוספת',
    'הוחזרו מכתבים מפרסום הקלה / שימוש חורג',
    'הועבר לארכיב', 'הועבר לבדיקת מפקח לפני דיון',
    'הועבר למהנדס הוועדה לקבלת חו"ד',
    'החזר כספי', 'החזרת הבקשה לוועדה ללא סריקה',
    'החלטה', 'החלטה לבטל היתר',
    'הפסקת טיפול',
    'הפקת / משלוח במייל גליון דרישות',
    'הפקת דוח פיקוח - אלישע',
    'הפקת מסמך רישום הערה לפי תקנה 27',
    'הצגת מסמכים להשבחה', 'השלמת מסמכים להיטל השבחה',
    'התפטרות עורך / מהנדס מהבקשה להיתר.',
    'חידוש היתר לשנה נוספת בשל תקנות הקורונה',
    'טיוב בקשה לא מאושרת',
    'יש להשלים תנאים מקדמיים לפני דיון בועדה',
    'לארכיון לצרוף תיק ישן',
    'מינוי עורך / מהנדס לבקשה להיתר', 'מינוי שמאי מכריע',
    'ממתין לצרוף תיק ישן', 'מצגת לדיון',
    'משלוח מכתב תקנה 27', 'משלוח מכתב תקנה 36 ( 2 ב\')',
    'נשלח מכתב', 'נשלח מכתב לפרסום הקלה', 'נשלח מכתב על חוסר תיקונים',
    'סירוב מהנדס לרישוי עסק',
    'פטור עד 140', 'פרסום עפ"י תקנה 36',
    'קבלת חוות דעת יועמ"ש',
    'רישום הערת אזהרה בטאבו',
    'שליחת מכתב החלטה למתנגד/ים',
    'תעודת קבלן רשום', 'תשלום אגרת מידע', 'תשלום היטל השבחה',
    # זמורה — person-specific routing
    'העברה לבודקת היתרים - אביה דוד', 'העברה לבודקת היתרים - מירי שטיין',
    'העברה לבודקת רישוי-יפעת קליין',
    'העברה לבודקת תוכניות', 'העברה לבודקת תכניות- נטלי סיאני',
    'העברה לבודקת-הדר דביר',
    'העברה לחוות דעת מהנדסת הועדה',
    'העברה למזכיר ועדה', 'העברה למזכירות / מהנדסת ועדה לבדיקה',
    'העברה למזכירות ועדה', 'העברה לפיקוח', 'העברה לבודק תכניות',
    'העברת מכתב לעורך הבקשה - עפ"י תקנה 36',
    # מיצפה אפק (vmm.co.il) — additional doc routing
    'בקשה טרם נסרקה', 'מסמכים הועלו למערכת', 'תיק הועבר לסריקה',
    'הערה יעודית לפי סעיף 27', 'טיפול מלא בבקשה', 'אין חומר לסריקה',
    'השתתפות בישיבת ועדת מליאה', 'שיבוץ לישיבת ועדת מליאה',
    'חו"ד מהנדס הועדה', 'חישוב היטל השבחה - ועדה', 'בקשה נסרקה',
    # מיצפה אפק — section header labels (appear as stage names in the portal)
    '== מסלול רישוי בניה ==', '== מסלול שלבי בניה ==',
    '=== עררים =====', '=========================',
    # מיצפה אפק — inspection / approval
    'אושר פטור מהשבחה', 'אי עמידה בתנאי החלטת הועדה המקומית',
    'אישור בדיקת מפקח', 'אישור מהנדס להארכת תוקף החלטה לפי תקנה 46',
    'אישור משרד הבריאות', 'אישור ערר', 'אישור ערר חלקי',
    'אישור/פטור הג"א למקלט', 'בדיקה לפטור מהג"א',
    'בדיקת השבחה להיתר', 'בדיקת התאמה להיתר', 'בדיקת התחלת בניה',
    'עמידה בתנאי החלטת הועדה המקומית', 'עמידה בתנאי סף',
    'תכנית עומדת בהחלטת הועדה.',
    'תכנית שינויים בסמכות מהנדס לא תקינה', 'תכנית שינויים בסמכות מהנדס תקינה',
    # מיצפה אפק — warranty/financial
    'ביטול ערבות', 'ביטול צו הפסקת עבודה',
    'החזר אגרה-ביטול היתר', 'החזר היטל השבחה',
    'חישוב אגרה שונה(ביול)', 'חישוב שומה מכרעת', 'חילוט ערבות',
    'הפקת גליון דרישות', 'הפקת היטל השבחה - מקדמה', 'הפקת טופס ביטוך ערבות',
    'ללא חיוב השבחה בהיתר', 'מינוי שמאי מכריע לקביעת היטל השבחה',
    'נשלח לעריכת שומה', 'נשלח מייל לשמאי לעדכון תשלום השבחה',
    'נשלחה דרישת ערבות במייל',
    'תשלום אגרה שונה(ביול)', 'תשלום היטל השבחה - ועדה',
    'תשלום היטל השבחה - מקדמה', 'תשלום שומה מכרעת',
    # מיצפה אפק — technical review
    'בקרת תכן ע"י  מכון בקרה תקינה - העברה לסיכום להפקת דרישות תשלום',
    'בקרת תכן ע"י מכון בקרה אינה תקינה',
    'בקשה אינה עומדת בבקרה מרחבית',
    'בקשה להארכת תוקף החלטה בסמכות מהנדס לפי תקנה 46',
    'הגשת תיקונים ברישוי זמין בשלב בקרה מרחבית',
    'קבלת חו"ד מסכמת לבקרת תכן ממכון בקרה',
    # מיצפה אפק — inspection reports
    'דו"ח פיקוח', 'דו"ח פיקוח - אישור לטאבו', 'דו"ח פיקוח תיק עבירה.',
    'דיווח עורך בקשה על ביצוע שינויים', 'עריכת דוח פיקוח',
    # מיצפה אפק — admin/routing
    'הארכת תוקף אוטומטית בשנה', 'הגשת בקשה לפטור מהג"א',
    'הגשת ערר לפרקליטות לפי סעיף 64',
    'הוגש באתר הועדה', 'הודעה לעורך הבקשה ולמבקש',
    'החלטה להוריד מסדר היום', 'החלטה להעביר למישנה סטטוט',
    'החלטה למחוזית לאישור חורג', 'החלטות', 'החרגת צו הפסקת עבודה',
    'הכנת דף מידע', 'העברה להנהלת חשבונות', 'העברה למהנדסת הוועדה',
    'העברה למח\' היטלי השבחה - חן',
    'העברה למפקח - תכנית שינוייים בסמכות מהנדס',
    'העברה למפקח להזמנה למסירת גירסה', 'העברה למפקח לשחרור ערבות',
    'העברה לשמאי', 'העברת הבקשה לבדיקת השבחה.',
    'העברת התיק למפקח', 'העלאת פירסומים/פרוטוקולים',
    'הפקת אישור להעברה בטאבו',
    'השלמת דרישות', 'השתתפות בישיבת ועדת משנה',
    'התייעצות נותן הצו עם תובע (ישן)', 'התרת שינויים בסמכות מהנדס',
    'ישיבת ועדה',
    'לדחות את ההתנגדות', 'לקבל ההתנגדות ולאשר', 'לקבל ההתנגדות ולסרב',
    'לשוב ולדון', 'מזכר', 'מחיקת הערה', 'מחיקת הערת אזהרה',
    'מענה למכתב התנגדות',
    'נדרשו דיווחים על בניה', 'נדרשו מסמכי השלמה השבחה',
    'ס.85(ב)(1) - החלטת ועדה מקומית על הפקדת תכנית עם שינויים',
    'סגירת בקשה', 'סיום טיפול בערר', 'סיכום מכינה עם מהנדסת הוועדה',
    'סיכום פגישה פרונטלית', 'עררים',
    'פרסום הקלה ותכנית ראשית באתר הוועדה',
    'פתיחת תיק שינויים בסמכות מהנדס הוועדה',
    'רישום הערה יעודית', 'רישום הערת אזהרה בטאבו',
    'רישום הערת אזהרה לפי תקנה 29', 'רשם מקרקעין - אי התאמה להיתר',
    'שיבוץ בישיבת ועדה', 'שיבוץ לישיבת ועדת משנה',
    'תוכנית תנועה ע"י יועץ תנו', 'תיעוד אירוע במערכת ניהול ועדה',
    'תיק נסרק', 'תלונה', 'תשלום היטל השבחה',
    # הראל (v-harel.co.il) — appraisal / inspector / committee
    'תשלום שומת ועדה', 'הפקת שומת ועדה', 'בוצעה שמאות',
    'הבקשה פטורה מהיטל השבחה',
    'קבלת חוות דעת שמאי - אין חבות בהיטלי השבחה',
    'העברה לבדיקת מפקח', 'ביקור מפקח בשטח לפני דיון',
    'פרסום הקלה/שימוש חורג 149',
    'העברה לבקרת תכן',
    '"הראל" - ישיבת מליאה',
    'החלטה לשוב ולדון', 'החלטה לא לאשר',
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
      shimush_ikari       - שימוש עיקרי (primary use — public building filter)
      unit_count          - מספר יח"ד (residential unit count)
      detail_block_lot    - gush-helka from detail page (more accurate than list page)
      permit_status       - highest-ranked status across all stage tables
      permit_status_date  - date of that stage
    """
    soup = BeautifulSoup(html, 'html.parser')

    request_type = _extract_dl_field(soup, 'תאור הבקשה')
    shimush_ikari = _extract_dl_field(soup, 'שימוש עיקרי')
    unit_count = _extract_dl_field(soup, 'מספר יח"ד')

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
        'shimush_ikari':       shimush_ikari,
        'unit_count':          unit_count,
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
        self.max_pages_per_parcel: int = 20   # hard cap per gush/helka to prevent runaway on large blocks

        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._session.headers['Referer'] = f'{self.base_url}/SearchPermitApplication'

    def scrape(self) -> List[Dict]:
        """Full scan across all permit types, filtered by self.min_year."""
        seen: Dict[str, Dict] = {}
        for type_id, type_label in self.permit_types.items():
            _log(f'TypeOfPermit={type_id} ({type_label})...')
            permits = self._scrape_type(type_id, type_label, early_exit_year=self.min_year)
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
        return self._enrich_with_details(seen)

    def scrape_parcels(self, parcel_pairs: List[tuple]) -> Dict[str, Dict]:
        """
        Fetch all permits for the given (gush, helka) pairs without detail enrichment.
        Returns a seen-dict keyed by request_number — pass the result to merge_and_enrich().
        """
        seen: Dict[str, Dict] = {}
        for gush, helka in parcel_pairs:
            page = 1
            zero_new_streak = 0
            while True:
                if self.max_pages and page > self.max_pages:
                    break
                if page > self.max_pages_per_parcel:
                    _log(f'  [CAP] Parcel {gush}-{helka}: hit {self.max_pages_per_parcel}-page cap, stopping')
                    break
                html = self._fetch_parcel_page(gush, helka, page)
                if not html or 'לא נמצאו נתונים' in html:
                    break
                rows = self._parse_page(html, '', 51)  # type_label '' — detail page will correct it
                if not rows:
                    break
                new = 0
                for p in rows:
                    if self.min_year:
                        yr = _permit_year(p)
                        if yr > 0 and yr < self.min_year:
                            continue
                    if p['request_number'] not in seen:
                        seen[p['request_number']] = p
                        new += 1
                _log(f'  Parcel {gush}-{helka} page {page}: {len(rows)} rows, {new} new')
                if new == 0:
                    zero_new_streak += 1
                    if zero_new_streak >= 3:
                        _log(f'  Early exit parcel {gush}-{helka}: 3 consecutive pages with 0 new')
                        break
                else:
                    zero_new_streak = 0
                if self.min_year and rows:
                    years = [_permit_year(r) for r in rows]
                    dated = [y for y in years if y > 0]
                    if dated and all(y < self.min_year for y in dated):
                        _log(f'  Early exit parcel {gush}-{helka}: all pre-{self.min_year}')
                        break
                if len(rows) < 5:
                    break  # last page
                page += 1
                time.sleep(0.3)
        return seen

    def merge_and_enrich(self, *seen_dicts: Dict[str, Dict]) -> List[Dict]:
        """
        Merge multiple seen-dicts (later dicts fill gaps in earlier ones) then
        enrich every unique permit with its detail page. Use for two-phase scrapes.
        """
        merged: Dict[str, Dict] = {}
        for d in seen_dicts:
            for num, permit in d.items():
                merged.setdefault(num, permit)
        return self._enrich_with_details(merged)

    def _enrich_with_details(self, seen: Dict[str, Dict]) -> List[Dict]:
        all_permits = list(seen.values())
        _log(f'\nFetching detail pages for {len(all_permits)} unique permits...')
        total = len(all_permits)
        for i, permit in enumerate(all_permits):
            entity_num = permit['request_number']
            def_type   = permit.pop('_definement_type', list(self.permit_types.keys())[0])
            detail_html = self._fetch_detail(entity_num, def_type)
            if detail_html:
                detail = _parse_detail(detail_html)
                if detail['permit_status']:
                    permit['permit_status']      = detail['permit_status']
                    permit['permit_status_date'] = detail['permit_status_date']
                if detail['request_type']:
                    permit['request_type'] = detail['request_type']
                if detail['bakasha_description']:
                    permit['bakasha_description'] = detail['bakasha_description']
                if detail['shimush_ikari']:
                    permit['shimush_ikari'] = detail['shimush_ikari']
                if detail['unit_count']:
                    permit['unit_count'] = detail['unit_count']
                if detail['detail_block_lot']:
                    permit['block_lot'] = detail['detail_block_lot']
            if (i + 1) % 200 == 0:
                _log(f'  [{i + 1}/{total}] detail pages fetched')
            time.sleep(0.2)
        _log('Detail phase complete.')
        return all_permits

    def _scrape_type(self, type_id: int, type_label: str,
                     early_exit_year: Optional[int] = None) -> List[Dict]:
        """
        Scrape all pages for a single TypeOfPermit.
        If early_exit_year is set, stops as soon as an entire page contains only
        permits older than that year (by request_date). Permits with unparseable
        dates are treated as recent and never trigger early exit.
        """
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
            if early_exit_year and rows:
                years = [_permit_year(r) for r in rows]
                dated = [y for y in years if y > 0]
                if dated and all(y < early_exit_year for y in dated):
                    _log(f'  Early exit: all permits on page {page} are pre-{early_exit_year}')
                    break
            if last_page and page >= last_page:
                break
            page += 1
            time.sleep(0.3)
        return permits

    def _fetch_parcel_page(self, gush: str, helka: str, page: int) -> str:
        params = {
            'searchType': 'ByDetails',
            'GushNumber': gush,
            'HelkaNumber': helka,
            'g-recaptcha-response': 'x',
            'page': page,
        }
        try:
            resp = self._session.get(
                f'{self.base_url}{RESULTS_PATH}', params=params, timeout=30)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return resp.text
        except Exception as e:
            _log(f'  [WARN] parcel {gush}-{helka} page {page}: {e}')
            return ''

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
        'shimush_ikari':      '',
        'unit_count':         '',
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
