# Session Handoff — 2026-07-15 A

**Date:** 2026-07-15
**Sessions covered:** O, P, Q (2026-07-13 through 2026-07-15 — none of these were committed yet;
last commit on `master` is Session K, `7cd0f59`)
**Scope:** מורדות כרמל scrape/matcher completion; Complot triage artifact rebuild + handoff feature;
V2 consolidated report runner (new); `city` column; new immediate next step (custom crawlers)

---

## What was accomplished

### Session O — מורדות כרמל scrape + matcher, Complot triage artifact rebuild

- **מורדות כרמל scrape completed**: `outputs/mordot_carmel_fresh.csv` — 18,540 permits
  (started ~09:29, finished ~14:44 2026-07-13). 138 unique event strings seen across the full run.
- **Complot triage artifact rebuilt** to match the existing Bartech/Hadera design system (table +
  per-row colored `<select>` + localStorage + "Unset only" filter + search + bulk-ignore). Key
  additions beyond the Bartech design:
  - Count column + sort toggle (count desc / alphabetical) — Complot events have real frequency data
  - 7th classification option `manual_review` (Complot's `_MANUAL_REVIEW_EVENTS`, which Bartech
    doesn't have)
  - Export produces ready-to-paste Python (`EVENT_TO_STATUS` dict lines / `_UNMAPPED_EVENTS` /
    `_MANUAL_REVIEW_EVENTS`), not JSON — and only exports *new* classifications, not ones already
    baked into the scraper file (fixed after first review caught it re-exporting existing presets)
  - **"Hand off to next person" / "Continue from handoff"** — copies/pastes a JSON code so
    classification progress carries across colleagues' separate browsers/devices. Needed because
    localStorage is per-browser; without this, multiple people classifying independently would each
    build an invisible, unmergeable copy of the state.
  - Artifact link: shared with colleagues directly (not persisted in docs — colleague-private link)
  - **138 unique events total, only 22 pre-classified.** ~116 still need triage, including the 2
    events flagged in the prior handoff: `מסירת אישור הרצת מערכות` (23x), `הפקת אישור הרצת מערכות`
    (26x) — both likely `היתר`.
- **מורדות כרמל matcher run** (before triage completed — see caveat below): `outputs/mordot_carmel_report.xlsx`
  — 10 status_advanced, 16 untracked, 2 manual_review, 0 new_permit. 108 projects in
  טירת הכרמל+נשר after city_filter; min_year=2015 auto-computed. Cache:
  `outputs/mordot_carmel_matched_cache.json` (5040 permits).

**⚠️ Caveat carried forward**: the matcher ran with only 22/138 events classified — the ~116
unclassified events (including the two known ones above) currently contribute no status. Once
colleagues finish triage and the Python export is pasted into `scrapers/complot/api_scraper.py`,
**re-run the matcher** — some `untracked`/`manual_review` rows will likely reclassify to
`status_advanced`.

### Session P — V2 consolidated report runner

- **`scripts/run_all_committees.py`** (new) — loops a declarative `COMMITTEE_CONFIGS` list, calls
  `transform.matcher.run()` per committee, merges results with a `committee` column, sorts by
  committee then flag priority, writes `outputs/consolidated_report.xlsx`. Skips (and logs, doesn't
  fail) any committee whose `fresh.csv` doesn't exist yet.
  - Verified working: first run produced 293 rows across 6 committees (חדרה, הראל, זמורה,
    מיצפה אפק, ישובי הברון, מורדות כרמל) — matches each committee's individual matcher output exactly.
  - **Bat Yam / Holon / Kiryat Ata / Krayot / Ramat Gan are NOT in `COMMITTEE_CONFIGS` yet** — no
    dedicated `run_*_matcher.py` script exists for them to copy exact params from (`city_filter`,
    `permit_url_base`). Add once confirmed — do not guess these values (data-integrity rule).
- **V2 blocking prerequisites reassessed**:
  - Nationwide projects export — ✅ already satisfied. `docs/all_projects_08072026.xlsx` (from
    Session L/M's `fetch_projects.py` + Looker MCP workflow) is the shared input across all 6
    configured committees. Still a manual export step, not API-automated, but functionally unblocks V2.
  - Consolidated report — ✅ built this session (see above).
  - **Remaining real blocker**: ~66 of 77 active committees in `config/committees.py` still have no
    scrape at all. This is the actual bottleneck now, not tooling.
- **`city` column added to the consolidated report** (requested after first V2 review):
  - `transform/matcher.py:_make_row()` now includes `city` from `proj['עיר']` when a project matched.
  - `run_all_committees.py`: each `COMMITTEE_CONFIGS` entry has a `cities` list (metadata only, not
    passed to `matcher.run()`). Single-city committees backfill blank `city` cells (unambiguous).
    Multi-city committees (מורדות כרמל, ישובי הברון) only get a real city on matched rows — untracked
    rows stay blank rather than parsing city from `full_address`, since scraped address text uses
    inconsistent spelling/hyphenation across sites (`זכרון-יעקב` vs `זכרון יעקב`) and can include
    neighboring cities outside the committee's own list (verified: an untracked מורדות כרמל permit at
    `רכסים`, not one of the two configured cities — confirms blank was the right call, not a guess).
  - `committee` / `city` / `flag` moved to the front of the column order for filtering.
  - Re-verified after the change: still 293 rows, identical flag counts — the change is additive only.

### Session Q — docs update

- Added a new immediate next step: **build custom crawlers for the 4 active-but-excluded committees
  that run neither Complot nor Bartech** (נתניה, תל אביב יפו, ירושלים, קצרין — see
  `config/committees.py` entries with `exclude_reason` in `proprietary`/`url_unverified`).
  - נתניה has a known candidate URL (`https://vaadnet.netanyagis.co.il`, `url_unverified`) — probe
    it first using the same approach that worked for ישובי הברון (Session K): check whether it's
    server-rendered (requests+BS4 viable) or JS-rendered (needs DevTools/Playwright), and always
    check for a disguised Complot/Bartech signature before building bespoke scraper code — ישובי
    הברון looked like a SharePoint dead end until it turned out to be Complot site_id=14.
  - תל אביב יפו / ירושלים / קצרין (`proprietary`) — system not identified at all yet. First session
    on each should be pure recon (view-source, network tab, robots.txt), no scraper code until the
    access mechanism is confirmed.

---

## Open items carried forward

- **Complot triage**: ~116/138 events still unclassified in colleagues' hands (via the handoff
  artifact link). Re-run מורדות כרמל matcher once done.
