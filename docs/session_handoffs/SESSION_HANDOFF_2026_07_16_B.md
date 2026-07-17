# Session Handoff — 2026-07-16 B

**Date:** 2026-07-16
**Session:** T (follows Session S, covered in `SESSION_HANDOFF_2026_07_16_A.md`)
**Scope:** ירושלים custom scraper built from scratch — full recon, live schema confirmation via
colleague's DevTools captures, working scraper, full 2,530-parcel production run, matcher wired
and run to a real report, sequential תיק-number sweep built (not yet run)

---

## What was accomplished

### ירושלים identified as genuinely custom (not disguised Complot/Bartech)

Previously `proprietary` / system unknown in `config/committees.py`. Static JS bundle analysis of
`ykpubdata.jerusalem.muni.il` (a create-react-app SPA) found two backend REST hosts, confirmed live
end-to-end this session via a mix of static analysis, curl testing, and colleague's own DevTools
Network-tab captures while logged in from the office:

1. **`jergisinfohub.jerusalem.muni.il`** — `GET /Services/api/MetaDataObjectsDetails/1?gush=X&helka=Y&street=&house=&taba=&migrash=`
   returns the רישוי בניה (`gisObjectName="RishuiBniya"`) list for a parcel: one row per תיק with
   `tik_num`, `taarih_ptiha` (open date), `sug_bakasha` (type — often a comma-joined multi-value
   string), `r_status`/`r_taarih_status` (רישוי status + date), `p_taarih_status`, `shimush`,
   `mevakesh`, `address`. This is the primary data source (full fields, matches colleague's
   description of the "מידע תכנוני מקיף" → "רישוי בניה" workflow exactly).

2. **`jerbasicserviceapi.jerusalem.muni.il`** — `POST /api/Db/ExecuteGetJSON`, a generic
   stored-procedure executor: `{"ProcName": <int>, "Cnn": "cnnGisYk", "Parameters": {...}}`. ~28
   proc IDs mapped from the JS bundle (search `outputs/debug_jerusalem_main.js` for the full list).
   Two wired into the scraper:
   - `242700473` `getProcessesContentPikuahBniaData(TikNum)` — the תהליך פיקוח stage table.
     Confirmed live schema: `stepCodeText` (stage description), `stepStatusText`
     ("מתוכנן"/"בוצע"), `planDateStr`, `execDateStr`. Used for the אכלוס/טופס 4 milestone per
     colleague's rule (`stepCodeText` matching "מסירת טופס 4"/"הפקת טופס 4"/"תעודת גמר" **and**
     `stepStatusText` = "בוצע", not "מתוכנן").
   - `242700437` `fetchTikRushiData` — exact-match misparTik lookup (format `"YYYY/NNNN.SS"`,
     confirmed live), thin schema (`ID`/`tik_num`/`status_code`/`teurStatus`/`taarih_status`/
     `sugbakasha_code`/`teurSugbakasha`/`mahut_bakasha` — no gush/helka/address/mevakesh). Used by
     the sweep (see below).

Both hosts hit a **transient Akamai 403** during the very first recon pass (before confirming with
the user they were "at the office") that cleared on retest minutes later with no network change on
our end — this looked at first like the same office-IP WAF gate Complot has, but turned out to be a
burst rate-limit: the full 2,530-parcel production run later completed with zero 403s from this
same (non-office) environment. Worth re-checking if a future run hits repeated blocks, but "must run
from the office" is not a confirmed requirement the way it is for Complot.

**No citywide "recent permits" feed exists** for either host — every endpoint requires a search key
(gush/helka, street, תיק number, or תב"ע number). This is architecturally different from
Complot/Bartech and shapes the whole scraping strategy: iterate known (gush, helka) pairs rather
than discover permits from nothing.

### Scraper built: `scrapers/jerusalem/api_scraper.py`

`JerusalemPermitsAPI` — plain `requests`, no Selenium. `scrape_parcels(parcel_pairs)` fetches
רישוי בניה rows per parcel, maps to the project's common output schema (same as Bartech/Complot),
then enriches every permit with a פיקוח stage-table lookup for the occupancy status. `STATUS_MAP`
translates `r_status`/`teurStatus` values to the project's status vocabulary (בקשה להיתר / היתר
בתנאים / היתר / טופס 4) — started empty, grew to ~26 real statuses by the end of the full run.
Unmapped statuses auto-log (`[NEW STATUS]`), same convention as every other city's scraper.

Field mapping confirmed against colleague's stated rules and cross-checked twice (once via a
50-parcel smoke test, once independently via the sweep test on year 2020) landing on identical
results for the same תיק (`2020/0440.00`/`.01`):
- תאריך בקשה = `taarih_ptiha`
- תאריך היתר = `r_taarih_status` when `r_status` = "הופק-הוצא היתר בניה"
- אכלוס/טופס 4 = פיקוח stage table, per the rule above

### Runner scripts built

- `scripts/run_jerusalem.py` — loads the 1,646 ירושלים rows from `docs/all_projects_08072026.xlsx`,
  extracts 2,530 unique (gush, helka) pairs via the existing `transform/gush_helka.parse()`, runs
  `scrape_parcels()`, writes `outputs/jerusalem_fresh.csv`. Also has a sweep phase
  (`RUN_SWEEP = True`) added **after** the production run below had already started — see the sweep
  section for why that phase never actually ran yet.
- `scripts/run_jerusalem_matcher.py` — same pattern as `run_harel_matcher.py`, calls
  `transform.matcher.run()` against `jerusalem_fresh.csv`, `city_filter=['ירושלים']`.
  **Flagged, unconfirmed assumption in its docstring**: Jerusalem's API has no separate
  request-category field distinct from request_type, so `EXCLUDED_REQUEST_CATEGORIES` (בקשה מקדמית
  etc.) can't filter anything for this city. Only safe if רישוי בניה results are always finalized
  permit files, never preliminary/info-request stages — not yet spot-checked against a real example.

