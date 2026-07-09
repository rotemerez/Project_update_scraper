# Session Handoff — 2026-07-09 E

**Date:** 2026-07-09  
**Session:** J  
**Scope:** Bartech scraper hardened from full zmora + mitzpe_afek run logs; harel + zmora matchers run; mitzpe_afek matcher pending

---

## What was accomplished

### 1. Bartech scraper comprehensively updated — `scrapers/bartech/api_scraper.py`

Added the 2 planned zmora stages, then monitored both zmora and mitzpe_afek detail-phase logs live
and added every new stage/status as it appeared. Net additions vs session I:

**STATUS_MAP additions:**
- `'היתר/טופס 4/גמר'` → `'טופס 4'` (zmora: composite completion status)
- `'בקרת תכן תקינה'` → `'בקשה להיתר'` (mitzpe_afek list-page status)

**STAGE_TO_STATUS additions (~15 entries):**
- `'לאשר עם הקלות'` → `'היתר בתנאים'`
- `'לאשר בתנאי'` → `'היתר בתנאים'` (substring: catches `לאשר הבקשה בתנאי מילוי דרישות...`)
- `'לאשר בהסתיגות'` → `'היתר בתנאים'` (substring: catches `לאשר בהסתיגות המהנדס הו'`)
- `'מתן ת. גמר'` → `'טופס 4'` (abbreviated completion certificate)
- `'מסירת אישור תחילת עבודות'` → `'היתר'`
- `'צו התחלת עבודות'` → `'היתר'`
- `'הודעה על התחלת הבניה'` → `'היתר'`
- `'הודעה על התחלת בניה'` → `'היתר'` (variant without ה at start)
- `'חתימת היתר במערכת המקוונת'` → `'היתר'`
- `'לאשר חידוש היתר'` → `'היתר'`
- `'מתן טופס 2'` → `'היתר'`
- `'הגשת בקשה להיתר מקוונת במערכת רישוי זמין'` → `'בקשה להיתר'`

**`_UNMAPPED_STAGES` additions (~120 entries):**
Organized into sections `# זמורה`, `# זמורה — [category]`, and `# מיצפה אפק — [category]`.
Full list in the file. Highlights:
- Zmora: person-specific routing (`העברה לבודקת היתרים - אביה דוד`, etc.), appeal/legal stages,
  construction inspection stages (`ביקורת ראשונה באתר הבניה`, `בדיקת פיקוח - הכל תקין`, etc.),
  plan revision stages, regulatory letter stages (תקנה 36/27/46)
- Mitzpe_afek: section header labels (`== מסלול רישוי בניה ==`), appeal handling (`אישור ערר`,
  `סיום טיפול בערר`), financial stages (`חישוב שומה מכרעת`, `תשלום שומה מכרעת`), Tabu registration
  steps, inspector/field stages

### 2. Harel matcher — complete

```
outputs/harel_report.xlsx      — 37 rows (5 status_advanced, 32 untracked, 0 manual_review)
outputs/harel_matched_cache.json — 166 permits
```

### 3. Zmora matcher — complete

```
outputs/zmora_report.xlsx      — 77 rows (7 status_advanced, 70 untracked, 0 manual_review)
outputs/zmora_matched_cache.json — 264 permits
```

BUG-016 check passed: both `בנייה חדשה` (588) and `בניה חדשה` (66) present in zmora data.
Both already in `RELEVANT_TYPE_SUBSTRINGS`.

### 4. Mitzpe_afek scrape — complete, matcher NOT yet run

```
outputs/mitzpe_afek_fresh.csv  — 3888 permits (באר יעקב, vmm.co.il)
```

BUG-016 check passed: both `בנייה חדשה` (701) and `בניה חדשה` (292) present.

Matcher was NOT launched — session ended before running it.

### 5. ישובי הברון HTTP probe

Additional HTTP inspection of `www.vaada-habaron.org.il/newengine/Pages/request2.aspx`:
- Page loads OK (HTTP 200) with standard SharePoint WebForms structure
- Ext.NET TreePanel confirmed in JS (`Ext.net.TreePanel` at position 125295)
- No AJAX URLs, no store proxy config, no search form inputs in static HTML
- The search/data-load logic is entirely client-side JavaScript
- Static `requests` approach will never work — need browser DevTools to capture the XHR

---

## Open items

- **Mitzpe_afek matcher** — run `scripts/run_mitzpe_afek_matcher.py` (CSV ready)
- **מורדות כרמל** — still needs office IP
- **ישובי הברון DevTools** — browser inspection still required
- **Hadera stage classification** — still pending colleague input
- **Kiryat Ata report review** — 59 manual_review rows still pending

---

## What to do next session

### Priority 1 — Run mitzpe_afek matcher

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'
$env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\run_mitzpe_afek_matcher.py
```

Check for any `[WARN]` lines in output — none expected since scraper is now fully updated.
Review `outputs/mitzpe_afek_report.xlsx`.

### Priority 2 — ישובי הברון DevTools

1. Open `https://www.vaada-habaron.org.il/newengine/Pages/request2.aspx` in Chrome
2. Open DevTools → Network tab → filter XHR/Fetch
3. Enter a known gush number (e.g. גוש 10617 for זכרון יעקב) and submit search
4. Identify the POST that returns permit rows — look for JSON or HTML fragment response
5. Note: endpoint URL, request body shape (search params, ViewState?), response format
6. If replicable with `requests` → build scraper with gush enumeration; if not → Playwright

### Priority 3 — Review harel/zmora/mitzpe_afek reports

Open the 3 new Excel reports and triage with colleague:
- `outputs/harel_report.xlsx` (5 status_advanced, 32 untracked)
- `outputs/zmora_report.xlsx` (7 status_advanced, 70 untracked)
- `outputs/mitzpe_afek_report.xlsx` (TBD — matcher not run yet)

---

## State of key files

| File | State |
|---|---|
| `scrapers/bartech/api_scraper.py` | Fully updated — all zmora + mitzpe_afek stages added |
| `outputs/harel_fresh.csv` | Complete — 1,145 permits (מבשרת ציון) |
| `outputs/harel_report.xlsx` | Complete — 5 status_advanced, 32 untracked |
| `outputs/harel_matched_cache.json` | 166 permits |
| `outputs/zmora_fresh.csv` | Complete — 2383 permits (מזכרת בתיה) |
| `outputs/zmora_report.xlsx` | Complete — 7 status_advanced, 70 untracked |
| `outputs/zmora_matched_cache.json` | 264 permits |
| `outputs/mitzpe_afek_fresh.csv` | Complete — 3888 permits (באר יעקב) |
| `outputs/mitzpe_afek_report.xlsx` | Does not exist — run matcher |
| `outputs/mordot_carmel_fresh.csv` | Does not exist — needs office IP |
