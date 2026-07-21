# Session Handoff — 2026-07-20 B

**Date:** 2026-07-20 (session ran into the early hours of 2026-07-21 due to a long background job)
**Session:** V (follows Session U, 2026-07-20 A)
**Scope:** Jerusalem sweep manual-parcel-lookup gap closed (new API procs found + wired in + full
enrichment run); Ashkelon `permit_url_base` confirmed and wired in; two new construction types
added to `RELEVANT_TYPE_SUBSTRINGS` after due-diligence checks (Ashkelon `ביטול היתר ובנייה מחדש`,
Jerusalem `תוספת יח"ד באמצעות תוספת בניה`); Session T carryover item 2 explicitly reviewed and left
open.

---

## What was accomplished

### Jerusalem sweep: manual parcel lookup gap closed

Session U's sweep (`outputs/jerusalem_sweep.csv`, 20,693 תיק rows) was necessarily partial — no
gush/helka/address — because `fetchTikRushiData` (the proc `sweep_by_tik_number()` uses to walk
תיק numbers) has no such fields in its schema. This session found the fix:

- Grepped `outputs/debug_jerusalem_main.js` for proc IDs referenced in the bundle but not yet
  mapped in `scrapers/jerusalem/api_scraper.py`'s docstring. Found and live-tested three candidates
  against a known תיק (`2005/0001.00`):
  - **`getGushimContentData`** (proc 242700456, `{SystemId, TikNum}`) — returns real
    gush/miHelka/adHelka. Confirmed live.
  - **`getKtovetContentData`** (proc 242700455, `{systemId, tikNum}`) — returns street
    name/house number/neighborhood. Confirmed live.
  - `getTeurHabakashaContentData` (proc 242700447) — richer request description +
    requestor/architect names, used later in the session for due-diligence sampling (see below),
    not wired into the scraper itself.
- Added `JerusalemPermitsAPI.resolve_parcel(tik_num)` combining the two into
  `(block_lot, full_address)`. Wired into `sweep_by_tik_number()` — future sweeps mark
  `scrape_status='success'` when either resolves, instead of always `'partial'`.
- Built `scripts/enrich_jerusalem_sweep.py` (resumable via a checkpoint CSV every 200 rows) to
  enrich the *existing* 20,693-row sweep without re-running the whole sweep. Verified on a random
  8-row sample first (6/8 resolved, 2 genuinely unindexed) before committing to the full run.
- **Ran in the background, ~5.2 hours real time.** Result: **18,871/20,693 rows (91.2%) now have
  block_lot/full_address.** Remaining 1,822 are genuinely not indexed in Jerusalem's own
  gushim/ktovet system.
  - Hit a real ~2.5hr DNS-resolution outage mid-run (`jerbasicserviceapi.jerusalem.muni.il` failed
    to resolve — a local network/DNS issue, not a WAF/rate-limit block). The existing
    blocked-vs-error handling (`_with_retry()`, `[GIVE UP]` logging) worked exactly as designed:
    one תיק (`2019/0350.00`) was logged as inconclusive rather than silently counted as a miss, the
    process stayed alive throughout, and it resumed at the same ~80 rows/min pace once the network
    came back. No data corruption, no silent fabrication.
  - That one תיק was manually re-resolved after the run finished:
    `resolve_parcel('2019/0350.00')` → `block_lot='30173-116;30173-33'`,
    `full_address='רשב"ג 20'`. Row updated directly in `outputs/jerusalem_sweep.csv`, now fully
    resolved.
- **Not yet done**: the 1,822 genuinely-unresolved rows and the sweep file as a whole still need to
  actually be run through the matcher (`transform/matcher.py`) against tracked Jerusalem projects —
  this session only closed the parcel-resolution gap, it didn't run a matcher pass over the sweep
  data itself.

### Ashkelon: `permit_url_base` confirmed

Rotem provided a real permit URL:
`https://ashkelon.complot.co.il/newengine/Pages/request2.aspx#request/20160086` — the `20160086`
matches the exact `request_number` format already in `outputs/ashkelon_fresh.csv` (e.g.
`20110001`), confirming the pattern directly (no guessing needed).

- Wired `permit_url_base='https://ashkelon.complot.co.il/newengine/Pages/request2.aspx#request/'`
  into `config/committees.py`, `scripts/run_ashkelon_matcher.py`, and added a new entry to
  `scripts/run_all_committees.py`'s `COMMITTEE_CONFIGS` (Ashkelon was previously excluded from the
  consolidated report pending exactly this confirmation, per that file's own docstring rule).
- Re-ran the Ashkelon matcher — same match counts as before, `request_url` column now populated
  and spot-checked correct (e.g. `20160086` → the exact URL Rotem gave).

### Two new construction types added to `RELEVANT_TYPE_SUBSTRINGS`

Both followed the same pattern: pull real sample permits with links, confirm the construction
semantics with Rotem, only then edit the substring list — same due-diligence approach as the
New-City Checklist in CLAUDE.md.

1. **`ביטול היתר ובנייה מחדש`** (permit cancellation + rebuild) — flagged as a carried-forward item
   from Session U's Ashkelon double-yod check (6 occurrences, not a spelling variant of anything
   tracked, a genuinely distinct category). Pulled all 6 sample permits with links; Rotem confirmed
   it's effectively new construction. Added to `RELEVANT_TYPE_SUBSTRINGS`. Checked whether the
   accompanying unit-minimum filter (`_is_below_unit_minimum`) would still correctly filter
   single-family examples — found it only catches rows where the scraper's own `unit_count` field
   is populated (2/6 samples), not rows where `shimush_ikari` says `צמודי קרקע` but `unit_count` is
   blank (4/6 samples) — a **pre-existing gap**, not specific to this new type.
   **Rotem's explicit call: leave this gap alone** — a land-use tag alone doesn't tell us unit
   count, not enough information to safely filter on. Ashkelon matcher re-run: 42→43 report rows.

