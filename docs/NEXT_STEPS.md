# Next Steps — Project Update Scraper

**Last Updated:** 2026-07-22 (Session W)
**Current Phase:** V1 — manual-review report only (no automatic backoffice writes)  
**Scope:** Bat Yam via Complot; Holon + Kiryat Ata + Krayot + Hadera + Harel + Zmora + Mitzpe Afek
via Bartech (all 6 rescraped-and-date-corrected as of Session W); ירושלים custom scraper built +
full run + matcher (Session T, 61-row report as of Session V) + sweep enrichment (Session V,
18,871/20,693 parcels resolved); אשקלון via Complot built + run + matcher (Session U, 53-row
report as of Session W, permit_url_base confirmed); מורדות כרמל Complot triage confirmed final
(Session W); Tel Aviv GIS-layer approach built + run + matcher (Session U, 107-row report);
nationwide pipeline in progress

---

## Done

### Session W — 2026-07-22

Colleague's Ashkelon manual review drove a deep investigation: found and fixed BUG-023 (public-use
plural gap + 2 missing Ashkelon high-rise construction types), BUG-024 (`הרצת מערכות` wrongly
mapped to real `טופס 4`), and a related unit-minimum spelling gap; added 7 more construction types
after colleague confirmation; ran a targeted BUG-020 date-correction pass across all 6 Bartech
cities (7,695 dates corrected); ran a targeted BUG-024 re-check on Ashkelon + Mordot Carmel (5
Ashkelon permits corrected, 4 downgraded from false-positive `טופס 4`); closed the long-open
Complot triage backlog as final (colleague's export fully matches the current code already — no
new classifications, 2026-07-22). Full detail in
`docs/session_handoffs/SESSION_HANDOFF_2026_07_22_A.md` and `docs/BUG_REFERENCE.md` (BUG-023,
BUG-024).

### Session V — 2026-07-20

- **Jerusalem sweep parcel-resolution gap closed — the "manual parcel lookup" blocker from Session
  U is gone.** `sweep_by_tik_number()`'s hits had no gush/helka/address because `fetchTikRushiData`'s
  schema doesn't carry them. Grepped `outputs/debug_jerusalem_main.js` for proc IDs not yet mapped
  in `scrapers/jerusalem/api_scraper.py`'s docstring and found two live, working ones:
  `getGushimContentData` (242700456, `{SystemId, TikNum}` → gush/miHelka/adHelka) and
  `getKtovetContentData` (242700455, `{systemId, tikNum}` → street/house/neighborhood). Both
  confirmed live against real תיק numbers. Added `resolve_parcel(tik_num)` to
  `JerusalemPermitsAPI`, wired into `sweep_by_tik_number()` for future sweeps (marks
  `scrape_status='success'` when either resolves, instead of always `'partial'`).
  - **Enriched the existing 20,693-row `outputs/jerusalem_sweep.csv`** via new
    `scripts/enrich_jerusalem_sweep.py` (resumable, checkpoints every 200 rows) run in the
    background: **18,871/20,693 rows (91.2%) now have block_lot/full_address**. Remaining 1,822
    are genuinely not indexed in Jerusalem's own gushim/ktovet system (same pattern seen in a live
    spot-check sample, ~25% miss rate there too).
    - Hit a ~2.5hr DNS-resolution outage mid-run (`jerbasicserviceapi.jerusalem.muni.il` failed to
      resolve, not a WAF/rate-limit block) — the existing `_with_retry()`/blocked-vs-error handling
      caught it correctly: one תיק (`2019/0350.00`) logged `[GIVE UP]` as inconclusive rather than a
      fabricated miss, process stayed alive, resumed normal ~80 rows/min pace once the network
      recovered. That one תיק was manually re-resolved after the run finished (`30173-116;30173-33`,
      `רשב"ג 20`) — now fully resolved too.
  - Sweep CSV is now ready to feed into the matcher (previously blocked entirely on this gap).

- **אשקלון `permit_url_base` confirmed** (Rotem provided a real permit URL:
  `https://ashkelon.complot.co.il/newengine/Pages/request2.aspx#request/20160086` — same
  `request_number` format as `outputs/ashkelon_fresh.csv`). Wired into `config/committees.py`,
  `scripts/run_ashkelon_matcher.py`, and added a new entry to `run_all_committees.py`'s
  `COMMITTEE_CONFIGS` (previously excluded from the consolidated report pending this). Matcher
  re-run, `request_url` column confirmed populated correctly.

- **`RELEVANT_TYPE_SUBSTRINGS` gained two new tracked construction types**, both confirmed against
  real sample permits before adding (same due-diligence pattern as the double-yod checklist in
  CLAUDE.md):
  - **`ביטול היתר ובנייה מחדש`** (permit cancellation + rebuild) — 6 occurrences in Ashkelon,
    confirmed by Rotem as effectively new construction. Ashkelon matcher re-run: 42→43 report rows.
  - **`תוספת יח"ד באמצעות תוספת בניה`** (unit addition via building extension) — found while doing
    the Session T double-yod carryover check (no actual double-yod bug found; the substring
    matching handles the comma-joined `sug_bakasha` format fine). 486 occurrences across Jerusalem's
    two datasets (192 in `jerusalem_fresh.csv`, 294 in `jerusalem_sweep.csv`), 465 previously
    **entirely invisible** to the matcher (not just filtered — never even recognized as relevant).
    Pulled real `mahutBakasha` descriptions via `getTeurHabakashaContentData` (242700447) for 5
    sample permits before adding — one was a genuine 19-unit addition. Jerusalem matcher re-run:
    all 5 samples now appear in `matched_cache` (4,270 permits, up from 3,611); full report now 61
    rows (52 status_advanced, 3 untracked, 6 new_permit) — not a clean before/after of just this
    change since `docs/all_projects.xlsx` was also refreshed multiple times since Session T.
  - **Explicitly decided against** extending `_is_below_unit_minimum()` to also check
    `shimush_ikari` for `צמודי קרקע` (currently only checks `request_type`) — Rotem's call: land-use
    tag alone doesn't tell us unit count, not enough information to act on.