### Full production run completed

All 2,530 parcels scraped → **7,927 unique permits** → `outputs/jerusalem_fresh.csv`. Took ~35
minutes (parcel search phase fast, ~0.3s/parcel; פיקוח enrichment phase the bulk of the time,
~7,927 lookups at ~0.2s + latency each). No WAF blocks during the run.

### Matcher run — real report produced

`min_year` auto-computed as **2005**. 7,927 → 6,004 permits after the year filter.
**`outputs/jerusalem_report.xlsx`: 111 rows** — **103 `status_advanced`**, 8 `untracked`, 0
`new_permit`, 0 `manual_review`. Matched cache: 3,611 permits
(`outputs/jerusalem_matched_cache.json`).

### Sequential תיק-number sweep — built, unit-tested, NOT yet run in production

Colleague suggested (paraphrased): after covering known gush/helka pairs, sweep sequentially by
תיק number (confirmed format `"YYYY/NNNN"`) to catch permits not yet in the projects export.
Implemented as `JerusalemPermitsAPI.sweep_by_tik_number(years, max_number, sub_indices,
miss_streak_limit, known_tik_nums)`:
- Tries every `sub_indices` entry unconditionally per number (not stopping at the first miss) —
  caught a real bug in an earlier draft: some old filings (e.g. `1962/0077`) start at `.01` with no
  `.00` at all, so breaking early would silently skip them.
- Stops a year after `miss_streak_limit` consecutive numbers with zero hits across all subs.
- Results are necessarily **partial** — `fetchTikRushiData`'s schema has no gush/helka/address/
  mevakesh, so `scrape_status` is always `'partial'` and those fields are left blank rather than
  guessed, flagging the rows for manual parcel lookup.

Unit-tested on year 2020, numbers 1-442 (570 results) — independently reproduced the exact same
status/date for `2020/0440.00`/`.01` that the parcel-search path found, a strong cross-check.

**Never run as part of a full scrape**: the sweep phase was added to `scripts/run_jerusalem.py`
*after* the production run above had already started with the old (pre-sweep) file content loaded
into the running Python process. Next session: either re-run `run_jerusalem.py` end-to-end (redoes
the parcel scrape too — ~35 min again) or call `sweep_by_tik_number()` directly, passing
`jerusalem_fresh.csv`'s `request_number` column as `known_tik_nums` to skip re-fetching known תיקים.

---

## Open items carried forward

- **Run the תיק-number sweep** in production (see above) — built and tested, just never executed
  end-to-end yet.
- **Double-yod substring check** — `sug_bakasha` is often a comma-joined multi-value string (e.g.
  "תוספת בניה / הרחבה לבניין קיים, ממ\"ד, בנית מחסן/מחסנים, בניית מרפסת"). Haven't confirmed
  `transform/matcher.py`'s `RELEVANT_TYPE_SUBSTRINGS` substring-matching handles this correctly
  across the full 7,927-row dataset — only spot-checked on the 50-parcel sample (no problematic
  double-yod variant was actually observed in that sample).
- **No-request-category assumption** — spot-check the 8 `untracked` rows and a sample of the 103
  `status_advanced` rows in `outputs/jerusalem_report.xlsx` against the assumption flagged in
  `scripts/run_jerusalem_matcher.py` (see above).
- **Colleague's "+50 on helka" note** — "לפעמים הם מוסיפים 50 לפי החלקה" (sometimes +50 is appended
  to the helka in their own project records) — not yet investigated. Unrelated to any of the numeric
  IDs seen in the API responses (those are internal record IDs, not a helka-plus-50 pattern).
- Everything else carried forward from `SESSION_HANDOFF_2026_07_16_A.md` (Complot triage,
  BUG-020 rescrape gap, מורדות כרמל matcher re-run, Kiryat Ata re-scrape, Tel Aviv reCAPTCHA — still
  paused, 7 Harel permits data-staleness flag, `_extract_unit_count` Hebrew-number-words gap) is
  still open — untouched this session.

---

## State of key files

| File | State |
|---|---|
| `scrapers/jerusalem/api_scraper.py` | New — `JerusalemPermitsAPI`, `STATUS_MAP` (~26 statuses), `sweep_by_tik_number()` |
| `scripts/run_jerusalem.py` | New — parcel-scrape runner, sweep phase added (not yet run) |
| `scripts/run_jerusalem_matcher.py` | New — matcher runner, run once against `jerusalem_fresh.csv` |
| `outputs/jerusalem_fresh.csv` | New — 7,927 permits from the full parcel-scrape run |
| `outputs/jerusalem_report.xlsx` | New — 111-row matcher report (103 status_advanced, 8 untracked) |
| `outputs/jerusalem_matched_cache.json` | New — 3,611 matched permits |
| `outputs/jerusalem_smoketest.csv` | New — earlier 50-parcel validation run, superseded by the full run |
| `outputs/debug_jerusalem_*.{html,js,json}` | New — recon artifacts (JS bundle, sample API responses) |
| `docs/NEXT_STEPS.md` | Updated — Session T entry, item 4 table row, sweep TODO added to Immediate |

---

## Commit/push status

**Nothing committed this session.** `git status` shows `docs/NEXT_STEPS.md` modified and
`scrapers/jerusalem/`, `scripts/run_jerusalem.py`, `scripts/run_jerusalem_matcher.py` untracked.
`outputs/` is gitignored as usual. Rotem has not asked for a commit yet this session.
