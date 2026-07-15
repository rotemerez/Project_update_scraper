# Next Steps — Project Update Scraper

**Last Updated:** 2026-07-15 (Session R)
**Current Phase:** V1 — manual-review report only (no automatic backoffice writes)  
**Scope:** Bat Yam via Complot; Holon + Kiryat Ata + Krayot + Hadera via Bartech; nationwide pipeline in progress

---

## Done

### Session R — 2026-07-15

- **נתניה confirmed Bartech** via live recon (`g-recaptcha-response=x` dummy-token trick works
  here too) — `BartechPermitsAPI` needs no new code, just wiring (`config/committees.py` +
  `scripts/run_netanya.py`, not started).
- **תל אביב יפו fully reverse-engineered and a working scraper built** —
  `scrapers/tel_aviv/scraper.py` (browser-automation, drives the real search UI since reCAPTCHA
  Enterprise v3 is gateway-enforced and can't be bypassed with a placeholder), plus
  `scripts/run_tel_aviv.py` / `run_tel_aviv_matcher.py`. See "Immediate — Do First Next Session"
  #3 for full detail — race-condition and blocked-vs-miss bugs found and fixed via live browser
  observation with Rotem watching the non-headless window, adaptive rate-limiting from reCAPTCHA
  Enterprise confirmed empirically and mitigated (in-app "חיפוש חדש" navigation instead of full
  reloads, longer backoff). **Live validation deferred to next session** — code is written and
  syntax-checked but not yet proven stable over a longer real run.
- Docs added: `docs/tlv_permit_api_findings.md`, `docs/tlv_permit_api_findings2.md` (Tel Aviv API
  recon, via Claude Desktop browser instrumentation).

### Session Q — 2026-07-15

- **New immediate next step added**: build custom crawlers for the 4 active-but-excluded
  committees that run neither Complot nor Bartech (נתניה, תל אביב יפו, ירושלים, קצרין) — see
  "Immediate — Do First Next Session" #3. נתניה has a known URL to probe first; the other three
  need pure system-identification recon before any scraper design.

### Session P — 2026-07-13

- **V2 consolidated report runner built** (`scripts/run_all_committees.py`) — loops a declarative
  `COMMITTEE_CONFIGS` list, calls `transform.matcher.run()` per committee, merges results with a
  `committee` column, sorts by committee then flag priority, writes `outputs/consolidated_report.xlsx`.
  Skips (and logs) any committee whose `fresh.csv` doesn't exist yet rather than failing.
  **Verified working**: first run produced 293 rows across 6 committees (חדרה, הראל, זמורה,
  מיצפה אפק, ישובי הברון, מורדות כרמל) — matches each committee's individual matcher output exactly.
  Bat Yam / Holon / Kiryat Ata / Krayot / Ramat Gan are **not yet in `COMMITTEE_CONFIGS`** — no
  dedicated `run_*_matcher.py` script exists for them to copy exact params from (city_filter,
  permit_url_base); add once confirmed rather than guessing (see V2 item in "Later" section).
- **Nationwide projects export re-confirmed sufficient for V2** — `docs/all_projects_08072026.xlsx`
  (from Session L/M's `fetch_projects.py` + Looker MCP workflow) is already the shared input across
  all 6 configured committees. Manual export step, but functionally unblocks V2 prerequisite #2.
- **`city` column added to consolidated report** — `transform/matcher.py:_make_row()` now includes
  `proj['עיר']` when a project matched. `run_all_committees.py` backfills blanks for single-city
  committees (unambiguous); multi-city committees (מורדות כרמל, ישובי הברון) only get a real city on
  matched rows — untracked rows stay blank rather than parsing it from `full_address`, since scraped
  address text uses inconsistent city spelling/hyphenation (e.g. `זכרון-יעקב` vs `זכרון יעקב`) and can
  include neighboring cities outside the committee's own list (e.g. a מורדות כרמל untracked permit at
  `רכסים`, not one of the two configured cities). `committee`/`city`/`flag` moved to the front of the
  column order for filtering.

### Session O — 2026-07-13

- **מורדות כרמל scrape completed** — `outputs/mordot_carmel_fresh.csv`: 18,540 permits (started ~09:29,
  finished ~14:44). 138 unique event strings seen total across the full run (up from ~80 mid-scrape).
- **Complot triage artifact rebuilt** to match the Bartech/Hadera design: table layout with count
  column + sort toggle, per-row colored `<select>`, localStorage persistence, "Unset only" filter,
  search, bulk-ignore, Python export (only genuinely new classifications, not re-exporting existing
  presets). Added a "Hand off to next person" / "Continue from handoff" pair so multiple colleagues
  can classify sequentially across separate browsers/devices (localStorage doesn't sync between
  people, so state must be passed explicitly). Link: shared separately with colleagues.
- **מורדות כרמל matcher run** — `outputs/mordot_carmel_report.xlsx`: 10 status_advanced, 16 untracked,
  2 manual_review, 0 new_permit (108 projects in טירת הכרמל + נשר after city_filter; min_year=2015
  auto-computed; cache: `outputs/mordot_carmel_matched_cache.json`, 5040 permits).
- **Note**: matcher was run before the 2 known-unclassified events (`מסירת אישור הרצת מערכות`,
  `הפקת אישור הרצת מערכות`, ~26/23 occurrences) and ~110 other unmapped events were triaged — those
  events currently fall through to `_UNMAPPED_EVENTS`-equivalent (no status contribution) since
  they're absent from `EVENT_TO_STATUS`. If colleague triage later reclassifies any of them to a
  real status, **re-run the matcher** — some `untracked`/`manual_review` rows may reclassify as
  `status_advanced`.

### Session N — 2026-07-13

- **`min_year` support added to Complot scraper** (`scrapers/complot/api_scraper.py`) — new `min_year`
  parameter on `ComplotPermitsAPI.__init__`; new `_passes_min_year()` method; `scrape()` now filters
  the permit list before the detail-fetch phase. Previously, `min_year` was computed but silently
  discarded (no parameter existed), causing full 2011–present scrapes.
- **`scripts/run_mordot_carmel.py` updated** — now passes `min_year=min_year` to `ComplotPermitsAPI`.
- **מורדות כרמל scrape relaunched** from office (site_id=61, min_year=2015). List phase: 20,098 unique
  permits → 18,540 after year filter. Detail phase running as of end of session (~09:30 start).
- **Complot api_scraper.py updated** from mordot carmel scrape events:
  - 3 new `EVENT_TO_STATUS` entries: `חתימת היתר` → `'היתר'`; `הפקת היתר בניה` → `'היתר בתנאים'`;
    `שיבוץ לישיבת ועדה` → `'בקשה להיתר'`
  - 17 new `_UNMAPPED_EVENTS` entries (mordot carmel block): `בדיקה לשחרור ערבות`, `פתיחת ערבות`,
    `סיום ושחרור ערבות`, `דוח מפקח`, `דיווח מפקח בשלבי בניה`, `דו"ח פיקוח לפני וועדה`,
    `דו"ח ביקור לטופס 4`, `העברת נתונים לשמאי לעריכת שומה`, `החזרת התיק משמאי`,
    `השלמת דרישות בקרת תכן`, `אי השלמת דרישות בקרת תכן`, `המתנה לתיקון תכנית אצל העורך`,
    `הגשת הבקשה מחדש`, `העברת תכנית לפיקוח`, `שיבוץ לישיבת מליאה`, `הודעה על פרסום הקלה`
  - 2 new events seen mid-scrape, **not yet classified**: `מסירת אישור הרצת מערכות`,
    `הפקת אישור הרצת מערכות`
- **Complot triage artifact started** — first version built but wrong design (paste-log, button-row).
  Bartech artifact fetched and reviewed. Rebuild needed: table layout, per-row dropdown,
  localStorage persistence, bulk-ignore, pre-loaded events. **Not complete.**

### Session M — 2026-07-13

- **`scripts/fetch_projects.py` implemented and working** — Looker export pipeline complete.
  Looker API key access not available; workflow uses Claude Desktop Looker MCP to export CSV,
  then `fetch_projects.py --from-csv` to convert to Hebrew-column xlsx.
  Column rename map (29 Looker dot-notation → Hebrew) baked into the script.
  SDK mode (`init40()`) also implemented for when API keys are available.
  Output verified: 45,496 rows, 23,240 unique projects — matches old file city-by-city.
  Output: `outputs/madlan_projects_fresh.xlsx`
- **ישובי הברון matcher complete** — `outputs/yishuvei_habaron_report.xlsx`: 2 status_advanced, 49 untracked, 0 manual_review; cache: `outputs/yishuvei_habaron_matched_cache.json` (455 permits). 9737 permits scraped across זכרון יעקב, אור עקיבא, בנימינה גבעת עדה, ג'סר א-זרקא.
- **Complot api_scraper.py updated** — 7 new `EVENT_TO_STATUS` entries: `תעודת גמר`, `הפקת טופס 4 מותלה`, `הפקת טופס 4 להרצת מערכות`, `הפקת טופס נלווה לטופס 4` → `'טופס 4'`; `חתימת היתר בניה`, `הפקת אישור תחילת עבודות`, `אישור המפקח לתחילת עבודות` → `'היתר'`. ~80 new `_UNMAPPED_EVENTS` entries from full yishuvei_habaron scrape.

### Session L — 2026-07-12

- **`scripts/fetch_projects.py` implemented and working** — Looker export pipeline complete.
  Looker API key access not available; workflow uses Claude Desktop Looker MCP to export CSV,
  then `fetch_projects.py --from-csv` to convert to Hebrew-column xlsx.
  Column rename map (29 Looker dot-notation → Hebrew) baked into the script.
  SDK mode (`init40()`) also implemented for when API keys are available.
  Output verified: 45,496 rows, 23,240 unique projects — matches old file city-by-city.
  Output: `outputs/madlan_projects_fresh.xlsx`
- **ישובי הברון matcher complete** — `outputs/yishuvei_habaron_report.xlsx`: 2 status_advanced, 49 untracked, 0 manual_review; cache: `outputs/yishuvei_habaron_matched_cache.json` (455 permits). 9737 permits scraped across זכרון יעקב, אור עקיבא, בנימינה גבעת עדה, ג'סר א-זרקא.
- **Complot api_scraper.py updated** — 7 new `EVENT_TO_STATUS` entries: `תעודת גמר`, `הפקת טופס 4 מותלה`, `הפקת טופס 4 להרצת מערכות`, `הפקת טופס נלווה לטופס 4` → `'טופס 4'`; `חתימת היתר בניה`, `הפקת אישור תחילת עבודות`, `אישור המפקח לתחילת עבודות` → `'היתר'`. ~80 new `_UNMAPPED_EVENTS` entries from full yishuvei_habaron scrape.

### Session K — 2026-07-12

- **ישובי הברון scraper built** (`scripts/run_yishuvei_habaron.py`) — discovered site is Complot `site_id=14` at `handasi.complot.co.il` (not the SharePoint portal). Full scrape launched: 9,737 permits across 2011–2026.
- **Complot api_scraper.py updated** — 5 new `_UNMAPPED_EVENTS` entries for ישובי הברון: `פתיחת תיק`, `שליחת מכתבי החלטה`, `החלטה לדחות את הדיון`, `החלטה לא לאשר`, `ישיבת מליאת הועדה המקומית`; 1 new `EVENT_TO_STATUS` entry: `החלטה להמליץ למחוזית לאשר` → `'היתר בתנאים'`; also 4 additional unmapped events found mid-scrape: `בדיקת מפקח`, `תיק הועבר לבדיקת מפקח`, `אישור מחלקת השבחה להפקת היתר`, `התיק הועבר לדיון`.
- **ישובי הברון matcher script created** (`scripts/run_yishuvei_habaron_matcher.py`) — ready to run when scrape completes.
- **committees.py updated** — ישובי הברון moved from `_EXCLUDED` (no_scraper) to `_COMPLOT` with `site_id=14, exclude=False`.
- **Mitzpe_afek matcher complete** — `outputs/mitzpe_afek_report.xlsx`: 14 status_advanced, 33 untracked, 0 manual_review; cache: `outputs/mitzpe_afek_matched_cache.json` (601 permits).
- **Committee endpoint validator built** (`scripts/validate_committees.py`) — probes all active committees; confirmed **77/77 OK** (all Complot site_ids and Bartech base_urls reachable and returning data).

### Session J — 2026-07-09

- **Bartech scraper comprehensively updated** (`scrapers/bartech/api_scraper.py`) from zmora + mitzpe_afek full runs:
  - STATUS_MAP: `'היתר/טופס 4/גמר'` → `'טופס 4'`; `'בקרת תכן תקינה'` → `'בקשה להיתר'`
  - STAGE_TO_STATUS (~15 new entries): `'לאשר עם הקלות'` / `'לאשר בתנאי'` / `'לאשר בהסתיגות'` → `'היתר בתנאים'`; `'מסירת אישור תחילת עבודות'`, `'צו התחלת עבודות'`, `'הודעה על התחלת הבניה'` / `'בניה'`, `'חתימת היתר במערכת המקוונת'`, `'לאשר חידוש היתר'`, `'מתן טופס 2'`, `'הגשת בקשה להיתר מקוונת במערכת רישוי זמין'` → `'היתר'`/`'בקשה להיתר'`; `'מתן ת. גמר'` → `'טופס 4'`
  - `_UNMAPPED_STAGES`: ~120 new entries from zmora + mitzpe_afek full runs (person-specific routing, appeal/legal, inspection, financial, plan-revision, section-header labels)
- **Harel matcher complete** — `outputs/harel_report.xlsx`: 5 status_advanced, 32 untracked; cache: `outputs/harel_matched_cache.json` (166 permits)
- **Zmora matcher complete** — `outputs/zmora_report.xlsx`: 7 status_advanced, 70 untracked; cache: `outputs/zmora_matched_cache.json` (264 permits)
- **Mitzpe_afek scrape complete** — `outputs/mitzpe_afek_fresh.csv`: 3888 permits (באר יעקב); BUG-016: both `'בנייה חדשה'` (701) and `'בניה חדשה'` (292) present — both in `RELEVANT_TYPE_SUBSTRINGS`
- **ישובי הברון HTTP probe** — Ext.NET page loads (200 OK), but AJAX endpoint not discoverable from static HTML; still requires Chrome DevTools inspection

### Session I — 2026-07-09

- **Bartech scraper updated** (`scrapers/bartech/api_scraper.py`) from zmora + harel smoke tests:
  - 4 new STATUS_MAP entries → `'בקשה להיתר'`: `לאחר פרסום עמידה בתנאים מוקדמים`, `בדיקת מרחבית תקינה`, `תשלום אגרות והיטלים`; + `ביטול היתר` → `'היתר'`
  - 4 new STAGE_TO_STATUS entries: `היתר חתום ע"י מהנדס ויו"ר` → `'היתר'`, `תעודת גמר` → `'טופס 4'`, `הפקת אישור תחילת עבודות` → `'היתר'`, `מתן צו התחלת עבודה` → `'היתר'`
  - ~30 new `_UNMAPPED_STAGES` entries tagged `# זמורה / הראל`
- **3 Bartech scrapers launched** (all running in background as of ~14:03):
  - `run_mitzpe_afek.py` (vmm.co.il, באר יעקב, 5,627 pages type 51, min_year=2014) — in list phase
  - `run_zmora.py` (zmora.org.il, מזכרת בתיה, 3,499 pages type 51, min_year=2016) — in detail phase
  - `run_harel.py` (v-harel.co.il, מבשרת ציון, 1,654 pages type 51, min_year=2017) — **DONE** (1,145 permits → `outputs/harel_fresh.csv`)
- **`docs/FETCH_PROJECTS_IMPLEMENTATION.md`** added as Soon item 4 in NEXT_STEPS.md.
- **ישובי הברון portal investigated** (`www.vaada-habaron.org.il`):
  - SharePoint 2013 + Ext.NET — data is JS-rendered, `requests` alone cannot extract rows
  - SP REST API (`/_api`) blocked (connection reset); SOAP (`_vti_bin`) returns 401
  - Search modes: by permit number, gush number, or meeting number — no "browse all" in plain HTML
  - **Plan**: browser DevTools inspection to find the AJAX endpoint the Ext.NET grid calls;
    if clean, build a `requests` scraper with gush enumeration; else use Playwright

### Session H — 2026-07-09

- **NEXT_STEPS.md trimmed**: from 724 → ~190 lines; old Done history archived to `docs/session_handoffs/DONE_ARCHIVE.md`.
- **Global CLAUDE.md trimmed**: from 147 → ~90 lines; removed ILA-specific Python path and boilerplate sections.
- **`transform/matcher.py` extended**: added `city_filter: Optional[List[str]]` parameter — filters projects_df by `'עיר'` column after loading; also fixed address matching to use `proj_row.get('עיר', city_hebrew)` per-project instead of a single global city. Backward compatible.
- **8 runner scripts created** for the 4 new committees:
  - `scripts/run_mordot_carmel.py` + `run_mordot_carmel_matcher.py` (Complot site_id=61, cities: טירת הכרמל + נשר)
  - `scripts/run_mitzpe_afek.py` + `run_mitzpe_afek_matcher.py` (Bartech, vmm.co.il, city: באר יעקב)
  - `scripts/run_zmora.py` + `run_zmora_matcher.py` (Bartech, zmora.org.il, city: מזכרת בתיה)
  - `scripts/run_harel.py` + `run_harel_matcher.py` (Bartech, v-harel.co.il, city: מבשרת ציון)
- **Bartech scraper updated** (`scrapers/bartech/api_scraper.py`) from vmm.co.il smoke test:
  - 6 new STATUS_MAP entries → `'בקשה להיתר'`: `ישיבה`, `בקשה עומדת בתנאים מוקדמים`, `לאחר פרסום אי עמידה בתנאים מוקדמים`, `בדיקה מרחבית אינה תקינה`, `בדיקה מרחבית תקינה`, `בקרת תכן אינה תקינה`
  - 2 new STAGE_TO_STATUS entries → `'היתר'`: `אישור לתחילת עבודות`, `מתן אישור התחלת עבודה`
  - ~20 new `_UNMAPPED_STAGES` entries (מיצפה אפק routing/admin stages)
  - Verified: vmm.co.il smoke test shows zero `[NEW STATUS]` / `[NEW STAGE]` warnings after update
- **Complot (מורדות כרמל) blocked from home IP**: WAF blocks `handasi.complot.co.il` API from non-office IPs. All 3 Bartech portals (vmm.co.il, zmora.org.il, v-harel.co.il) are accessible from home.

### Session G — 2026-07-09

- **Committee registry expanded**: `config/committees.py` — 4 new active committees added, 9 no_scraper
  cities moved out of standalone entries.

  **New active committees:**
  | Committee | System | Cities | URL |
  |---|---|---|---|
  | מורדות כרמל | Complot (site_id=61) | טירת הכרמל, נשר | mordotcarmel.org/iturbakashot/ |
  | מיצפה אפק | Bartech | באר יעקב | vmm.co.il |
  | זמורה | Bartech | מזכרת בתיה | zmora.org.il |
  | הראל | Bartech | מבשרת ציון | v-harel.co.il |

  **ישובי הברון** (זכרון יעקב, אור עקיבא, בנימינה גבעת עדה, ג'סר א זרקא) — confirmed SharePoint
  portal (`vaada-habaron.org.il`), not Complot/Bartech. Added as single excluded entry with
  `exclude_reason='no_scraper'`. Needs custom scraper before activation.

  **Regional council portals confirmed NOT to cover target cities** (they serve kibbutzim/moshavim
  only): hof hacarmel, mateh yehuda, emek hefer — all check negative.

  **Updated counts:** Active 76 (Complot 47, Bartech 29), no_scraper 76, total entries 156.

### Session F — 2026-07-09

- **Diagnostic scripts deleted**: `scripts/diagnose_hadera.py`, `scripts/diagnose_hadera2.py`

- **Committee registry built**: `config/committees.py` — 160 entries covering all 162 project-file cities.
  - 46 active Complot committees (with `site_id`)
  - 26 active Bartech committees (with `base_url` + `permit_url_base`)
  - 1 excluded `url_unverified` (Netanya — `vaadnet.netanyagis.co.il` needs testing)
  - 3 excluded `proprietary` (תל אביב, ירושלים, קצרין)
  - 84 excluded `no_scraper` (cities in projects file with no known portal)
  - Krayot handled as one entry with `cities_hebrew: [קרית מוצקין, קרית ביאליק, קרית ים]`
  - `include_bakasha_meqdamit=True` for פתח תקווה and הרצליה (per CLAUDE.md exception)
  - Validated: all 162 project cities present, no duplicates, no missing site_id/base_url
  - Source: `local_committee_scrapers/unified_scraper/municipal_scraper/registry/dispatcher.py`

- **Open question for next session**: 72 active committees seems low. Several "no_scraper" cities
  with large project counts (מזכרת בתיה 95, באר יעקב 96, זכרון יעקב 62, מבשרת ציון 75,
  טירת הכרמל 78, נשר 30, אור עקיבא 45) may be served by regional-council portals in the
  dispatcher that were not linked. Needs investigation.

*Older sessions archived to `docs/session_handoffs/DONE_ARCHIVE.md`.*

---

## Immediate — Do First Next Session

### 1. Complot triage artifact — colleagues to finish classifying

Rebuilt to match the Bartech/Hadera design (table + dropdown + localStorage + search + bulk-ignore),
plus a handoff mechanism ("Hand off to next person" / "Continue from handoff" — copies/pastes a JSON
code so progress carries across colleagues' separate browsers, since localStorage doesn't sync
between people). Link shared with colleagues directly (not stored here since it's colleague-private).

**138 unique events total**, only 22 pre-classified. ~116 still need triage, including the 2 flagged
last session:
- `מסירת אישור הרצת מערכות` (23 occurrences) — likely `היתר`
- `הפקת אישור הרצת מערכות` (26 occurrences) — likely `היתר`

Once classification is done, get the final Python export from whoever finishes and paste the new
`EVENT_TO_STATUS` / `_UNMAPPED_EVENTS` / `_MANUAL_REVIEW_EVENTS` entries into
`scrapers/complot/api_scraper.py`, then **re-run the mordot carmel matcher** — the report below was
generated with only 22/138 events classified, so some `untracked`/`manual_review` rows may reclassify
to `status_advanced` once the rest are triaged.

### 3. Build custom crawlers for non-Complot/Bartech committees

4 active-but-excluded committees have a real portal but run neither Complot nor Bartech
(`config/committees.py`, `exclude_reason` in `proprietary`/`url_unverified`):

| Committee | Reason | URL / notes |
|---|---|---|
| נתניה | `url_unverified` — **RESOLVED, confirmed Bartech** | `https://vaadnet.netanyagis.co.il` — see below |
| תל אביב יפו | `proprietary` — **partial recon done (2026-07-15)** | system identified, API host not yet confirmed — see below |
| ירושלים | `proprietary` | system unknown — needs investigation before any scraper design |
| קצרין | `proprietary` | system unknown — needs investigation before any scraper design |

**נתניה confirmed Bartech (2026-07-15 recon)** — same signature as v-harel/zmora/vmm/Holon/Krayot:
- Search page `/SearchPermitApplication` → results `/SearchPermitApplicationResults/` → detail
  `/PermitApplicationDetails?Definement_Entity_Type=...&Entity_Type=P&Entity_Number=...` — exact
  match to `scrapers/bartech/api_scraper.py`'s `RESULTS_PATH`/`DETAIL_PATH` constants and referer path.
- Results table columns identical to existing Bartech parser: מספר בקשה, מספר תיק בניין, סטטוס,
  כתובת, מקרקעין (גוש/חלקה/מגרש), שם המבקש, תאור הבקשה.
- **reCAPTCHA v2 on results endpoint is not strictly enforced server-side** — a plain `requests` GET
  with `g-recaptcha-response=x` (the same dummy-token trick `_fetch_parcel_page()` already uses)
  returns real live data, e.g. permit `1/20260495`, גוש 8005 חלקה 1 מגרש 123, applicant
  "גינדי ישראל 2010 בע״מ", opened 14/07/2026. A bare GET with no `g-recaptcha-response` param at
  all is rejected with a captcha-error page ("אופס... חלה שגיאה בעת ביצוע הפניה").
- Debug snapshots: `outputs/debug_netanya_search.html` (search form),
  `outputs/debug_netanya_results.html` (captcha-error response, no token param),
  `outputs/debug_netanya_results2.html` (real data, dummy token param).
- **No new scraper code needed** — `BartechPermitsAPI` should work unchanged with
  `base_url='https://vaadnet.netanyagis.co.il'`. Remaining work (not started yet): move נתניה from
  `_EXCLUDED` to the active Bartech list in `config/committees.py`, build
  `scripts/run_netanya.py` following the `run_harel.py` pattern, confirm `min_year`/pagination
  against the live site, smoke-test before a full scrape.

For ירושלים / קצרין, the system isn't identified yet at all — first session on each should be
pure reconnaissance (view-source, network tab, robots.txt) with no scraper code written until
the actual data-access mechanism is confirmed. ישובי הברון (Session K) and נתניה both turned out
to be disguised Complot/Bartech instances despite looking custom at first glance — always check
for that signature in network requests before assuming a bespoke scraper is required.

**תל אביב יפו — two separate source sites, per Rotem (2026-07-15):**
- **`https://rishuybniya.tel-aviv.gov.il/resident-licensing/licensing-request-pages/request-search`**
  — covers the request lifecycle from טרום בקשה through היתר. This is the one probed this session
  (see below).
- **`https://handasa.tel-aviv.gov.il/pages/default.aspx`** — covers בדיקת אכלוס (occupancy check),
  a separate stage/system. **Deliberately deferred — not investigated yet, deal with later.**

**רישוי בנייה מקוון (`rishuybniya.tel-aviv.gov.il`) recon — FULL findings (2026-07-15):**

Static bundle analysis (this session, CLI-only) confirmed it's **not Complot or Bartech** — a
bespoke Angular (Universal SSR) SPA over a custom .NET REST API — but couldn't resolve the live
API host (injected at runtime, not hardcoded in delivered JS/HTML). Live browser instrumentation
via Claude Desktop (XHR interception) then confirmed everything else. Full writeup:
**`docs/tlv_permit_api_findings.md`**.

Key facts:
- **API host**: `https://apimtlvprd.tel-aviv.gov.il`, paths under `/prd/RishuiBniyaWeb/publicApi`
  (public search) vs `/prd/RishuiBniyaWeb/api` (Azure B2C-authenticated).
- **Search endpoint**: `POST .../publicApi/ResidentLicensing/Request/getRequest` — body is 7
  fixed fields (`submissionId`, `licenseId`, `streetCode`, `houseNumber`, `entrance`,
  `blockNumber`, `parcelNumber`); 0/null means "don't filter on this."
- **reCAPTCHA Enterprise v3 is gateway-enforced, not just client-side** — verified: missing token
  → `400 Missing assertion`; fake token → `400 Invalid assertion`. Required header:
  `X-Client-Assertion: <token>`, tokens expire ~2 min, one per request. Unlike Netanya's Bartech
  v2 (which accepted a dummy value), **this cannot be bypassed with a placeholder** — a working
  scraper would need a real browser context (e.g. Playwright driving `grecaptcha.enterprise.execute()`)
  to mint fresh tokens per request, which is a meaningfully heavier lift than any committee done so far.
- **Permit detail pages require full Azure B2C login** (MSAL/OAuth2 PKCE redirect) — not
  reachable by an unauthenticated scraper at all; direct API calls return `401`.
- **Street code lookup** (`GET .../publicApi/Address/SearchTlvStreets/{name}`) has no auth —
  usable to resolve `streetCode` for address-based search.
- **Backend confirmed working (Session 2 follow-up, 2026-07-15)** — the Session 1 "outage" was
  **not a real outage**: the Nativ backend throws its 500 whenever `entrance` is sent as `null`
  instead of `""`. Angular's own requests always send `""`, which is why the one real XHR
  captured in Session 1 happened to succeed. **Always send `entrance: ""`, never `null`.**
- **Confirmed real response schema** (`data` field, two sub-arrays):
  - `data.residentLicenseRequest` — building permit records: `requestId` (int, internal DB id),
    `dataNumber` (string, `"YY-NNNNN"`), `submissionStr` (string, secondary numeric ref),
    `licenseNumber` (string, display permit number `"YY-NNNN"`), `requestType`, `address`,
    `requestStatus`, `link` (always `"לפרטי הבקשה"`).
  - `data.requestDataList` — information/online-submission records: same `requestId`/`dataNumber`
    (empty)/`requestType`/`address`/`requestStatus`, no `licenseNumber`/`submissionStr`/`link`.
- **Permit number format confirmed**: `licenseId` in the request body = `20` + 2-digit year +
  4-digit zero-padded sequence (e.g. `20260624`), maps to display `licenseNumber` `"26-0624"`.
  **Sequence is mostly but not perfectly consecutive** — gaps exist (e.g. 625/626 missing while
  620–624 present) — a scraper must use a consecutive-miss threshold (e.g. 20+ in a row) to detect
  the true ceiling, not stop at the first gap. **Current ceiling as of 2026-07-15: `licenseId
  20260624` / `26-0624`** — ~620 permits issued in Tel Aviv in the first ~6.5 months of 2026
  (~95/month).
- Full writeup with the permit-number scan table: `docs/tlv_permit_api_findings2.md`.
- **Second Tel Aviv site (deferred, per Rotem 2026-07-15)**: `https://handasa.tel-aviv.gov.il/pages/default.aspx`
  covers בדיקת אכלוס (occupancy check) — separate stage, separate system, not investigated yet.

**Assessment**: fully scrapable — search endpoint, street lookup, response schema, and permit
numbering scheme are all confirmed working with real data (Session 2, 2026-07-15). The only
remaining structural obstacle is the mandatory per-request reCAPTCHA Enterprise token, which
means it needs a headless-browser component to mint tokens, not a plain `requests`-based scraper
like every other committee so far. Real step up in complexity/cost vs. Complot/Bartech, but no
longer blocked on unknowns — ready for scraper design once prioritized. No scraper code written yet.

**Complexity analysis + candidate solutions (2026-07-15):**

Two independent hard sub-problems, not one:

1. **Token minting is mandatory and server-verified** (not a client-side-only nicety like
   Netanya's v2). A real `grecaptcha.enterprise.execute()` call is required per search; tokens
   expire in ~2 min. Options considered:
   - **Drive the real page with a browser (recommended)** — Selenium / `undetected-chromedriver`
     (already project dependencies, already used for the legacy browser-based
     `scrapers/complot/scraper.py` before it was replaced by the faster Complot API approach).
     Load the search page, fill gush/helka or address fields, click search, let Angular's own JS
     mint the token and fire its own API call, then scrape the rendered results table from the DOM.
     Safer than the alternative below because Enterprise v3 scores behavioral signals tied to the
     actual page/session — a token minted and used in the same session looks like normal traffic.
     Cost: slow (full page load + JS render + randomized delay per query, ~5-15s each, same
     convention as the existing Complot browser scraper) — thousands of targeted lookups would
     take hours, comparable to prior browser-based scrapes in this project.
   - **Mint token in a browser, replay against the API directly** — faster (clean JSON vs DOM
     scraping) but riskier: separating token generation from the request that consumes it is a
     known pattern Enterprise scoring flags, likely causing intermittent silent rejections rather
     than a clean failure.
   - **Paid CAPTCHA-solving service (2captcha etc.)** — ruled out; not something to build,
     regardless of the underlying data being public.
2. **Query scope is unconfirmed** — search body always sends 7 fields with 0/null meaning "don't
   filter," but whether an all-zero body returns the full historical dataset (like Complot/Bartech)
   or requires a real filter is unknown (backend was down during testing). Blocks scraper design
   until retested:
   - **If full-list works** → same model as Complot/Bartech, just slower per-page from token overhead.
   - **If a real filter is required** → targeted model only: loop over gush/helka pairs already
     known from Madlan's nationwide projects export (`docs/all_projects_08072026.xlsx`), one query
     per Tel Aviv project — mirrors the `scrape_parcels` pattern already built for Bartech
     (zmora/mitzpe_afek runs). Lower volume, which also caps token/browser-session overhead.

**Worth flagging**: reCAPTCHA Enterprise is a deliberate control the site owner put on this
endpoint specifically — materially bigger step than any committee scraped so far (all either had
no such protection or a soft client-side check). The browser-driving approach is the least
invasive path (mimics a human using their own form) but is still a real build/maintenance cost
(DOM scraping is more fragile to UI changes than API scraping) — worth confirming it's worth
pursuing before investing the time. No code written.

**Decision (Rotem, 2026-07-15): go with Option A** — Selenium/`undetected-chromedriver` driving
the real search UI (not direct API calls with a replayed token).

**BUILD COMPLETE (2026-07-15) — pending live validation, deferred to next session ("tomorrow"):**

- **`scrapers/tel_aviv/scraper.py`** — `TelAvivPermitsBrowserScraper`. Three public methods:
  - `scrape_parcels(pairs)` — targeted גוש/חלקה lookup, same `scrape_parcels`-style shape as
    Bartech's.
  - `scrape_license_ids(ids)` — explicit-list lookup by `licenseId`, used for gap-fill.
  - `scan_license_range(start, consecutive_miss_limit)` — sequential upward scan with a
    consecutive-genuine-miss stopping threshold.
  - Real bugs found and fixed **live**, via direct browser observation (Rotem watching the
    non-headless window) and empirical testing — do not re-introduce these:
    - **Must run non-headless.** Headless got a syntactically-valid-but-server-rejected token
      (`400 Invalid assertion`); the identical query in a real window succeeded (`200`).
      Confirmed by direct comparison.
    - **Form must be reloaded/re-navigated before every query**, not reused — Angular swaps the
      form out for a results view after a search, so previously-found `formcontrolname` elements
      go stale on the second query onward.
    - **Race condition**: the field being present in the DOM does not mean Angular's reactive
      `FormGroup` has finished wiring/default-populating it — filling too early gets silently
      overwritten back to `"0"` (caught by Rotem watching the live browser). Fixed with an
      explicit settle delay + a fill-then-verify-then-JS-fallback in `_fill_field()`.
    - **Blocked ≠ not-found**: a `400`/gateway rejection was initially mis-counted as a genuine
      "no permit here," which would have silently truncated scans at a false ceiling. Fixed:
      `_parse_response()` now returns a 3-way outcome (`'ok'` / `'blocked'` / `'error'`), and
      `_query()` retries blocked/error outcomes with scaling backoff (30-75s × attempt, up to 3
      tries) rather than counting them as misses.
    - **Adaptive rate-limiting confirmed empirically**: after a couple of successful queries in a
      tight loop, the gateway started rejecting every subsequent request with `400 Invalid
      assertion` even in a real browser — reCAPTCHA Enterprise degrades a session's score based on
      request frequency/pattern, not just headless-ness. Mitigated by (a) using the results page's
      own **"חיפוש חדש" button** for in-app navigation between queries instead of a full
      `driver.get()` reload every time (a real user doing several searches doesn't reload the
      whole SPA bundle each time — confirmed the button exists via a live screenshot from Rotem),
      and (b) longer inter-query delays (10-25s normal, scaling backoff on rejection). Full
      resilience under sustained real-world load is **not yet proven** — this needs the deferred
      live validation pass.
- **`scripts/run_tel_aviv.py`** — 3-phase orchestration:
  1. Parcel mode over Tel Aviv's known gush/helka pairs (excludes `אוכלס`/occupied projects —
     cuts the pair count from 5,640 to **3,893**, since fully-complete projects have no reason to
     show new permit activity). **`PARCEL_LIMIT = 150`** caps the first real run to a validation
     batch, per Rotem — raise/remove once proven stable at scale.
  2. Gap-fill: scans every `licenseId` between the min/max actually found in phase 1 that phase 1
     didn't already surface (catches permits for projects not yet in Madlan, without a blind
     from-year-0001 scan).
  3. Sequential continue: scans upward from (max found) + 1 to catch new filings, same
     consecutive-miss-threshold logic.
  - Rotem's explicit design call: **do not** derive the scan seed from Madlan's permit-request
    *dates* (the nationwide export has no permit-number field at all — confirmed) — derive
    everything from the scraper's own actual findings instead.
- **`scripts/run_tel_aviv_matcher.py`** — thin `matcher.run()` call, same shape as every other
  committee's matcher runner. No `permit_url_base` (detail pages need Azure B2C login).
- **Known schema gap, by design (not a bug)**: `request_date`, `request_category`, `requestor`,
  `bakasha_description`, `shimush_ikari`, `unit_count` are left blank — not available from the
  public search response, only from the login-gated detail page. Per CLAUDE.md's data-integrity
  rule, blank rather than fabricated.
- **Status vocabulary (`STATUS_MAP`) ships empty** — only 2 real values seen so far
  (`בדיקה מרחבית מחלקת רישוי`, `פניה נדחתה`) plus several more surfaced mid-testing
  (`סגירת בקשה-נמסר היתר`, `סגירת בקשה-פג תקף החלטה`, `סגירת בקשה-נפתחה בטעות`,
  `סיום רישוי-במערכת קודמת`) — not yet enough real data to classify confidently. New values log
  via `[NEW STATUS]`; classify once a real batch run has completed (same iterative pattern as
  Bartech's `STATUS_MAP`).
- **Next session**: run `scripts/run_tel_aviv.py` for real (150-pair batch), confirm the fixes
  hold up over a longer session, then decide whether to raise `PARCEL_LIMIT` toward the full 3,893.

### 4. Review pending reports (with colleague)

| Committee | Report | Key figures |
|---|---|---|
| מורדות כרמל | `outputs/mordot_carmel_report.xlsx` | 10 status_advanced, 16 untracked, 2 manual_review — **run with only 22/138 events classified, re-run after triage completes** |
| קרית אתא | `outputs/kiryat_ata_report.xlsx` | 14 status_advanced, 41 untracked, 59 manual_review |
| הראל | `outputs/harel_report.xlsx` | 5 status_advanced, 32 untracked |
| זמורה | `outputs/zmora_report.xlsx` | 7 status_advanced, 70 untracked |
| מיצפה אפק | `outputs/mitzpe_afek_report.xlsx` | 14 status_advanced, 33 untracked |
| ישובי הברון | `outputs/yishuvei_habaron_report.xlsx` | 2 status_advanced, 49 untracked |

Kiryat Ata `manual_review` events to watch: `ביטול היתר`, `החלטת ועדת ערר`, `הפקת פרסום תמ"38`.

### 5. Classify Hadera unmapped stages + add to scraper

Artifact: https://claude.ai/code/artifact/c0dae2d0-319e-4123-b580-332c90957984
Use search + bulk-ignore for fast triage. Export JSON, then add entries to
`scrapers/bartech/api_scraper.py`:
- `STAGE_TO_STATUS` dict: strings that map to a real milestone
- `_UNMAPPED_STAGES` set: admin noise

---

## Soon

### 6. Full rescrape of Bat Yam (quarterly)
Current `bat_yam_fresh.csv` is from 2026-06-28 (scrape D). The `detail_block_lot` fix
and permit number regex fix will only take effect in the next full scrape.
Run quarterly to refresh the identity cache and pick up old permit ↔ new project linkages.

---

## Later

### 6. Resolve `שימור` substring noise
`שימור` is broad — it could match minor facade-preservation permits.  
After seeing real Complot data, tighten to a more specific substring if noise appears.

### 7. Complot event mapping — finalise
All distinct events from the 2011–2026 scrape have been catalogued (see session F handoff).
Three new ones were added. Remaining unmapped events are intentionally left blank (admin/processing).
No further action needed unless new event types surface in future scrapes.

### 8. V2 — regular all-committee scrape + consolidated report

**Architecture decisions (2026-07-08):**
- **Scraping runs from the office** — fixed IP avoids the Complot blocks that hit cloud runners.
  Use Windows Task Scheduler or a local cron job to trigger each city's runner script.
- **Incremental mode for regular runs** — refresh all cached-matched permits + scan the last
  N days of new submissions per city (the matched-cache + `scrape_targeted` pattern already
  exists for Bat Yam). Full scrapes drop to quarterly per city.
- **Nation-wide projects export** — ✅ done (Session P) — `docs/all_projects_08072026.xlsx` via
  `fetch_projects.py` + Looker MCP is already the shared input. Still a manual export step, not
  API-automated (see item 9), but functionally satisfies this prerequisite.
- **Single consolidated report** — ✅ built (Session P) — `scripts/run_all_committees.py`. One
  Excel file across configured committees, `committee` column, sorted by committee then flag
  priority. Currently covers 6 of ~11 scraped committees (see Session P note); add
  Bat Yam/Holon/Kiryat Ata/Krayot/Ramat Gan once their exact matcher params are confirmed.

**Remaining blocking prerequisite before full V2:**
1. All per-system scraper/matcher procedures finalised and stable (Complot + Bartech) — ~66 of
   77 active committees in `config/committees.py` still have no scrape at all. This is the real
   bottleneck; the runner/export infra is no longer blocking.

### 9. V2 — automatic backoffice writes
After the manual-review cycle is validated:
- Build `backoffice/client.py` (API wrapper)
- Build `transform/mapper.py` (scraped fields → backoffice payload)
- Tie into matcher output for auto-update of `status_advanced` projects
- `new_permit` and `untracked` still require human sign-off before creation

---

## Key File Paths

| Path | Role |
|---|---|
| `scrapers/complot/api_scraper.py` | Complot API scraper — working; outputs `migrash` + `applicant_name` |
| `scrapers/bartech/api_scraper.py` | Bartech API scraper — two-phase (list + detail pages); `min_year` param |
| `scripts/run_bat_yam.py` | Full scrape runner (~80 min) |
| `scripts/run_bat_yam_incremental.py` | Incremental runner — Phase A + Phase B (~10 min) |
| `scripts/run_ramat_gan.py` | Ramat Gan (Complot, site_id=3) — needs office IP; re-scrape required |
| `scripts/run_kiryat_ata.py` | Kiryat Ata (Complot, site_id=32) — needs office IP |
| `scripts/run_holon.py` | Holon (Bartech) full scrape runner — min_year auto-computed |
| `scripts/run_krayot.py` | Krayot (Bartech, vkrayot.co.il) — min_year auto-computed from projects file |
| `transform/matcher.py` | Matching + report; `_pick_best_candidate()` for multi-project parcels; `run()` returns `report_df` |
| `scripts/run_all_committees.py` | V2 consolidated runner — loops `COMMITTEE_CONFIGS`, merges into `outputs/consolidated_report.xlsx` |
| `docs/all_projects_08072026.xlsx` | Nationwide Madlan projects export (Looker MCP) — shared input across all configured committees |
| `outputs/consolidated_report.xlsx` | Merged multi-committee report — 293 rows / 6 committees as of Session P |
| `transform/gush_helka.py` | Gush-helka parsing and set-intersection |
| `transform/address_match.py` | Address normalization and range matching |
| `docs/bat_yam.xlsx` | Madlan projects export for Bat Yam (601 rows) |
| `docs/holon_28062026.xlsx` | Madlan projects export for Holon (500 rows) |
| `outputs/bat_yam_fresh.csv` | Latest full Bat Yam scrape |
| `outputs/ramat_gan_fresh.csv` | Stale — scraped while IP-blocked, detail fields empty; re-scrape from office |
| `outputs/holon_fresh.csv` | Complete — 21,039 permits (2026-07-02) |
| `outputs/kiryat_ata_fresh.csv` | Complete — 3,318 permits (2026-07-02); some `היתר` statuses missing (old code) |
| `outputs/kiryat_ata_report.xlsx` | Matcher output — 14 status_advanced, 41 untracked |
| `outputs/holon_report.xlsx` | First run: 194 status_advanced, 3 untracked (pre-הסתיים fix); re-run in progress |
| `outputs/holon_matched_cache.json` | 2,487 matched permits (first run) |
| `outputs/krayot_fresh.csv` | Detail phase running ~14:00 2026-07-02 |
| `docs/krayot_projects_30062026.xlsx` | Madlan projects export for Krayot (534 projects) |
| `outputs/bat_yam_matched_cache.json` | Permit numbers matched to BO projects — Phase A input |
| `outputs/ramat_gan_matched_cache.json` | Generated by first matcher run (not yet run) |
| `outputs/bat_yam_report.xlsx` | Latest Bat Yam report (5 rows) |
| `docs/Ramat_Gan_Projects_30062026.xlsx` | Madlan projects export for Ramat Gan |
| `docs/session_handoffs/` | Per-session handoff notes |
