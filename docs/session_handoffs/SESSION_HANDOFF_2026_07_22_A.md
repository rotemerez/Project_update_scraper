# Session Handoff — 2026-07-22 A

**Date:** 2026-07-22
**Session:** W (follows Session V, 2026-07-20 B)
**Scope:** Colleague's manual Ashkelon review (`docs/אשקלון - יולי 2026.xlsx`) triggered a deep
investigation that found and fixed 3 real bugs (BUG-023, BUG-024, plus a related unit-minimum
gap), added 9 new construction types to the matcher, ran a targeted BUG-020 date-correction pass
across all 6 Bartech cities, and closed out the long-open Complot triage backlog.

---

## What was accomplished

### Ashkelon manual review — investigated, 2 real bugs found and fixed

Colleague reviewed the 41-row Ashkelon report: all 16 `status_advanced` rows correctly matched
and accurate; of 24 `untracked` rows, 22 correctly identified as irrelevant (municipal public
buildings, a hostel, sub-threshold private housing) and 2 correctly became new project pages.

Dug into *why* the 44 projects in his own separate "עיבוי נקודתי" filter list (56 total, his own
broader candidate list) weren't surfacing progress:
- **4 projects** genuinely have no Complot permit on their tracked גוש-חלקה — nothing to find.
- **~39 projects** had permits, but all correctly filtered (wrong type, no upgrade, below unit
  minimum, or correctly attributed by the matcher to a neighboring project sharing the same
  parcel).
- **1 project** (`מגרש_200_201_אבן_עזרא_אשקלון`) was a real miss at the time of his review — traced
  the matcher logic by hand, found no explanation beyond report-snapshot timing; it now correctly
  shows `status_advanced`.

That digging surfaced two real, fixed bugs:

- **BUG-023** — `_PUBLIC_USE_PATTERNS` only had the singular `מבנה ציבור`; Ashkelon/Holon use the
  plural `מבני ציבור` (693/47 permits respectively) — same class of gap as the double-yod
  construction-type bug. Also found (via a full request-type audit across every scraped city)
  that two Ashkelon high-rise labels (`בניה רוייה מעל 10 קומות`, `מבנה מגורים+מסחר מעל 10 ק`, up
  to 112 permits, 26-154 units per sample) were entirely invisible to `RELEVANT_TYPE_SUBSTRINGS`.
  Both fixed; Ashkelon report went from 43 → 57 rows, 10 previously-invisible projects newly
  correctly flagged.
- **7 more construction types** added after the colleague reviewed the resulting new rows and
  confirmed them: `מבנה מגורים משולב במסחר`, `מסחר ומגורים`, `הקמת בית מגורים חדש`,
  `בית מגורים  משותף + מסחר`, `בנין מגורים צמוד קרקע חדש`, `מגורים:צמוד קרקע`,
  `מבנה מגורים 2 יחידות דיור` (this last one: confirmed the label is a fixed municipal category,
  not a literal per-permit count — one sample scraped `unit_count=4` despite the "2" in the name).
  Found and fixed the matching gap in `_is_below_unit_minimum()` at the same time — it only
  checked `'צמודי קרקע'`, missing the singular `'צמוד קרקע'` used by two of the new types.
- **BUG-024** — colleague's review of the *new* rows (after the above fixes) flagged permit
  `20220897`: our matcher showed `טופס 4` but it was actually only a "systems commissioning"
  checkpoint (`הפקת טופס 4 להרצת מערכות`), not real building completion. Root cause:
  `EVENT_TO_STATUS` mapped that event straight to `'טופס 4'`; simply deleting the entry wouldn't
  have been enough since `_map_event()`'s substring-scan would still catch it via the more generic
  `'הפקת טופס 4'` key. Fixed with an explicit `'הרצת מערכות'` guard in `_map_event()`, checked
  before the substring loop. This also resolved a long-standing Complot triage question (see below).
  Colleague's other 2 flags (a "balcony enlargement" mislabeled as high-rise construction, and a
  "ביטול היתר ובנייה מחדש" permit that was actually a rocket-damage restoration, not new
  construction) were logged as known one-off noise, same tradeoff as other broad-substring types —
  not acted on given a sample size of one each.

### BUG-020 targeted re-enrichment — all 6 Bartech cities

Built `scripts/reenrich_bartech_dates.py` to re-fetch only the `היתר`/`טופס 4` detail pages (the
two statuses BUG-020's fix can override) for all 6 previously-affected Bartech cities, recovering
each permit's `definement_type` from the already-saved `request_category` label (= `PERMIT_TYPES`
label) instead of redoing the list-phase scrape. Ran in the background, paused mid-run for an
internet-connectivity gap (killed cleanly, no corruption — Holon and Krayot had already saved;
resumed the remaining 4 afterward). Final corrections: הולון 4,654/5,096 (91%), קריות 841/1,391
(60%), חדרה 204/2,260 (9%), הראל 322/479 (67%), זמורה 373/779 (48%), מיצפה אפק 1,301/1,641 (79%) —
**7,695 dates corrected total**. All 6 matchers re-run; row/flag counts barely moved (the bug only
ever corrected a date, never which milestone was reached). Pre-fix backups kept at
`outputs/{city}_fresh_pre_bug020.csv`.