- **2 known events still unclassified**: `מסירת אישור הרצת מערכות`, `הפקת אישור הרצת מערכות`
- **V2 runner missing 5 committees**: Bat Yam, Holon, Kiryat Ata, Krayot, Ramat Gan — need their
  exact matcher params confirmed (no existing `run_*_matcher.py` to copy from) before adding to
  `COMMITTEE_CONFIGS`.
- **New crawler recon needed**: נתניה (probe known URL first), תל אביב יפו / ירושלים / קצרין
  (system unknown, pure recon first).
- **Pending report reviews (with colleague)**: קרית אתא, הראל, זמורה, מיצפה אפק, ישובי הברון,
  מורדות כרמל (or just review the new `outputs/consolidated_report.xlsx` instead of per-city files).
- **Hadera stage classification**: separate artifact still open
  (https://claude.ai/code/artifact/c0dae2d0-319e-4123-b580-332c90957984)
- **מורדות כרמל**: scraper still needs office IP for future re-scrapes (WAF blocks home IP)

---

## What to do next session

### Step 1 — Check Complot triage progress

Ask colleagues for their handoff code or check if they've finished. If ~138/138 classified, get the
final Python export and paste the new `EVENT_TO_STATUS` / `_UNMAPPED_EVENTS` /
`_MANUAL_REVIEW_EVENTS` entries into `scrapers/complot/api_scraper.py`.

### Step 2 — Re-run מורדות כרמל matcher (and the consolidated runner)

```powershell
$env:PYTHONPATH = 'c:\R_PROJECTS\Project_update_scraper'; $env:PYTHONUTF8 = '1'
& 'C:\Users\Rotem\AppData\Local\Programs\Python\Python313\python.exe' scripts\run_all_committees.py
```
This re-runs all 6 configured committees and rewrites `outputs/consolidated_report.xlsx` — check
whether `untracked`/`manual_review` counts for מורדות כרמל dropped now that more events are classified.

### Step 3 — Probe נתניה portal

```
https://vaadnet.netanyagis.co.il
```
View-source first; if JS-rendered, open Chrome DevTools Network tab and look for an API call
pattern matching Complot (`mgrqispi.dll`, `GetBakashotByNumber`) or Bartech
(`bartech-net.co.il`-style REST) before assuming a bespoke scraper is needed.

### Step 4 — Add remaining committees to `run_all_committees.py`

For Bat Yam / Holon / Kiryat Ata / Krayot / Ramat Gan: find or reconstruct each committee's exact
matcher call (check git history / old terminal output for the original `matcher.run()` args used),
write a `scripts/run_<name>_matcher.py` per the existing pattern, then add the same params to
`COMMITTEE_CONFIGS`.

---

## State of key files

| File | State |
|---|---|
| `scrapers/complot/api_scraper.py` | Unchanged this session pending colleague triage — 22/138 events classified |
| `transform/matcher.py` | `_make_row()` now returns a `city` field (from `proj['עיר']`) |
| `scripts/run_all_committees.py` | New — V2 consolidated runner, 6 committees configured |
| `scripts/run_mordot_carmel.py` | Unchanged since Session N (`min_year` param already added) |
| `outputs/mordot_carmel_fresh.csv` | Complete — 18,540 permits |
| `outputs/mordot_carmel_report.xlsx` | 10 status_advanced, 16 untracked, 2 manual_review — **stale, re-run after triage** |
| `outputs/consolidated_report.xlsx` | 293 rows / 6 committees, `city` column added |
| `docs/all_projects_08072026.xlsx` | Nationwide Madlan projects export — shared input across all configured committees |
| `docs/NEXT_STEPS.md` | Updated through Session Q |

---

## Uncommitted work reminder

**Nothing since Session K (`7cd0f59`) has been committed to git.** This handoff covers Sessions
L through Q. Before losing more context, consider committing (`git status` shows the accumulated
diff: `matcher.py`, `api_scraper.py`, `run_mordot_carmel.py`, `requirements.txt`, `NEXT_STEPS.md`,
plus new files `run_all_committees.py`, `fetch_projects.py`, `.env.example`,
`docs/all_projects_08072026.xlsx`, and 3 untracked session handoff files from 07-12/07-13).
