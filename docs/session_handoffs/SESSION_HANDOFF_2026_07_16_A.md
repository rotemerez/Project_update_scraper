# Session Handoff — 2026-07-16 A

**Date:** 2026-07-16
**Session:** S (follows Session R, covered in `SESSION_HANDOFF_2026_07_15_B.md`)
**Scope:** Migrash-based matching fix (Complot + Bartech); all 6 existing Bartech cities
rescraped + re-matched; Bartech certificate-date bug found + fixed; Tel Aviv reCAPTCHA
investigated and paused; Complot triage export merged; colleague Harel review analyzed

---

## What was accomplished

### BUG-019 — Migrash-based project matching fixed (Complot + extended to Bartech)

Colleague's review of Kiryat Ata (`docs/Kiryat_Ata_July_2026.xlsx`, comment columns) flagged wrong
project assignment whenever multiple projects share one גוש/חלקה — e.g. gush/helka `10514-11`
covers migrashim 179-238+ under `שכונת האבוקדו`, several without a BO project page yet.

Root cause: `transform/matcher.py`'s `_parse_migrash()` looked for the literal word `מגרש` via
regex, but the real `תבע+מגרש` project-file column format is `plan+number` (e.g. `תמל/1024+179`)
— the migrash tie-break had silently never fired on any real data. Separately,
`_pick_best_candidate()` accepted a single gush/helka candidate blindly with no migrash check at
all, even when the permit's migrash clearly didn't belong to that project.