2. **`תוספת יח"ד באמצעות תוספת בניה`** (unit addition via building extension) — found while doing
   Session T's double-yod carryover check on Jerusalem's `sug_bakasha` field. The double-yod check
   itself came back **clean** (no missed spelling variant, comma-joined substring matching works
   fine) — but this phrase turned up 486 times across `jerusalem_fresh.csv` (192) and
   `jerusalem_sweep.csv` (294), 465 of which were **entirely invisible** to the matcher (not
   filtered — never even recognized as relevant in the first place). Pulled `mahutBakasha`
   (real free-text nature-of-request) via `getTeurHabakashaContentData` for 5 sample permits before
   deciding — one was a genuine 19-unit addition (`2013/0441.01`: "תוספת בניה של 6 קומות מגורים - 19
   יח\"ד"). Rotem confirmed it should be tracked. Added to `RELEVANT_TYPE_SUBSTRINGS`. Jerusalem
   matcher re-run: all 5 samples now appear in `jerusalem_matched_cache.json` (4,270 permits, up
   from 3,611); full report now 61 rows (52 status_advanced, 3 untracked, 6 new_permit) — **not a
   clean before/after of just this change**, since `docs/all_projects.xlsx` has also been refreshed
   multiple times since Session T.

### Session T carryover item 2 — explicitly left open

Jerusalem's "no request-category field" assumption (documented in
`scripts/run_jerusalem_matcher.py`'s docstring: the API has no separate administrative-stage field,
so `EXCLUDED_REQUEST_CATEGORIES` can't filter anything for this city — relies on an unverified
assumption that `jergisinfohub`'s רישוי בניה search never returns preliminary/info-request stages).
Explained to Rotem in full; **Rotem's explicit call: leave it open for now, keep tracking it** —
not investigated this session.

---

## Open items carried forward

1. **Jerusalem sweep matcher pass** — the 20,693-row sweep (now 91.2% parcel-resolved) still needs
   to actually be run through `transform/matcher.py` against tracked Jerusalem projects. Not done
   this session (only the parcel-resolution gap was closed).
2. **Jerusalem "no request-category field" assumption** — still open, explicitly deferred by Rotem.
   Needs a manual spot-check of report rows (especially `untracked`) to confirm the API genuinely
   never surfaces preliminary-stage requests.
3. **Colleague's "+50 on helka" note** — still open, untouched. "לפעמים הם מוסיפים 50 לפי החלקה"
   (sometimes 50 is added to the helka in their own project records) — not yet investigated at all.
4. **קצרין (Qatzrin) recon** — still open. System genuinely unidentified (not Complot, not
   Bartech) — first step is pure reconnaissance, no scraper code until the data-access mechanism is
   confirmed.
5. **Complot triage artifact** — still open, blocked on colleagues. 138 unique events, only 22
   classified as of the last check. Two flagged unclassified events:
   `מסירת אישור הרצת מערכות` (23x), `הפקת אישור הרצת מערכות` (26x) — both likely → היתר.
6. **`_is_below_unit_minimum` shimush_ikari gap** — noted this session, explicitly not fixed per
   Rotem's call (see Done above). Not a bug to silently revisit; would need a deliberate decision
   if it comes up again with more information available.
7. **Tel Aviv GIS report spot-check** — still not done (carried since Session U). 107-row report,
   especially address-matched (non-gush/helka) rows.
8. Everything else carried forward from Session T/U (double-yod check on Jerusalem — now done,
   see above; Kiryat Ata re-scrape, Mordot Carmel matcher re-run pending Complot triage, BUG-020
   rescrape gap, 7 Harel permits data-staleness flag, `_extract_unit_count` Hebrew-number-words
   gap) is still open — untouched this session.

---

## State of key files

| File | State |
|---|---|
| `scrapers/jerusalem/api_scraper.py` | New: `PROC_GUSHIM_CONTENT`, `PROC_KTOVET_CONTENT`, `SYSTEM_ID` constants; `_fetch_gushim()`, `_fetch_ktovet()`, `resolve_parcel()` methods; `sweep_by_tik_number()`/`_map_thin_row()` updated to use them |
| `scripts/enrich_jerusalem_sweep.py` | New — resumable enrichment runner for the existing sweep CSV |
| `outputs/jerusalem_sweep.csv` | Enriched in place — 18,871/20,693 rows now have block_lot/full_address (up from 0) |
| `outputs/jerusalem_report.xlsx` / `jerusalem_matched_cache.json` | Re-generated — 61-row report, 4,270-permit cache |
| `config/committees.py` | Ashkelon `permit_url_base` set |
| `scripts/run_ashkelon_matcher.py` | Ashkelon `permit_url_base` set |
| `scripts/run_all_committees.py` | Ashkelon added to `COMMITTEE_CONFIGS` |
| `outputs/ashkelon_report.xlsx` / `ashkelon_matched_cache.json` | Re-generated — 43-row report, 531-permit cache |
| `transform/matcher.py` | `RELEVANT_TYPE_SUBSTRINGS` gained 2 entries: `ביטול היתר ובנייה מחדש`, `תוספת יח"ד באמצעות תוספת בניה` |
| `docs/NEXT_STEPS.md` | Updated — Session V entry added, relevant Immediate-section items marked done |

---

## Commit/push status

Committed and pushed at the end of this session — see `git log` for the actual commit hash and
message (prepared alongside this handoff, same as Session U's own note).
