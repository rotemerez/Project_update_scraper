# Session Handoff — 2026-07-09 D

**Date:** 2026-07-09  
**Session:** I  
**Scope:** Zmora + Harel smoke tests; Bartech scraper updated; 3 full scrapes launched; ישובי הברון portal investigation

---

## What was accomplished

### 1. Bartech scraper updated — `scrapers/bartech/api_scraper.py`

From smoke tests of zmora.org.il (2 pages) and v-harel.co.il (2 pages):

**STATUS_MAP additions** (list-page statuses):
- `לאחר פרסום עמידה בתנאים מוקדמים` → `'בקשה להיתר'` (note: without "אי" — meets preconditions)
- `בדיקת מרחבית תקינה` → `'בקשה להיתר'` (variant with ת vs existing `בדיקה מרחבית תקינה` with ה)
- `תשלום אגרות והיטלים` → `'בקשה להיתר'` (from הראל)
- `ביטול היתר` → `'היתר'` (permit was issued, then cancelled)

**STAGE_TO_STATUS additions** (detail-page stages → milestone):
- `היתר חתום ע"י מהנדס ויו"ר` → `'היתר'`
- `תעודת גמר` → `'טופס 4'` (completion certificate = Form 4 equivalent)
- `הפקת אישור תחילת עבודות` → `'היתר'`
- `מתן צו התחלת עבודה` → `'היתר'` (from הראל)

**`_UNMAPPED_STAGES` additions** (~30 entries tagged `# זמורה / הראל`):
Zmora: `בקשה חזרה מסריקה ונקלטה במערכת`, `טיוב בקשה`, `סריקת גרמושקות נוספות`, `הערות`,
`חוסרים`, `ישיבת מליאת הועדה`, `חו"ד מהנדס הוועדה`, `דוח מפקח לרישוי עסק`,
`קבלת טופס לפטור מהיתר`, `קליטה בלבד ללא בדיקה`, `הפקת פיקדון`, `קליטת ערבות לבקשה`,
`ניתן פירסום לפי סעיף 149 לחוק`, `גמר פירסום לפי סעיף 149 לחוק`, `מתן טיוטא לנוסח פרסום`,
`בקשה אינה עומדת בתנאים מוקדמים לצורך הפקת נוסח`, `הזמנת שומה מכתב דרישות`,
`הועבר להיטל השבחה`, `שיבוץ לישיבת מליאה`, `שיבוץ למכינה למליאה`, `שיבוץ למכינה רישוי`,
`שיבוץ לרשות רישוי`, `בקרה מרחבית אינה תקינה - בדיקה ראשונה`,
`בקרה מרחבית תקינה - בדיקה ראשונה`, `בדיקת תנאי סף והעברה לשמאי/מפקח`,
`בקרת תכן תקינה העברה לסיכום והפקת דרישת תשלום`,
`קבלת מסמכים הנדרשים לפני התחלת עבודות בניה ( תחילת עבודות)`,
`העברה לבדיקת מפקח לאישור התחלת בניה`, `אישור מפקח לתחילת עבודות`,
`עדכון המבקש להחזר פיקדון`, `השלמת דרישות לתעודת גמר`, `התקבלו התנגדויות לבקשה`,
`סגירת הבקשה עקב סירוב`, `החלטה לסרב`

Harel: `תשלום שומת ועדה`, `הפקת שומת ועדה`, `בוצעה שמאות`, `הבקשה פטורה מהיטל השבחה`,
`קבלת חוות דעת שמאי - אין חבות בהיטלי השבחה`, `העברה לבדיקת מפקח`,
`ביקור מפקח בשטח לפני דיון`, `פרסום הקלה/שימוש חורג 149`, `העברה לבקרת תכן`,
`"הראל" - ישיבת מליאה`, `החלטה לשוב ולדון`, `החלטה לא לאשר`

### 2. 3 Bartech full scrapes launched (~14:03)

| Scraper | Portal | City | Pages (type 51) | min_year | Status at session end |
|---|---|---|---|---|---|
| `run_mitzpe_afek.py` | vmm.co.il | באר יעקב | 5,627 | 2014 | List phase, type 71 ~p70/210 |
| `run_zmora.py` | zmora.org.il | מזכרת בתיה | 3,499 | 2016 | Detail phase (new warnings below) |
| `run_harel.py` | v-harel.co.il | מבשרת ציון | 1,654 | 2017 | **DONE** — 1,145 permits |