- **Session T carryover item 2** (Jerusalem's "no request-category field" assumption) — explicitly
  reviewed and left open per Rotem's call; still needs a manual spot-check of report rows against
  the assumption in `scripts/run_jerusalem_matcher.py`'s docstring.

### Session U — 2026-07-20

- **Tel Aviv GIS-layer scraper built, full run, matcher done** — new approach discovered by Rotem:
  Tel Aviv's `gisn.tel-aviv.gov.il` runs a genuine public ArcGIS Feature Layer (layer 772, "בקשות
  והיתרי בניה") with no auth/reCAPTCHA, directly queryable via the standard `/query` REST API
  (paginated, 10,538 total rows). This is a full replacement candidate for the paused
  Selenium/reCAPTCHA scraper (`scrapers/tel_aviv/scraper.py`, still on hold).
  - `scrapers/tel_aviv/gis_api_scraper.py` — paginates the whole layer, merges multi-building
    request rows by `request_num`, derives `permit_status` from date fields directly
    (`occupation`→טופס 4, `permission_date`→היתר, `open_request`→בקשה להיתר — no second API call
    needed, unlike Jerusalem's פיקוח lookup).
  - **Gush/helka resolved via a second discovery**: Rotem found the building layer (513) links to
    a תיק בניין archive at `archive-binyan.tel-aviv.gov.il` → real host `handasa.tel-aviv.gov.il`.
    Claude Desktop browser investigation found the underlying data call: a plain, anonymous WCF
    REST endpoint (`_vti_bin/TlvSP2013PublicSite/TlvList.svc/GetListItemsByFieldFilterStringWithQuery`)
    keyed by תיק בניין number, returning `EngFolderBlocksParcels` (`"{gush}_{helka},..."`). Verified
    live, no auth needed, clean `[]` on unknown IDs. Only resolves ~26% of permits (2,281/8,898) —
    the archive doesn't index every building — so `transform/address_match.py` was fixed to handle
    comma-joined multi-address strings (each segment matched independently) as the fallback path
    for the rest.
  - **Full run**: 10,538 raw rows → 8,898 merged permits → `outputs/tel_aviv_gis_fresh.csv`.
    Status: 4,994 היתר, 2,830 בקשה להיתר, 1,074 טופס 4.
  - **Matcher run**: `outputs/tel_aviv_gis_report.xlsx` — 107 rows (24 status_advanced, 83 untracked,
    0 new_permit/manual_review); cache 2,959 permits (`outputs/tel_aviv_gis_matched_cache.json`).
  - **Not yet done**: spot-check a sample of status_advanced/untracked rows against reality
    (standard due-diligence for a new scraper), especially address-matched (non-gush/helka) rows
    since they carry most of the matching load here.

- **Jerusalem sweep: blocked-vs-not-found bug found and fixed, sweep re-run**.
  - Attempted the sweep (see Session T carryover) — hit a real IP/rate block on
    `jerbasicserviceapi.jerusalem.muni.il` (492 consecutive 403s) after an accidental duplicate
    process (a stale Start-Process launch a flawed liveness check had wrongly reported as exited)
    doubled request volume. Killed both processes.
  - **Root cause was a real bug, now fixed**: `_fetch_rishui_bniya()`, `_fetch_pikuah_stages()`,
    `_fetch_tik_rushi()` in `scrapers/jerusalem/api_scraper.py` used to treat any request exception
    (including a 403 block) as an ordinary empty result, feeding straight into `sweep_by_tik_number`'s
    miss-streak counter — silently corrupting results with fabricated "nothing here" data. Fixed:
    all three now return a 3-way `('ok'|'blocked'|'error', data)` outcome; a new `_with_retry()`
    helper retries blocked/error with backoff and logs `[GIVE UP]` + an inconclusive-count summary
    if still unresolved, rather than counting it as a miss. Same pattern already used in
    `scrapers/tel_aviv/scraper.py`. Smoke-tested on both `scrape_parcels` and `sweep_by_tik_number`
    paths — no regressions, real data confirmed.
  - **Checked whether Jerusalem has a Tel-Aviv-style public ArcGIS layer** (the Sunday task from
    Session T) — **negative result**. No `arcgis`/`esri`/`MapServer` references anywhere in the
    ~1.8MB JS bundle or either backend host; Jerusalem's `jergisinfohub`/`jerbasicserviceapi` is a
    genuinely custom system, unlike Tel Aviv's real Esri ArcGIS Server. Ruled out, not worth
    revisiting without a new lead.
  - **Sweep re-launched and completed** (single process, confirmed no stray processes first) — all
    years 2005-2026 swept cleanly, no further 403s. **20,693 תיק rows found** →
    `outputs/jerusalem_sweep.csv`. Per-year counts: 2005:1193, 2006:1122, 2007:980, 2008:911,
    2009:996, 2010:1372, 2011:1383, 2012:1155, 2013:1333, 2014:1215, 2015:1043, 2016:1574,
    2017:1164, 2018:902, 2019:608, 2020:754, 2021:496, 2022:533, 2023:552, 2024:560, 2025:520,
    2026:327 (partial year). Results are necessarily partial (no gush/helka/address from
    `fetchTikRushiData`'s schema) — **manual parcel lookup before matching is still not built**,
    next session's task.

- **אשקלון (Ashkelon) added — Complot, site_id=95**. Was already in `config/committees.py`
  (active, never run). Smoke-tested first (6,848 unique permits found in list phase alone, clean),
  then full run: `scripts/run_ashkelon.py` + `run_ashkelon_matcher.py` (same pattern as
  `run_mordot_carmel.py`). **6,612 permits** → `outputs/ashkelon_fresh.csv` (min_year=2011
  auto-computed). Double-yod check passed — all construction-type strings use single-yod
  spelling consistently, already covered by `RELEVANT_TYPE_SUBSTRINGS`. **Matcher**:
  `outputs/ashkelon_report.xlsx` — 40 rows (16 status_advanced, 24 untracked, 0
  new_permit/manual_review); cache 525 permits (`outputs/ashkelon_matched_cache.json`). No
  `permit_url_base` set yet (not confirmed for this committee).

- **New `madlan_projects_fresh.csv` dropped by Rotem — converted, but a real scope discrepancy
  found, NOT yet resolved**. Ran `scripts/fetch_projects.py --from-csv` → `outputs/madlan_projects_fresh.xlsx`
  (45,484 rows, 23,207 unique project IDs — raw Looker "per stakeholder" grain, ~2 rows/project).
  Compared against the currently-used `docs/all_projects_08072026.xlsx` (24,886 rows, 23,233 unique
  projects, ~1 row/project — some dedup step produced this from the same raw shape, not present in
  `fetch_projects.py`):
  - Project-ID overlap is solid (23,152 shared, 81 dropped/55 added — normal week-to-week churn).
  - **42 cities are completely missing from the new export** that are present in the old file —
    not thin data, entirely absent. Pattern: mostly Judea/Samaria settlements (אורנית, אפרת, בית אל,
    כפר קאסם, קרני שומרון, עמנואל, אלפי מנשה, צופים, ...) plus several Druze/Arab towns (דאלית
    אל-כרמל, עראבה, סח'נין, כפר ברא, ...) and **קצרין** — one of the four committees already
    flagged for a custom scraper (see below); if this narrower scope is real, that scraper would
    have nothing to match against.
  - **Not resolved**: is this an intentional scope change on the Looker dashboard, a permissions
    difference on this particular export, or an export glitch? `docs/all_projects_08072026.xlsx`
    was deliberately left untouched — do NOT swap it for the new file until this is confirmed with
    whoever owns the Looker dashboard.
  - **Automation built**: weekly refresh now auto-detects + auto-converts + auto-promotes.
    Real constraint discovered first: the CSV export itself depends on the Claude Desktop Looker
    MCP connector, which requires interactive auth and **cannot run in a headless/scheduled
    context** (confirmed via this session's own MCP-server system context) — so full end-to-end
    automation (no human ever touching this) would need real Looker API credentials
    (`fetch_projects.py`'s already-built `from_sdk()` path). Absent that, built
    `scripts/check_projects_refresh.py`: detects when `outputs/madlan_projects_fresh.csv` is newer
    than the last-processed xlsx, converts it, runs the scope+grain sanity check (city coverage,
    ID overlap, rows-per-project ratio), and **auto-promotes** over the production file only when
    all checks pass — otherwise logs `[ALERT]` and leaves the production file untouched. Registered
    as a daily Windows Scheduled Task (`MadlanProjectsRefreshCheck`, 8:00 AM,
    `outputs/projects_refresh_check_log.txt`).
  - **Root cause of the 42-missing-cities/doubled-row-count issues found and fixed (by Claude
    Desktop, same day)**: a Looker LEFT JOIN was producing one spurious null-partner row per
    project alongside real stakeholder rows, roughly doubling row count (45,639 rows for 23,305
    projects instead of ~25,000) — separate from, and probably unrelated to, the one-off missing-
    cities incident (which didn't recur on the next pull). Fixed by dropping null-partner rows for
    projects that have at least one real stakeholder, while keeping them for the 1,086 projects
    with no stakeholder at all. Verified: new export now 24,992 rows / 23,305 projects, matching
    the production file's shape (24,886 / 23,233) almost exactly.
  - **Production file renamed to remove the hardcoded date**: `docs/all_projects_08072026.xlsx` →
    `docs/all_projects.xlsx` (git-tracked rename). Every script that referenced the old dated
    filename (19 files: `config/committees.py`, every `run_*`/`run_*_matcher.py`) now points at the
    stable name — this was the actual fix for "why do we need to touch 19 files every week": the
    filename never needs to change again, only the file's contents (via the scheduled auto-promote
    above). Historical mentions of the old filename in past session entries below and in
    `docs/session_handoffs/` were deliberately left as-is (accurate record of what was true then).

### Session T — 2026-07-16

- **ירושלים custom scraper built, full-run, and matcher wired** — first working scraper for a
  previously-unidentified `proprietary` committee, taken all the way to a real matcher report in
  one session. Full recon done via static JS bundle analysis (`ykpubdata.jerusalem.muni.il`, React
  SPA) + live network captures with colleague testing from the office.
  - **Two backend hosts, both plain REST/JSON, no Selenium needed:**
    - `jergisinfohub.jerusalem.muni.il` `GET /Services/api/MetaDataObjectsDetails/1?gush=X&helka=Y&...`
      — the רישוי בניה (`RishuiBniya`) parcel search, confirmed live. One row per תיק:
      `tik_num`, `taarih_ptiha` (open date), `sug_bakasha` (type, often comma-joined multi-value),
      `r_status`/`r_taarih_status` (רישוי status/date), `p_taarih_status`, `shimush`, `mevakesh`, `address`.
    - `jerbasicserviceapi.jerusalem.muni.il` `POST /api/Db/ExecuteGetJSON` — generic stored-proc
      executor (`{"ProcName": <int>, "Cnn": "cnnGisYk", "Parameters": {...}}`), ~28 proc IDs mapped
      from the JS bundle. Two wired up: `242700473` (getProcessesContentPikuahBniaData, פיקוח stage
      table — confirmed live schema `stepCodeText`/`stepStatusText`/`execDateStr`/`planDateStr`) and
      `242700437` (fetchTikRushiData, thin misparTik lookup used by the sweep, see below).
  - **Both hosts hit a transient Akamai 403 during initial recon** (non-office network) that cleared
    on retest minutes later with no network change — looks like a burst rate-limit, not a persistent
    office-IP gate like Complot. The full production run (below) completed with zero 403s.
  - **No citywide "recent permits" feed exists** — every endpoint requires a search key (gush/helka,
    street, תיק number, or תב"ע number). Scraper iterates (gush, helka) pairs already tracked in
    `docs/all_projects_08072026.xlsx` (2,530 unique pairs for ירושלים) rather than discovering new
    permits from nothing.
  - Colleague's field rules confirmed and encoded: תאריך בקשה = `taarih_ptiha`; תאריך היתר =
    `r_taarih_status` when `r_status` = "הופק-הוצא היתר בניה"; אכלוס/טופס 4 = פיקוח stage table,
    `stepCodeText` matching "מסירת טופס 4"/"הפקת טופס 4"/"תעודת גמר" **and** `stepStatusText` = "בוצע"
    (not "מתוכנן") — confirmed against real data (permits resolving to `טופס 4` in both the smoke
    test and the full run).
  - **Full run completed**: all 2,530 parcels → **7,927 unique permits** → `outputs/jerusalem_fresh.csv`.
    `STATUS_MAP` grew to ~26 statuses from real data (started at 4 from initial recon); scraper logs
    `[NEW STATUS]` for anything unmapped, same convention as Bartech/Complot — check
    `scrapers/jerusalem/api_scraper.py` for the current full list.
  - **Matcher wired and run**: new `scripts/run_jerusalem_matcher.py` (same pattern as
    `run_harel_matcher.py`). min_year auto-computed as 2005; 7,927 → 6,004 permits after the filter;
    **111-row report** (`outputs/jerusalem_report.xlsx`) — 103 `status_advanced`, 8 `untracked`, 0
    `new_permit`, 0 `manual_review`. Matched cache: 3,611 permits (`outputs/jerusalem_matched_cache.json`).
  - **Known gap, flagged in the matcher script's docstring, not yet confirmed**: Jerusalem's API has
    no separate request-category field distinct from request_type, so `EXCLUDED_REQUEST_CATEGORIES`
    (בקשה מקדמית etc.) can't filter anything for this city — only safe if רישוי בניה search results
    are always finalized permit files, never preliminary/info-request stages. Spot-check the 8
    `untracked` rows and a sample of `status_advanced` rows against this assumption.
  - **Sequential תיק-number sweep built but NOT YET RUN** — `JerusalemPermitsAPI.sweep_by_tik_number()`
    + a sweep phase in `scripts/run_jerusalem.py` (gated by `RUN_SWEEP = True`, uses the same
    `_compute_min_year` convention as every other city). Unit-tested on year 2020 numbers 1-442 (570
    results, correctly reproduced `2020/0440.00`/`.01`'s status from the independent parcel-search
    path). **The completed full run above predates this code** (the sweep was added to
    `run_jerusalem.py` *after* that background run had already started with the old file loaded), so
    it has never actually run end-to-end as part of a full scrape. Next session: run it (either via
    `scripts/run_jerusalem.py` end-to-end, which will redo the parcel scrape too, or by calling
    `sweep_by_tik_number()` directly against the existing `jerusalem_fresh.csv`'s `request_number`
    set as `known_tik_nums`, to avoid rescraping). Results land in `outputs/jerusalem_sweep.csv` and
    are necessarily partial (no gush/helka/address from that endpoint) — needs manual parcel lookup
    before matching against tracked projects.
  - **Not yet done**: double-yod substring check against `transform/matcher.py`'s
    `RELEVANT_TYPE_SUBSTRINGS` on the full dataset (`sug_bakasha` is often a comma-joined multi-value
    string, e.g. "תוספת בניה / הרחבה לבניין קיים, ממ\"ד, בנית מחסן/מחסנים, בניית מרפסת" — matcher
    substring logic needs to handle that); colleague's "gush/helka sometimes has +50 appended to the
    helka" note not yet investigated.

### Session S — 2026-07-16

- **Migrash-based project matching fixed and extended to Bartech** (colleague's Kiryat Ata
  review, `docs/Kiryat_Ata_July_2026.xlsx`, flagged wrong project assignment when multiple
  projects share one גוש/חלקה — e.g. gush/helka `10514-11` covers migrashim 179-238+ under
  `שכונת האבוקדו`, several without a BO project page yet):
  - `transform/matcher.py`: `_parse_migrash` → `_parse_migrash_set` — the old regex only matched
    the literal word "מגרש", but the real `תבע+מגרש` project-file column format is `plan+number`
    (e.g. `תמל/1024+179`, comma-separated for multi-lot projects), so the migrash tie-break had
    silently never fired. `_pick_best_candidate()` now checks migrash before date/fuzzy-name for
    both single- and multi-candidate cases, and returns `None` ("no confident match") when the
    permit's scraped migrash doesn't belong to any gush/helka candidate's migrash set, instead of
    silently misattributing to the wrong project. `_make_row()` now includes `project_migrash` +
    `permit_migrash` columns in every report so this is auditable going forward (colleague's
    explicit request).
  - **Extended migrash scraping to Bartech** (`scrapers/bartech/api_scraper.py`) — previously only
    Complot's scraper captured `migrash`. Confirmed via live screenshots (Rotem) that Bartech's
    מקרקעין cell (list page) and detail-page גוש/חלקה table **both** expose מגרש
    (`מספר מגרש` column on the detail table). Added `_parse_migrash()`, wired into both the
    list-page row parser and `_parse_detail()`/`_enrich_with_details()`, mirroring the existing
    `block_lot`/`detail_block_lot` precedent. Verified against real HTML samples
    (`outputs/debug_bartech_detail.html`) and the screenshot text (`גוש: 31445, חלקה: 46, מגרש: 348`).
  - Verified end-to-end against real Kiryat Ata data: the 5 permits the colleague flagged
    (20240378/382/383/412/413, scraped migrash 187/188/189/191/219) no longer wrongly match
    `מגרש_179_183_האבוקדו` / `מגרש_202_204_האבוקדו` — matcher now correctly declines instead of
    guessing. They won't resurface until the colleague's new project rows (with their own
    `תבע+מגרש` values) are added to the projects file — that's a data step, not a code bug.
  - `docs/all_projects_08072026.xlsx` already has `תבע+מגרש` populated for Bartech cities too
    (4,615/24,886 rows nationwide), so the fix is immediately usable — see Immediate #2 below.

- **All 6 existing Bartech cities rescraped + re-matched** (was Immediate #2, now done) — הולון,
  קריות, חדרה, הראל, זמורה, מיצפה אפק. Results (status_advanced / untracked / manual_review):

  | Committee | New | Prior baseline | Notes |
  |---|---|---|---|
  | הולון | 42 / 36 / 0 (cache 1364) | 194 status_advanced, 3 untracked (very old pre-הסתיים-fix baseline, not a fair comparison) | |
  | קריות | 36 / 14 / 0 (cache 1214) | no documented baseline | |
  | חדרה | 18 / 48 / 0 (cache 782) | no documented baseline | |
  | הראל | 5 / 33 / 0 (cache 155) | 5 / 32 (cache 166, Session J) | stable — little gush/helka overlap here |
  | זמורה | 4 / 70 / 0 (cache 101) | 7 / 70 (cache 264, Session J) | **isolated the fix's exact effect** — re-ran with migrash disabled, confirmed 162-permit cache drop is 100% attributable to the fix; spot-checked 8 permits + all 3 lost status_advanced rows individually, all genuine gush/helka conflicts (see BUG-019) |
  | מיצפה אפק | 17 / 34 / 0 (cache 466) | 14 / 33 (cache 601, Session J) | status_advanced went up — real accumulated progress, not re-tested in isolation |

- **BUG-020 fixed**: Bartech `permit_status_date` was sometimes pulled from the wrong stage table
  when multiple tracks (e.g. permit-issuance vs. work-commencement) reach the same status rank at
  different dates — found via colleague's manual review of `harel_report_15_07_2026.xlsx` (2 of
  her flagged permits, `20240647`/`20190029`, had a correct status but a date off by 7 weeks / 1
  day respectively). Fixed by adding `_parse_certificates()`, which reads the detail page's
  authoritative `תעודות` (certificates) table and overrides the date for `היתר`/`טופס 4` when
  present. Verified against both permits' real detail-page HTML — both now produce the exact
  colleague-confirmed correct date. **Not yet re-run against the 6 rescraped cities' detail
  pages** — this fix landed after their rescrape completed; see Immediate item below.

- **BUG-021 fixed**: Tel Aviv scraper's `_query()` retry loop didn't catch Selenium exceptions
  mid-attempt (only bad *responses*) — a `TimeoutException` on a retry attempt crashed the entire
  `_smoke_test_tel_aviv.py` run outright. Now wrapped in `try/except WebDriverException`, treated
  like any other retryable outcome, with a forced driver restart.

- **Tel Aviv smoke test run live (post-fix)** — very informative, but not in the way hoped:
  - Only 2 of 5 parcel queries and 0 of 9 scan queries succeeded; every other query was
    reCAPTCHA-rejected even after 3 retries with backoff up to 3+ minutes.
  - **Rotem manually tested the same UI by hand** (not automated) to isolate whether this was
    automation-detection: **a real human hit the identical wall after just 4 searches** in a few
    minutes — the איתור button simply stopped responding, no error shown. This rules out
    automation-detection as the cause — it's IP/session-level reCAPTCHA Enterprise throttling that
    catches genuine human traffic too, not something specific to the scraper.
  - **Not yet determined**: whether it recovers after a cooldown, and whether the "nothing
    happens" failure is a client-side token-mint hang or a silent server rejection. A precise
    Claude-Desktop investigation prompt was written (see chat) but not yet run — do this before
    touching the scraper again, since it determines whether the full 3,893-pair scrape is even
    achievable at any pace, or needs a fundamentally different approach.
  - Left `scripts/_smoke_test_tel_aviv.py`'s browser session mid-run when Rotem closed the Chrome
    window manually; process was killed cleanly (`TaskStop`), no `outputs/tel_aviv_fresh.csv`
    produced this session.

- **Complot triage additions** (מורדות כרמל event classification, colleague export 2026-07-15/16):
  2 new `EVENT_TO_STATUS` entries (`הפקת טופס 4`, `מסירת טופס 4` → `'טופס 4'`), 102 new
  `_UNMAPPED_EVENTS`, 13 new `_MANUAL_REVIEW_EVENTS`. Added to `scrapers/complot/api_scraper.py`,
  checked for zero duplicates/conflicts against existing entries before merging. **מורדות כרמל
  matcher not yet re-run** with these — still only ~22/138 events were classified as of the
  original Session O run; check with colleague whether triage is now complete before re-running
  (see existing Immediate #1 item below, still open).

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

### 1. ~~Complot triage artifact — colleagues to finish classifying~~ — CLOSED (2026-07-22)

Rotem confirmed `docs/Request Status's- Claude (1).docx` is the **final** colleague mapping —
whatever isn't explicitly given a status in it should NOT be attributed to a permit stage
(stays unmapped). Verified: all 121 entries in that document (2 `EVENT_TO_STATUS`, ~99
`_UNMAPPED_EVENTS`, ~13 `_MANUAL_REVIEW_EVENTS`) already exactly match what's in
`scrapers/complot/api_scraper.py` — this is the same export applied back in Session O
(2026-07-15/16), not a newer one. No code change needed; the backlog is considered resolved as
final, not merely paused.

The 2 events flagged in earlier sessions as still needing a guess — `מסירת אישור הרצת מערכות`
(23 occurrences) and `הפקת אישור הרצת מערכות` (26 occurrences), previously noted as "likely →
היתר" — are confirmed to stay **unmapped** per the final mapping, not היתר. This lines up with
BUG-024 (see `docs/BUG_REFERENCE.md`): `_map_event()` now explicitly ignores any `הרצת מערכות`
phrasing regardless of classification, since it's a pre-occupancy technical checkpoint, not a
real milestone.

### 2. ~~Rescrape + re-run matcher for existing Bartech cities (migrash fix)~~ — DONE (Session S, 2026-07-16)

All 6 cities rescraped + re-matched: הולון, קריות, חדרה, הראל, זמורה, מיצפה אפק. Results and
per-city verification notes are in Session S (Done, above). Zmora's fix effect was isolated and
individually verified; the others were spot-checked less deeply — worth a closer look if their
`untracked` counts look off in review.

**Follow-up — DONE (2026-07-22)**: BUG-020 dates corrected via a targeted re-enrichment
(`scripts/reenrich_bartech_dates.py`) that re-fetched only the `היתר`/`טופס 4` detail pages
(the two statuses `_parse_certificates()` can override) for all 6 cities, reconstructing each
permit's `definement_type` from its saved `request_category` label instead of redoing the list
phase. Correction counts: הולון 4,654/5,096 (91%), קריות 841/1,391 (60%), חדרה 204/2,260 (9%),
הראל 322/479 (67%), זמורה 373/779 (48%), מיצפה אפק 1,301/1,641 (79%) — **7,695 dates corrected
total**. All 6 matchers re-run; report row counts barely moved (this bug only ever fixed the date
on an already-correctly-ranked status, never which milestone was reached). Pre-fix backups kept at
`outputs/{city}_fresh_pre_bug020.csv`.

### 3. Tel Aviv reCAPTCHA throttling — ON HOLD (Rotem's call, 2026-07-16), full findings below

**Status: paused.** Not resuming scraper work until the open question below is answered.

**What's confirmed:**
- The failure is **server-side, not a client-side hang** (Claude Desktop CDP investigation,
  2026-07-16). A real reCAPTCHA Enterprise token is minted and sent with every request via
  `X-Client-Assertion`; the Tel Aviv API gateway (`apimtlvprd.tel-aviv.gov.il`) responds `400
  Invalid assertion` in ~150ms. Angular's `HttpClient` error handler swallows the 400 silently —
  no UI feedback at all, which is why the איתור button just appears to do nothing.
- BUG-021 fixed this session (uncaught Selenium exception mid-retry could crash the whole scrape)
  — stands regardless of the throttling question below.

**What's NOT actually resolved yet, despite the investigation** — the Claude Desktop test used a
CDP-driven browser (same underlying protocol our own scraper's `undetected_chromedriver` uses,
just without its anti-detection patches) and got rejected on **every single attempt, including
the very first** — unlike Rotem's manual test (real browser, first 3-4 searches succeeded) and
unlike our own scraper's earlier smoke test (also got real 200s before degrading). A
permanently-flagged-as-automated session failing immediately, and staying failed after a 63-minute
wait, tells us nothing about whether a *real* session's score recovers after backing off — it was
guaranteed to fail throughout regardless of timing. The report's `action: "register"` theory is
also weakened by Rotem's own results: a static action-name mismatch would have rejected his first
search too, not just the later ones. Score decay from request volume/pattern (with CDP sessions
starting from a permanently-low floor) fits both datasets better than an action-name bug.

**The actual open question, unanswered**: does a real browser session's score recover after a
cooldown once it degrades? Only testable by waiting on an *already-blocked real* tab (Rotem's own,
or our scraper's own session) and retrying — a fresh automated session can't answer this, since
it's disqualified before request volume even becomes a factor. This determines whether the full
3,893-pair scrape is achievable at any pace (if score recovers, slower pacing may work) or needs a
fundamentally different approach (if it doesn't recover, or recovery is too slow to be practical).

**Next step when resumed**: Rotem waits on his own already-stuck browser tab (15-20+ min), retries
the same query, and reports whether it starts working again — no scraper code changes until that's
answered.

### 4. Build custom crawlers for non-Complot/Bartech committees

4 active-but-excluded committees have a real portal but run neither Complot nor Bartech
(`config/committees.py`, `exclude_reason` in `proprietary`/`url_unverified`):

| Committee | Reason | URL / notes |
|---|---|---|
| נתניה | `url_unverified` — **RESOLVED, confirmed Bartech** | `https://vaadnet.netanyagis.co.il` — see below |
| תל אביב יפו | `proprietary` — **partial recon done (2026-07-15)** | system identified, API host not yet confirmed — see below |
| ירושלים | `proprietary` — **scraper built + full run + matcher done (2026-07-16)** | custom REST API, `scrapers/jerusalem/api_scraper.py` — see Session T in Done, and sweep TODO below |
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

**ירושלים identified, scraper built, full run + matcher done (Session T, 2026-07-16)** — genuinely
custom (not a disguised Complot/Bartech instance), see Session T write-up in Done and
`scrapers/jerusalem/api_scraper.py` docstring for the full API mapping. Remaining work:
1. ~~Run the sequential תיק-number sweep~~ — **DONE (Session U, re-run completed 20,693 rows;
   Session V enriched 18,871/20,693 with block_lot/full_address — manual parcel lookup gap closed,
   see Session V write-up in Done above).** Original text kept below for history.
1. **Run the sequential תיק-number sweep** (`JerusalemPermitsAPI.sweep_by_tik_number()`, built and
   unit-tested this session but never run as part of a full scrape — the completed full run predates
   this code, see Session T for why). Either re-run `scripts/run_jerusalem.py` end-to-end
   (`RUN_SWEEP = True` is already set) or call `sweep_by_tik_number()` directly against the existing
   `outputs/jerusalem_fresh.csv`'s `request_number` set to skip re-scraping known parcels. Results
   are partial (no gush/helka/address) and need manual parcel lookup before matching.
   - **[2026-07-17 attempt] Got IP/rate-blocked partway through, killed.** Standalone runner
     `scripts/run_jerusalem_sweep.py` (new this session, reuses `jerusalem_fresh.csv`'s
     `request_number`s as `known_tik_nums` so it doesn't re-scrape parcels) completed years 2005-2007
     cleanly (1193/1122/978 found), but a **duplicate accidental second
     process** (an earlier Start-Process launch that a flawed process-liveness check wrongly reported
     as exited) ran concurrently against the same API from ~03:44-04:40, doubling request volume.
     `jerbasicserviceapi.jerusalem.muni.il` started returning `403 Forbidden` on every single request
     from 04:27:47 onward (492 consecutive 403s confirmed before the process was killed) — years
     2008/2009's "0 found" / low counts in the log are **not real** (every request in that window was
     blocked, not genuinely empty) and must be re-swept once unblocked.
     - **Fixed (2026-07-18)**: `_fetch_tik_rushi()`, `_fetch_rishui_bniya()`, and `_fetch_pikuah_stages()`
       in `scrapers/jerusalem/api_scraper.py` now return a 3-way `('ok'|'blocked'|'error', data)` outcome
       instead of silently treating any request exception (including a 403 block) as an ordinary empty
       result. A new `_with_retry()` helper retries blocked/error outcomes with backoff (up to 3 tries)
       and logs `[GIVE UP]` + a final inconclusive-count summary if still unresolved, rather than feeding
       them into the miss-streak counter as fake "not found" hits — same fix already applied to Tel
       Aviv's Selenium scraper. Smoke-tested against both live paths (`sweep_by_tik_number` and
       `scrape_parcels`'s `_fetch_rishui_bniya`) — both return real data, no regressions.
     - **Block confirmed cleared (2026-07-18)** — direct test against `jerbasicserviceapi` returned the
       known-good result for `2020/0440.00`. Sweep relaunched same day as a single process (checked
       `Get-CimInstance` first for stray processes, per the lesson above) — years 2005-2007's results
       from the killed run were never persisted (the script only writes the CSV once at the end), so
       it's redoing the full sweep from scratch rather than resuming.
2. ~~Double-yod substring check against `RELEVANT_TYPE_SUBSTRINGS`~~ — **DONE (Session V)**: no
   actual double-yod bug found (comma-joined `sug_bakasha` substring matching works fine), but
   surfaced a genuine new tracked-type gap (`תוספת יח"ד באמצעות תוספת בניה`, 486 occurrences) — now
   added to `RELEVANT_TYPE_SUBSTRINGS`, see Session V write-up in Done above.
3. Spot-check the "no request-category field" assumption flagged in
   `scripts/run_jerusalem_matcher.py` — confirm רישוי בניה search results never include
   preliminary/info-request stages that should've been excluded. **Still open (Session V: reviewed
   and explicitly left for a future session, per Rotem).**
4. Colleague's "gush/helka sometimes has +50 appended to the helka" note — not yet investigated.
5. **[Sunday 2026-07-19] Check for a Jerusalem GIS-layer scrape method, same pattern as Tel Aviv** —
   **DONE (Session U): negative result**, no ArcGIS/Esri references found anywhere in Jerusalem's
   JS bundle or backend hosts; genuinely custom system, ruled out. Original text kept below for
   history.
   This session (2026-07-17) found that Tel Aviv has a public, unauthenticated ArcGIS Feature Layer
   (`gisn.tel-aviv.gov.il/arcgis/rest/services/WM/IView2WM/MapServer/772`) exposing the entire
   permit-request table directly — no reCAPTCHA, no per-parcel iteration, just paginated `/query`
   calls — plus a separate WCF lookup resolving building → גוש/חלקה
   (`handasa.tel-aviv.gov.il/_vti_bin/.../TlvList.svc`). See `scrapers/tel_aviv/gis_api_scraper.py`
   for the full working implementation. Worth checking whether Jerusalem's municipality runs a
   similar public ArcGIS/GIS backend (`ykpubdata.jerusalem.muni.il` is a React SPA — check for an
   underlying MapServer the way `jergisinfohub`/`jerbasicserviceapi` were found via static JS bundle
   analysis in Session T). If one exists and exposes the same רישוי בניה data as a queryable layer,
   it could replace or complement the current custom REST scraper
   (`scrapers/jerusalem/api_scraper.py`) — possibly avoiding the parcel-iteration requirement (no
   citywide feed currently exists for Jerusalem) and the sequential תיק-number sweep entirely.

For קצרין, the system still isn't identified at all — first session should be pure
reconnaissance (view-source, network tab, robots.txt) with no scraper code written until
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

### 5. Review pending reports (with colleague)

| Committee | Report | Key figures |
|---|---|---|
| מורדות כרמל | `outputs/mordot_carmel_report.xlsx` | 10 status_advanced, 16 untracked, 2 manual_review — triage confirmed **final** and already fully applied (2026-07-22, see item #1); no reclassification pending |
| קרית אתא | `outputs/kiryat_ata_report.xlsx` | 14 status_advanced, 41 untracked, 59 manual_review — pre-migrash-fix; consider re-scraping to pick up BUG-019 fix like the Bartech cities were |
| הולון | `outputs/holon_report.xlsx` | 42 status_advanced, 36 untracked, 0 manual_review (rescraped Session S) |
| קריות | `outputs/krayot_report.xlsx` | 36 status_advanced, 14 untracked, 0 manual_review (rescraped Session S) |
| חדרה | `outputs/hadera_report.xlsx` | 18 status_advanced, 48 untracked, 0 manual_review (rescraped Session S) |
| הראל | `outputs/harel_report.xlsx` | 5 status_advanced, 33 untracked, 0 manual_review (rescraped Session S) — **colleague review complete, see below** |
| זמורה | `outputs/zmora_report.xlsx` | 4 status_advanced, 70 untracked, 0 manual_review (rescraped Session S) |
| מיצפה אפק | `outputs/mitzpe_afek_report.xlsx` | 17 status_advanced, 34 untracked, 0 manual_review (rescraped Session S) |
| ישובי הברון | `outputs/yishuvei_habaron_report.xlsx` | 2 status_advanced, 49 untracked |

Kiryat Ata `manual_review` events to watch: `ביטול היתר`, `החלטת ועדת ערר`, `הפקת פרסום תמ"38`.

**הראל colleague review complete** (`docs/harel_report_15_07_2026.xlsx`, comment column, reviewed
Session S) — mostly confirms the report is accurate (~20 of ~37 commented rows: "correct status
and date"), plus real findings:
- **BUG-020 found and fixed this session** (see Done above) — 2 permits had a status confirmed
  correct but a wrong date, traced to the exact root cause and fixed.
- **7 permits**: "correct status, incorrect date" or "incorrect status" with no code-level cause
  identified yet — worth checking whether these are further instances of BUG-020's pattern (a
  fresh Harel re-scrape with the fix would clarify) or a separate issue.
- **7 permits**: existing project `הרימון_קרית_יערים` (and one for `החוצבים_5_מבשרת_ציון`) not
  recognized because "request has new lot, while the project has old lot" — **this is a projects-file
  data-staleness issue, not a scraper/matcher bug**: the BO project record's own גוש/חלקה needs
  updating to the parcel's current numbering (likely a תב"ע-driven re-subdivision). Flag to
  whoever maintains the projects export.
- **1 permit** (`20250630`, "not valid as a new project- 2 units") slipped through
  `_is_below_unit_minimum` uncaught: its `bakasha_description` says "שתי יח"ד" (Hebrew number
  word "two", not the digit `2`), and `_extract_unit_count()` in `transform/matcher.py` only
  parses digit patterns — a narrow, safe enhancement (recognizing אחד/אחת/שני/שתי/שלושה/ארבעה as
  1-4) would let the matcher catch this automatically instead of relying on manual review. Not
  yet implemented — flagged here for whenever unit-minimum false negatives are worth tightening.
- ~15 permits: correctly flagged untracked, colleague confirmed as genuine new projects and
  assigned new project IDs (e.g. `הפלמח_56_מבשרת_ציון`, `הכרמים_62א_מבשרת_ציון`) — validates the
  untracked-flagging mechanism itself is working well.

### 6. Classify Hadera unmapped stages + add to scraper

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

### 10. Add projects from local-committee + מבא"ת (mavat) land-use plan searches

**Not to be started until local committee permit scraping + matching is fully honed** (V1/V2 above
stable, low noise). A further-out project-discovery source, separate from permit tracking:

Use local planning committee searches and מבא"ת (mavat) plan searches to surface new projects
directly from land-use plan approvals/deposits, rather than waiting for a building permit to be
filed against a project we already track. This would let us catch genuinely new projects earlier
in their lifecycle (plan stage, before any permit request exists) instead of relying entirely on
the permit-side `untracked`/`new_permit` flags in the current matcher.

Methodology to reuse: the plan-search approach currently being developed in the separate
`projects_monitor` project — check there for the current state of that work before designing this
from scratch.

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