### BUG-024 targeted re-check — Ashkelon + Mordot Carmel

Built `scripts/recheck_tofes4_bug024.py` — since this bug can only ever inflate a status upward
(never mask a real one), it was safe to re-check only the permits already at `scraped_status ==
'טופס 4'` in each report (28 total across the two cities with live reports). Results: Ashkelon 19
re-checked, 5 changed (4 downgraded `טופס 4` → real `היתר`, 1 date-only correction); Mordot Carmel
7 re-checked, 0 changed. Ashkelon matcher re-run: 57 → 53 rows, `status_advanced` 37 → 33.
קרית אתא/ישובי הברון/רמת גן have zero permits at `טופס 4` currently (separate known
scraper-staleness issues, unrelated). בת ים has 2 candidate rows, left untouched — its report is
already stale for unrelated reasons.

### Complot triage backlog — closed as final

Rotem confirmed `docs/Request Status's- Claude (1).docx` is the colleague's **final** mapping.
Verified all 121 entries in it already exactly match `scrapers/complot/api_scraper.py` — this was
the same export applied back in Session O (2026-07-15/16), not a newer one. No code change
needed. The 2 previously-uncertain events (`מסירת אישור הרצת מערכות`, `הפקת אישור הרצת מערכות`,
guessed "likely → היתר") are confirmed to stay unmapped, consistent with BUG-024's fix. Backlog
closed, not just paused — no more colleague classification is coming for this list.

---

## Open items carried forward

1. **בת ים** — scrape predates `detail_block_lot`/permit-regex fixes; needs a full rescrape.
2. **קרית אתא** — known missing `היתר` statuses (old scraper code); needs a full rescrape.
3. **רמת גן** — no report exists; last scrape was IP-blocked with empty detail fields, needs a
   full re-scrape from the office.
4. **תל אביב (GIS)** — 107-row report exists but our own due-diligence spot-check of sample rows
   was never done. Fastest likely win toward another "ready for review" city.
5. **ירושלים** — "no request-category field" assumption still unverified; the 20,693-row sweep
   still needs an actual matcher pass against tracked projects.
6. **Colleague's "+50 on helka" note** — still uninvestigated.
7. **`_extract_unit_count`** — doesn't parse Hebrew number-words, only digits.
8. **7 Harel permits** — flagged data-staleness, not yet re-checked.
9. **קצרין (Qatzrin)** — system still unidentified, no scraper started.
10. **נתניה** — confirmed Bartech via recon, never wired up (no runner scripts built).
11. **תל אביב יפו (legacy Selenium scraper)** — reCAPTCHA throttling, on hold pending a manual
    test of whether a blocked browser session's score recovers after a cooldown.
12. **V2 consolidated report** — only 6 of ~11 scraped committees wired into `COMMITTEE_CONFIGS`.
13. **Automatic backoffice writes** — intentionally deferred until the manual-review cycle is
    fully validated.
14. **Mavat/local-committee plan-search project discovery** — new item added this session,
    explicitly gated on finishing/honing everything above first.

---

## State of key files

| File | State |
|---|---|
| `transform/matcher.py` | `RELEVANT_TYPE_SUBSTRINGS` gained 9 entries; `_PUBLIC_USE_PATTERNS` gained `מבני ציבור`; `_is_below_unit_minimum()` now also checks `צמוד קרקע` (singular) |
| `scrapers/complot/api_scraper.py` | `_map_event()` now ignores any `הרצת מערכות` phrasing before the substring loop; `EVENT_TO_STATUS` bad entry removed; `_UNMAPPED_EVENTS` gained the explicit entry |
| `scripts/reenrich_bartech_dates.py` | New — targeted BUG-020 date re-enrichment, all 6 Bartech cities |
| `scripts/recheck_tofes4_bug024.py` | New — targeted BUG-024 re-check via `scrape_targeted()` |
| `outputs/ashkelon_report.xlsx` | Re-generated — 53 rows (33 status_advanced, 2 new_permit, 18 untracked) |
| `outputs/mordot_carmel_report.xlsx` | Unchanged by BUG-024 (0 permits affected); still 28 rows |
| `outputs/{holon,krayot,hadera,harel,zmora,mitzpe_afek}_report.xlsx` | All re-generated post-BUG-020 fix |
| `outputs/{6 bartech cities}_fresh_pre_bug020.csv` | Pre-fix backups, kept for diffing if needed |
| `docs/BUG_REFERENCE.md` | BUG-023, BUG-024 added, both with full root-cause + fix + re-check results |
| `docs/NEXT_STEPS.md` | Complot triage item marked CLOSED; Bartech rescrape follow-up marked DONE; Session W entry to be added |
| `docs/אשקלון - יולי 2026.xlsx` | Colleague's Ashkelon review — now committed for the record |
| `docs/Request Status's- Claude (1).docx` | Colleague's final Complot triage mapping — now committed for the record |

---

## Commit/push status

Committed and pushed at the end of this session — see `git log` for the actual commit hash and
message.