Outputs:
- `outputs/harel_fresh.csv` — complete, ready for matcher
- `outputs/zmora_fresh.csv` — will exist when scrape completes
- `outputs/mitzpe_afek_fresh.csv` — will exist when scrape completes

**Zmora full-run new warnings** (seen mid-session, not yet added to scraper):
- `קבלת בקשה לרישיון עסק` → `_UNMAPPED_STAGES` (business license intake, not construction)
- `אישור מהנדס לרישוי עסק` → `_UNMAPPED_STAGES` (engineer approval for business license)
Add these at the start of the next session before running the matcher.

### 3. ישובי הברון portal investigated

Portal URL: `https://www.vaada-habaron.org.il/newengine/Pages/request2.aspx`  
(Note: bare domain without `www.` returns 404)

Platform: SharePoint 2013 + **Ext.NET** (Sencha WebForms component library).

Key findings:
- Data is rendered client-side by JavaScript — `requests` sees empty tables
- SP REST API (`/_api/web/lists`) — connection reset (blocked)
- SP SOAP (`/_vti_bin/lists.asmx`) — 401 Unauthorized
- Search modes available: permit number (`bakasha`), gush/parcel number (`taba`), meeting number (`meeting`)
- No "browse all" permits endpoint in plain HTML
- Navigation: `/newengine/Pages/gush2.aspx`, `taba2.aspx`, `buildings2.aspx`, `meetings2.aspx` all return 200 but JS-rendered (empty tables in static HTML)

**Next step: browser DevTools inspection.** Open site in Chrome, search by a known gush number for one of the target cities, capture the Network tab POST request. The Ext.NET grid must call an endpoint to fetch rows — find it. If the endpoint is replicable with `requests`, build a scraper with gush enumeration per city. If not, use Playwright.

Cities: זכרון יעקב (62 projects), אור עקיבא (45), בנימינה גבעת עדה (42), ג'סר א-זרקא.

---

## Open items / caveats

- **Zmora and mitzpe_afek still running** — do not start matchers until CSV files exist and logs show "Detail phase complete."
- **2 new zmora _UNMAPPED_STAGES** must be added to `scrapers/bartech/api_scraper.py` before running zmora matcher.
- **מורדות כרמל** still blocked from home IP — needs office network.
- **Hadera stages** and **Kiryat Ata review** still waiting on colleague inputs.

---

## What to do next session

### Priority 1 — Add 2 missing zmora stages, then run matchers

```python
# Add to _UNMAPPED_STAGES in scrapers/bartech/api_scraper.py (# זמורה section):
'קבלת בקשה לרישיון עסק', 'אישור מהנדס לרישוי עסק',
```

Check logs to confirm scrapes are done:
```powershell
Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_zmora.txt' -Tail 10
Get-Content 'c:\R_PROJECTS\Project_update_scraper\outputs\scrape_log_mitzpe_afek.txt' -Tail 10
```

For each completed scrape:
1. Check `request_type` value counts at bottom of log (BUG-016 double-yod check)
2. Review any remaining `[NEW STATUS]` / `[NEW STAGE]` lines — add to scraper
3. Run matcher:
```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
$env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\run_harel_matcher.py
```

### Priority 2 — ישובי הברון DevTools inspection

1. Open `https://www.vaada-habaron.org.il/newengine/Pages/request2.aspx` in Chrome
2. Open DevTools → Network tab → filter XHR/Fetch
3. Enter a known gush number (e.g. גוש 10617 for זכרון יעקב area) and submit search
4. Identify the network request that returns permit rows (look for a POST returning JSON or HTML fragment)
5. Note the endpoint URL, request body shape, and response format
6. Share findings — then build scraper

### Priority 3 — מורדות כרמל (from office)

Run `scripts/run_mordot_carmel.py` from office network.

---

## State of key files

| File | State |
|---|---|
| `scrapers/bartech/api_scraper.py` | Updated — 4 STATUS_MAP + 4 STAGE_TO_STATUS + ~30 _UNMAPPED_STAGES from zmora/harel smoke tests |
| `outputs/harel_fresh.csv` | Complete — 1,145 permits (מבשרת ציון) |
| `outputs/zmora_fresh.csv` | In progress — scrape running |
| `outputs/mitzpe_afek_fresh.csv` | In progress — scrape running |
| `outputs/mordot_carmel_fresh.csv` | Does not exist — needs office IP |
| `outputs/kiryat_ata_report.xlsx` | 89 rows — awaiting colleague input |
| `outputs/hadera_report.xlsx` | 53 rows — awaiting colleague input on stage classification |
| `docs/NEXT_STEPS.md` | Updated — session I done |
