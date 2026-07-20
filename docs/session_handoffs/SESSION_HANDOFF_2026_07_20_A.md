# Session Handoff — 2026-07-20 A

**Date:** 2026-07-20
**Session:** U (follows Session T, 2026-07-16)
**Scope:** Tel Aviv GIS-layer scraper built + full run + matcher; Jerusalem sweep blocked-vs-not-found
bug found and fixed, sweep re-run to completion; אשקלון (Ashkelon) added via Complot, full run +
matcher; nationwide projects-export pipeline fixed (grain bug + scope check) and migrated to a
stable filename with auto-promoting weekly automation.

---

## What was accomplished

### Tel Aviv: new GIS-layer scraper replaces the paused reCAPTCHA approach

Rotem found that `gisn.tel-aviv.gov.il` runs a genuine public **ArcGIS Feature Layer** (layer 772,
"בקשות והיתרי בניה") — no auth, no reCAPTCHA, standard `/query` REST API, fully paginated
(10,538 total rows). This sidesteps the Tel Aviv reCAPTCHA Enterprise problem that's been on hold
since Session R/S entirely, for permit discovery at least.

- **`scrapers/tel_aviv/gis_api_scraper.py`** — paginates the whole layer, merges multi-building
  request rows by `request_num`, derives `permit_status` straight from date fields
  (`occupation`→טופס 4, `permission_date`→היתר, `open_request`→בקשה להיתר) — no second API call
  needed, unlike Jerusalem's פיקוח lookup.
