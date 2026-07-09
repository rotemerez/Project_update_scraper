# Next Steps — Project Update Scraper

**Last Updated:** 2026-07-09 (Session J)
**Current Phase:** V1 — manual-review report only (no automatic backoffice writes)  
**Scope:** Bat Yam via Complot; Holon + Kiryat Ata + Krayot + Hadera via Bartech; nationwide pipeline in progress

---

## Done

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

### 1. Classify Hadera unmapped stages + add to scraper

Artifact: https://claude.ai/code/artifact/c0dae2d0-319e-4123-b580-332c90957984
Use search + bulk-ignore for fast triage. Export JSON, then add entries to
`scrapers/bartech/api_scraper.py`:
- `STAGE_TO_STATUS` dict: strings that map to a real milestone
- `_UNMAPPED_STAGES` set: admin noise (silence the `[NEW STAGE]` log warnings)

### 1. Review Kiryat Ata report (59 `manual_review` rows)

Report at `outputs/kiryat_ata_report.xlsx` (89 rows total). Each `manual_review` row has a
`request_url` link. Pay attention to:
- `manual_review_event = 'ביטול היתר'` — project likely stalled
- `manual_review_event = 'החלטת ועדת ערר'` — appeal committee, outcome unknown
- `manual_review_event = 'הפקת פרסום תמ"38'` — תמ"א 38 publication event

### 2. Address request 20250178 (wrong-project match)

Sub-permit for project 20250142 matched to open project 11051-3 via shared parcel. Complot
list-page shows wrong date (2024-02-07 vs actual 13/07/2025). Accept as a known manual-review
case or add a filter for "dig/foundation only" sub-permits.

### 3. Run mitzpe_afek matcher + review reports

| Committee | Status | Next step |
|---|---|---|
| הראל (מבשרת ציון) | **DONE** — `outputs/harel_report.xlsx` (5 status_advanced, 32 untracked) | Review report |
| זמורה (מזכרת בתיה) | **DONE** — `outputs/zmora_report.xlsx` (7 status_advanced, 70 untracked) | Review report |
| מיצפה אפק (באר יעקב) | **CSV done** — `outputs/mitzpe_afek_fresh.csv` (3888 permits) | **Run matcher**: `scripts/run_mitzpe_afek_matcher.py` |
| מורדות כרמל | Not started — WAF blocks home IP | Run from office with `run_mordot_carmel.py` |

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\run_mitzpe_afek_matcher.py
```

### 4. ישובי הברון — find AJAX endpoint via browser DevTools, then build scraper

Portal: `www.vaada-habaron.org.il/newengine/Pages/request2.aspx` (SharePoint 2013 + Ext.NET).
Cities: זכרון יעקב (62 projects), אור עקיבא (45), בנימינה גבעת עדה (42), ג'סר א-זרקא.

**Investigation done (sessions I + J):** SP REST API blocked, SOAP requires auth, data is JS-rendered.
Page loads OK (200) with Ext.NET TreePanel configured in JS — static HTML has no AJAX URLs or
store proxy config. No "browse all" in plain HTML. Search modes: permit number, gush number, meeting number.

**Next step:** Open the site in Chrome, do a gush-number search in DevTools Network tab, find
the actual AJAX POST that fetches the permit grid data. If it's a clean endpoint → build a
`requests` scraper with gush enumeration per city. If not → Playwright.

Gush numbers for target cities can be read from `docs/all_projects_08072026.xlsx` (column `גוש`
on matched permits) or from govmap.

### 5. New cities

Current test cities are at report-review stage. Ready to add new Bartech or Complot cities when decided.

---

## Soon

### 4. Implement `scripts/fetch_projects.py` — Looker projects export

Full spec in `docs/FETCH_PROJECTS_IMPLEMENTATION.md`. Automates the manual Looker export
using the `looker-sdk` Python package. Fetches tile 2 ("Projects by each developer/architect/lawyer")
from dashboard 724 at `localize.eu.looker.com`, writes to `outputs/madlan_projects_fresh.xlsx`.
Credentials via `.env` file (`LOOKER_BASE_URL`, `LOOKER_CLIENT_ID`, `LOOKER_CLIENT_SECRET`).
After implementing: add `looker-sdk` + `python-dotenv` to `requirements.txt`; do not yet wire into
existing runner scripts.

### 5. Full rescrape of Bat Yam (quarterly)
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
- **Nation-wide projects export** — a single export covering all tracked municipalities replaces
  per-city Excel files. Either automated via backoffice API (see item 4) or a scheduled manual
  export before each report run.
- **Single consolidated report** — one Excel file across all committees, with a `committee`
  column, sorted by committee then by flag priority (`status_advanced` → `new_permit` →
  `untracked` → `manual_review`). The top-level runner calls each city's `matcher.run()`,
  concatenates the returned DataFrames, and writes the merged file.

**Blocking prerequisites before V2:**
1. All per-system scraper/matcher procedures finalised and stable (Complot + Bartech).
2. Nation-wide projects export confirmed (API or scheduled manual — still being investigated).

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
| `transform/matcher.py` | Matching + report; `_pick_best_candidate()` for multi-project parcels |
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