Fixed: `_parse_migrash_set()` (renamed, returns a set — a project can span several migrashim),
`_pick_best_candidate()` now checks migrash before date/fuzzy-name tie-breaks for both single- and
multi-candidate cases, returns `None` ("no confident match") instead of guessing when the permit's
migrash doesn't fit any candidate with migrash data. `_make_row()` now includes `project_migrash` +
`permit_migrash` columns in every report for auditability (colleague's explicit request).

**Extended migrash scraping to Bartech** (`scrapers/bartech/api_scraper.py`) — previously only
Complot's scraper captured it. Confirmed via Rotem's live screenshots that Bartech's list-page
מקרקעין cell and detail-page גוש/חלקה table both expose מגרש. Added `_parse_migrash()`, wired into
the list-page row parser and `_parse_detail()`/`_enrich_with_details()`.

Verified end-to-end on Kiryat Ata (5 colleague-flagged permits no longer wrongly match) and on
Zmora — isolated the fix's *exact* effect by re-running the matcher with migrash-awareness
disabled, confirmed a 162-permit matched-cache drop is 100% attributable to the fix, and manually
spot-checked 8 dropped permits plus all 3 lost `status_advanced` rows individually. All were
genuine gush/helka conflicts; one (`20190936`) was an active false positive — misattributed to a
project with `db_status='היתר בניה'` when the correct migrash-matched project was already `אוכלס`
(fully complete). Full writeup: `docs/BUG_REFERENCE.md` BUG-019.

### All 6 existing Bartech cities rescraped + re-matched

הולון, קריות, חדרה, הראל, זמורה, מיצפה אפק — run via `Start-Process` from the office/current
machine (all Bartech portals are directly `requests`-accessible, no office-IP requirement unlike
Complot). Results (status_advanced / untracked / manual_review):

| City | Result | vs. prior baseline |
|---|---|---|
| הולון | 42 / 36 / 0 (cache 1364) | old baseline (194/3) predates the הסתיים-filter fix, not comparable |
| קריות | 36 / 14 / 0 (cache 1214) | no documented baseline |
| חדרה | 18 / 48 / 0 (cache 782) | no documented baseline |
| הראל | 5 / 33 / 0 (cache 155) | 5 / 32 (cache 166, Session J) — stable |
| זמורה | 4 / 70 / 0 (cache 101) | 7 / 70 (cache 264, Session J) — isolated & verified, see above |
| מיצפה אפק | 17 / 34 / 0 (cache 466) | 14 / 33 (cache 601, Session J) — real accumulated progress |

New runner script created: `scripts/run_krayot_matcher.py` (didn't exist before — Krayot had never
had a dedicated matcher runner).

### BUG-020 — Bartech wrong-track `permit_status_date`

Found via colleague's manual review of `docs/harel_report_15_07_2026.xlsx` (comment column): 2
permits had a status confirmed correct but a date that was wrong by 7 weeks / 1 day. Root cause: a
Bartech detail page can have multiple `סטטוס שלב` stage tables (e.g. permit-issuance track vs.
work-commencement track) that independently reach the same status rank at different dates — the
rank-based scan only updates on strictly-higher rank, so whichever table's matching-rank stage is
scanned last effectively wins when the "correct" stage (`הוצאת היתר בניה`) is deliberately
unmapped. Fixed with new `_parse_certificates()`, which reads the detail page's authoritative
`תעודות` (certificates) table and overrides the date for `היתר`/`טופס 4` when present. Verified
against both flagged permits' real detail-page HTML — both now produce the exact colleague-
confirmed date.

**Not yet re-run against the 6 Bartech cities above** — this fix landed after their rescrapes
already completed. Only affects dates, not status/matching correctness; lower priority.

### BUG-021 — Tel Aviv scraper crash on retry

`_query()`'s retry loop only classified bad *responses*, not exceptions raised *during* an
attempt. A `TimeoutException` from `_load_search_form()` mid-retry crashed the entire
`_smoke_test_tel_aviv.py` run. Fixed: wrapped the per-attempt body in `try/except
WebDriverException`, treated like any other retryable outcome, with a forced driver restart.

### Tel Aviv reCAPTCHA — investigated, then paused (Rotem's call)

After fixing BUG-021, re-ran the smoke test live: only 2/5 parcel queries and 0/9 scan queries
succeeded, everything else rejected even after 3 retries with backoff up to 3+ minutes. Rotem
manually tested the same UI by hand to isolate automation-detection as a cause — his first 3-4
searches worked, then the same wall hit (button silently does nothing).

Dispatched a precise investigation prompt to Claude Desktop (network/console instrumentation).
Result: **confirmed server-side** — a valid, freshly-minted reCAPTCHA Enterprise token is sent
with every request, and the Tel Aviv API gateway returns `400 Invalid assertion` every time,
silently swallowed by Angular's error handler (hence the "dead button" UX). BUT: the investigation
used a CDP-driven browser (same underlying protocol as our own scraper, minus its anti-detection
patches) that failed on the *very first* attempt and never recovered even after a 63-minute wait —
unlike Rotem's real browser and our own scraper, both of which succeeded on some early queries.
This means the 63-minute-wait-doesn't-help finding only proves a permanently-flagged-as-automated
session stays flagged; it does **not** answer whether a real session's score recovers after
backing off, which is the actual question that determines scraper feasibility.

**Decision: paused.** Full reasoning and the exact next diagnostic (Rotem waiting on his own
already-blocked tab and retrying, not a fresh automated session) are in
`docs/NEXT_STEPS.md` → Immediate #3. No scraper code changes until that's answered.

### Complot triage export merged

Colleague's מורדות כרמל event classification (fresh export, 2026-07-15/16) merged into
`scrapers/complot/api_scraper.py`: 2 new `EVENT_TO_STATUS` entries (`הפקת טופס 4`, `מסירת טופס 4`
→ `'טופס 4'`), 102 new `_UNMAPPED_EVENTS`, 13 new `_MANUAL_REVIEW_EVENTS`. Checked programmatically
for zero duplicates/conflicts against existing entries before merging.

---

## Open items carried forward

- **Tel Aviv — paused**, see above. Do not resume without the real-session wait-and-retry result.
- **BUG-020 rescrape gap** — the 6 Bartech cities rescraped this session predate the certificate-
  date fix; consider re-running just the detail-fetch phase rather than a full rescrape.
- **Mordot Carmel matcher not yet re-run** with the new Complot triage classifications — still
  only ~22/138 events were classified as of the original run; check with colleague whether triage
  is now complete.
- **Kiryat Ata not yet re-scraped** with the migrash fix (it's Complot, needs office IP per
  Session H's WAF note) — `outputs/kiryat_ata_report.xlsx` is still pre-fix.
- **7 Harel permits**: colleague flagged "existing project has old lot, request has new lot" for
  `הרימון_קרית_יערים`/`החוצבים_5_מבשרת_ציון` — a projects-file data-staleness issue (project's own
  גוש/חלקה needs updating), not a code bug. Flag to whoever maintains the projects export.
- **`_extract_unit_count` gap** (`transform/matcher.py`) — doesn't parse Hebrew number words
  (`שתי` = two, etc.), only digits. Let one permit (`20250630`) slip through
  `_is_below_unit_minimum` uncaught. Narrow, safe enhancement, not yet implemented.
- Everything else carried forward from `SESSION_HANDOFF_2026_07_15_B.md` (Jerusalem/Katzrin recon,
  Netanya wiring, Tel Aviv second site) is still open — untouched this session.

---

## State of key files

| File | State |
|---|---|
| `transform/matcher.py` | BUG-019 fix — migrash-based disambiguation, `project_migrash`/`permit_migrash` columns |
| `scrapers/bartech/api_scraper.py` | migrash scraping added; BUG-020 fix (`_parse_certificates`) |
| `scrapers/complot/api_scraper.py` | Complot triage export merged (event classifications) |
| `scrapers/tel_aviv/scraper.py` | BUG-021 fix (exception handling in `_query()` retry loop) |
| `scripts/run_krayot_matcher.py` | New — didn't exist before this session |
| `outputs/{holon,krayot,hadera,harel,zmora,mitzpe_afek}_fresh.csv` | Rescraped this session, now include `migrash` |
| `outputs/{holon,krayot,hadera,harel,zmora,mitzpe_afek}_report.xlsx` | Re-matched this session with the fix |
| `docs/BUG_REFERENCE.md` | BUG-019, BUG-020, BUG-021 added |
| `docs/NEXT_STEPS.md` | Updated through Session S |
| `docs/Kiryat_Ata_July_2026.xlsx`, `docs/harel_report_15_07_2026.xlsx` | Colleague review files with comment columns — reference material, now tracked in git |

---

## Commit/push status

Everything from this session was committed and pushed at the end — no uncommitted-work reminder
needed this time.