- **Gush/helka resolution — a second discovery, chased down via Claude Desktop**: the buildings
  layer (513) links to a תיק בניין archive at `archive-binyan.tel-aviv.gov.il` (real host:
  `handasa.tel-aviv.gov.il`). A Claude Desktop browser investigation (detailed prompt in this
  session's chat log) found the actual data call: an anonymous WCF REST endpoint
  (`_vti_bin/TlvSP2013PublicSite/TlvList.svc/GetListItemsByFieldFilterStringWithQuery`) keyed by
  תיק בניין number, returning `EngFolderBlocksParcels` (`"{gush}_{helka},..."`). Verified live,
  no auth, clean `[]` on unknown IDs. Only resolves ~26% of permits (2,281/8,898) — the archive
  doesn't index every building — so **`transform/address_match.py` was fixed** to handle
  comma-joined multi-address strings (each segment matched independently) as the fallback for the
  rest. This fix is generically useful, not Tel-Aviv-specific.
- **Full run**: 10,538 raw rows → 8,898 merged permits → `outputs/tel_aviv_gis_fresh.csv`.
  Status breakdown: 4,994 היתר, 2,830 בקשה להיתר, 1,074 טופס 4.
- **Matcher**: `outputs/tel_aviv_gis_report.xlsx` — 107 rows (24 status_advanced, 83 untracked, 0
  new_permit/manual_review); cache 2,959 permits (`outputs/tel_aviv_gis_matched_cache.json`).
- **Not yet done**: spot-check a sample of status_advanced/untracked rows against reality —
  standard due-diligence for a brand-new scraper, not done this session. Address-matched
  (non-gush/helka) rows carry most of the matching load here and are the ones most worth
  checking first.

### Jerusalem: real bug found and fixed, sweep completed

Attempted the sequential תיק-number sweep (carried over from Session T). Hit a genuine IP/rate
block on `jerbasicserviceapi.jerusalem.muni.il` — 492 consecutive `403 Forbidden` responses —
caused by an accidental **duplicate scrape process** (a stale `Start-Process` launch from earlier
that a flawed liveness check had wrongly reported as exited) running concurrently with the real
sweep for about an hour, doubling request volume. Both processes were killed.

- **Root cause was a real bug in the scraper, now fixed (BUG-022, see `docs/BUG_REFERENCE.md`)**:
  `_fetch_rishui_bniya()`, `_fetch_pikuah_stages()`, `_fetch_tik_rushi()` in
  `scrapers/jerusalem/api_scraper.py` treated any request exception (including a 403 block) as an
  ordinary empty result, feeding straight into the miss-streak counter as fabricated "not found"
  data. Fixed: all three now return a 3-way `('ok'|'blocked'|'error', data)` outcome; a new
  `_with_retry()` helper retries blocked/error with backoff and logs `[GIVE UP]` + an
  inconclusive-count summary if still unresolved, same pattern as `scrapers/tel_aviv/scraper.py`.
  Smoke-tested on both `scrape_parcels` and `sweep_by_tik_number` paths before the real re-run —
  no regressions.
- **Checked whether Jerusalem has a Tel-Aviv-style public ArcGIS layer** (the Sunday follow-up from
  Session T) — **negative result**. No `arcgis`/`esri`/`MapServer` references anywhere in the JS
  bundle or either backend host; Jerusalem's `jergisinfohub`/`jerbasicserviceapi` is genuinely
  custom, unlike Tel Aviv's real Esri ArcGIS Server. Ruled out — don't revisit without a new lead.
  Confirmed the rate-limit block clears on its own (same as the earlier Session T incident).
- **Sweep re-run to completion, single verified process this time**: all years 2005–2026 swept
  cleanly, no further blocks. Per-year found counts (real data): 2005:1193, 2006:1122, 2007:980,
  2008:911, 2009:996, 2010:1372, 2011:1383, 2012:1155, 2013:1333, 2014:1215, 2015:1043, 2016:1574,
  2017:1164, 2018:902, 2019:608, 2020:754, 2021:496, 2022:533, 2023:552, 2024:560, 2025:520,
  2026:327 (partial year, current as of session date). **Total: 20,693 תיק rows** written to
  `outputs/jerusalem_sweep.csv`.
  **Not yet done**: this sweep's results are necessarily partial (no gush/helka/address from
  `fetchTikRushiData`'s schema) — still need manual parcel lookup before matching against tracked
  projects, per the original design note in `sweep_by_tik_number()`'s docstring.

### אשקלון (Ashkelon) — new committee, Complot, site_id=95

Was already present in `config/committees.py` (active, never run). Smoke-tested first (6,848
unique permits in the list phase alone, clean, no blocks — confirmed reachable from home network
this time, unlike some other Complot committees). Built `scripts/run_ashkelon.py` +
`run_ashkelon_matcher.py` (same pattern as `run_mordot_carmel.py`).

- **Full run**: 6,612 permits → `outputs/ashkelon_fresh.csv` (min_year=2011 auto-computed).
  Double-yod check passed — all construction-type strings use single-yod spelling consistently,
  already covered by `RELEVANT_TYPE_SUBSTRINGS`. One minor note: `ביטול היתר ובנייה מחדש`
  ("permit cancellation and rebuild") is a double-yod phrase but a genuinely distinct category
  from the tracked `הריסה ובניה`/`הריסה ובנייה` substrings, not a spelling-variant bug — only 6
  occurrences, negligible, not added to `RELEVANT_TYPE_SUBSTRINGS` this session.
- **Matcher**: `outputs/ashkelon_report.xlsx` — 42 rows (18 status_advanced, 24 untracked, 0
  new_permit/manual_review); cache 531 permits (`outputs/ashkelon_matched_cache.json`). (Numbers
  shifted slightly from an earlier 40-row/16-status_advanced run after the projects-file grain fix
  below landed — re-ran and these are the current, correct numbers.)
- **Not yet set**: `permit_url_base` — no public portal URL pattern confirmed yet for this
  committee, left blank in the matcher runner.

### Nationwide projects export: grain bug fixed, scope verified, migrated to a stable filename

Rotem dropped a fresh `outputs/madlan_projects_fresh.csv` (Looker MCP export via Claude Desktop)
mid-session. Converting and sanity-checking it against the production file
(`docs/all_projects_08072026.xlsx` at the time) surfaced two real problems, both now resolved:

1. **Row-grain mismatch**: the raw export is at "one row per (project, stakeholder)" grain — the
   Looker tile is literally named "Projects by each developer/architect/lawyer" — giving ~2 rows
   per project (45,639 rows / 23,305 projects) vs. the production file's ~1 row per project
   (24,886 / 23,233). **Root cause (found and fixed by Claude Desktop, same day)**: a Looker LEFT
   JOIN was producing one spurious null-partner row per project alongside real stakeholder rows.
   Fix: drop null-partner rows for projects that have ≥1 real stakeholder, keep them for the 1,086
   projects with no stakeholder at all. Verified: corrected export now 24,992 rows / 23,305
   projects, matching production's shape almost exactly.
2. **One-off scope narrowing** (2026-07-19 export only): 42 cities completely missing (mostly
   Judea/Samaria settlements, several Druze/Arab towns, and קצרין — see full list in this
   session's chat log or `git log` on this handoff's date). Did **not** recur on the next day's
   pull (all 162 cities present) — looks like a transient export glitch, not an intentional scope
   change, but worth watching for recurrence.

**Automation built per Rotem's request** (`scripts/check_projects_refresh.py`):
- Detects when `outputs/madlan_projects_fresh.csv` is newer than the last-processed xlsx, converts
  it via `fetch_projects.from_csv()` (no duplicated logic), then runs a scope+grain sanity check
  (city coverage, project-ID overlap, rows-per-project ratio — the same checks that caught both
  issues above) and **auto-promotes** the new export over the production file only when all
  checks pass; otherwise logs `[ALERT]` and leaves production untouched.
- Registered as a **daily Windows Scheduled Task** (`MadlanProjectsRefreshCheck`, 8:00 AM), logging
  to `outputs/projects_refresh_check_log.txt`.
- Real constraint documented: the CSV export itself still needs a human (or interactive Claude
  Desktop session) to run the Looker MCP connector — **cannot be scheduled/headless**
  (interactive-auth MCP servers are unavailable in cron/headless contexts). Full zero-touch
  automation (including the export step) would need real Looker API credentials for
  `fetch_projects.py`'s already-built `from_sdk()` path — not pursued this session, Rotem chose
  to automate just the conversion+promotion half.
- **Verified live end-to-end**: forced a refresh cycle, watched convert → check → auto-promote,
  then confirmed a real matcher script (`run_ashkelon_matcher.py`) picks up the new data correctly.

**Production file renamed** to remove the hardcoded date: `docs/all_projects_08072026.xlsx` →
`docs/all_projects.xlsx` (git-tracked rename, history preserved via `git mv`). **All 19 files**
that referenced the old dated filename now point at the stable name (`config/committees.py` + every
`run_*`/`run_*_matcher.py` script) — this is the actual fix for "why does every weekly refresh
touch 19 files": the filename never needs to change again, only its contents (via the scheduled
auto-promote above).

---

## Open items carried forward

1. **Jerusalem sweep — complete** (20,693 תיק rows, `outputs/jerusalem_sweep.csv`). Results are
   partial (no gush/helka/address) and need manual parcel lookup before matching against tracked
   projects — that lookup step itself is not yet built.
2. **Tel Aviv GIS report**: spot-check a sample of `status_advanced`/`untracked` rows against
   reality, especially address-matched (non-gush/helka) ones — standard due-diligence for a new
   scraper, not done yet.
3. **Ashkelon**: confirm/find a public `permit_url_base` if one exists; not urgent.
4. **Ashkelon double-yod note**: `ביטול היתר ובנייה מחדש` (6 occurrences) doesn't map to any
   `RELEVANT_TYPE_SUBSTRINGS` entry — decide if it should be tracked (a rebuild after permit
   cancellation is arguably relevant new construction) before it recurs at higher volume in
   another city.
5. Everything else carried forward from Session T (double-yod check on Jerusalem's `sug_bakasha`,
   the "no request-category field" assumption spot-check, colleague's "+50 on helka" note, קצרין
   recon, Complot triage artifact) is still open — untouched this session.

---

## State of key files

| File | State |
|---|---|
| `scrapers/tel_aviv/gis_api_scraper.py` | New — `TelAvivGisAPI`, plain-HTTP ArcGIS + WCF gush/helka resolver |
| `scripts/run_tel_aviv_gis.py` / `run_tel_aviv_gis_matcher.py` | New — runner + matcher for the GIS approach |
| `outputs/tel_aviv_gis_fresh.csv` / `tel_aviv_gis_report.xlsx` / `tel_aviv_gis_matched_cache.json` | New — 8,898 permits, 107-row report, 2,959-permit cache |
| `transform/address_match.py` | Fixed — handles comma-joined multi-address strings |
| `scrapers/jerusalem/api_scraper.py` | Fixed — BUG-022, 3-way blocked/error/ok outcome + `_with_retry()` |
| `outputs/jerusalem_sweep.csv` | New — sweep results, check final line of the log for completion status |
| `scrapers/complot/api_scraper.py` | Minor — new `_UNMAPPED_EVENTS` from Ashkelon's first run (see log) |
| `scripts/run_ashkelon.py` / `run_ashkelon_matcher.py` | New |
| `outputs/ashkelon_fresh.csv` / `ashkelon_report.xlsx` / `ashkelon_matched_cache.json` | New — 6,612 permits, 42-row report, 531-permit cache |
| `scripts/fetch_projects.py` | Unchanged — reused by the new check script |
| `scripts/check_projects_refresh.py` | New — auto-convert + scope/grain check + auto-promote, registered as a daily Scheduled Task |
| `docs/all_projects.xlsx` | Renamed from `all_projects_08072026.xlsx` (git-tracked rename), content refreshed via auto-promote |
| `config/committees.py` + 18 `run_*`/`run_*_matcher.py` scripts | Updated — `projects_path` now points at the stable filename |
| `docs/BUG_REFERENCE.md` | Updated — BUG-022 added |
| `docs/NEXT_STEPS.md` | Updated — full Session U write-up |

---

## Commit/push status

Not committed as of this handoff being written — see the end of this session for the actual
commit (this handoff is being prepared alongside a `git push`, check `git log` for the real
commit hash and message).
