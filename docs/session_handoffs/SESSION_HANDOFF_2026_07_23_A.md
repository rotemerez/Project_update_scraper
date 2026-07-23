# Session Handoff — 2026-07-23 A

**Date:** 2026-07-23
**Session:** X (follows Session W, 2026-07-22)
**Scope:** Two starting tasks (Jerusalem sweep matcher run, Ramat Gan rescrape+match) snowballed
into a deep matcher-correctness investigation, driven by colleague review of both the new Ramat
Gan report and Mordot Carmel. Found and fixed 3 real matcher bugs (BUG-025, BUG-026, BUG-027).
Both reports sent to colleague at end of session. Rehovot (רחובות) queued as next new city.

---

## What was accomplished

### Jerusalem sweep matcher — first run, then fixed a broken recency filter

Ran the matcher against the 20,693-row tik-number sweep for the first time (previously only
enriched with block_lot/address, never matched — new script `scripts/run_jerusalem_sweep_matcher.py`).
Initial unfiltered result: 3,161 rows (7 `new_permit`, 3,154 `untracked`) — a review-volume
complaint led to investigating why. Root cause: the sweep's source endpoint
(`fetchTikRushiData`) has no request/filing-date field at all — confirmed directly via a live
call to the raw API (full schema: `ID/tik_num/status_code/teurStatus/taarih_status/
sugbakasha_code/teurSugbakasha/mahut_bakasha`). With `request_date` blank on every row, the
matcher's 365-day recency filter (`_is_recent`, which fails open on missing dates by design) was
a complete no-op for the entire sweep, letting permits back to 2005 through unfiltered — 97% of
the 3,154 untracked rows hadn't had a status update in over 3 years.

Fix: a sweep-specific pre-filter in the runner script (not `transform/matcher.py`, so no other
city is affected) using `permit_status_date` — the one real date field this endpoint does
provide — with a 3-year cutoff (Rotem's call). Re-run: **104 rows** (4 `new_permit`, 100
`untracked`) — a 96.7% cut. Verified the 3 excluded `new_permit` permits were all genuinely
stale (last status update 2006 or early 2023) via a targeted re-check against only the
`טרום בקשה`-status projects (193 of them, vs. re-running the full expensive match).

### Ramat Gan — rescrape + first-ever matcher run, then deep manual_review investigation

Previous scrape was IP-blocked and stale with no report ever generated. Full rescrape:
4,923/4,923 permits, 0 errors, 0 duplicates. New `scripts/run_ramat_gan_matcher.py` (first
matcher run for this city): 91 rows — 5 `new_permit`, 1 `status_advanced`, 0 `untracked`, **85
`manual_review`**.

The 85 count is a real outlier — checked every other live Complot/Bartech report and none has
more than 2 `manual_review` rows. Traced the cause: 100% תמ"א 38 permits (70
`תמ"א 38 הריסה ובניה` + 15 `תוספת לפי תמ"א 38`) from 2011-2016, each hitting one of two
appeals-committee events (`החלטת ועדת ערר`, `עיכוב היתר ע"י ועדת ערר`) the matcher treats as
inherently ambiguous (outcome unknown, per the scraper's own docstring). Status-rank analysis of
the 85 (using `_status_rank`/`DB_STATUS_NORM`, same comparison the matcher itself uses):
- 75 (88%) — status unchanged from what's already tracked; stuck there purely because an old,
  presumably long-resolved appeals event sits in the permit's history
- 7 — scraped status shows *less* progress than what's tracked (`behind`); traced one
  (`2011379`) in detail via a live call to the Complot detail endpoint and found its own event
  history includes an unmapped `סגירת בקשה !` (request closed) event — likely superseded by a
  different, later request not captured under this same parcel, not a scraper bug
- 3 — genuine upgrades (`טרום בקשה` → `בקשה להיתר`) masked by the manual_review flag — fixed via
  BUG-027 below

### BUG-025 — migrash leading-zero normalization (found via colleague's Mordot Carmel review)

Colleague's review of `docs/מורדות הכרמל - יולי 2026.xlsx` flagged permit `20212109` (project
`Roth ברמות יצחק, נשר`) as "the scraper missed this Form 4." Traced every filter/match stage in
`transform/matcher.py`'s `run()` by hand for this exact permit — everything passed cleanly until
`_pick_best_candidate`'s migrash check: the project's BO record has migrash `'1'`, the permit
scraped migrash `'001'` — same sub-plot, different zero-padding, but compared as raw strings so
the "no confident match" safeguard from BUG-019 (Session S) fired and silently dropped a
completely genuine match. Fixed with a new `_norm_migrash()` helper (strips leading zeros),
applied on both sides of the comparison. Also confirmed the colleague's second flagged permit
(`20210854`/`עמק הכרמל RESERVE`) is a genuine tracked-parcel data gap (its actual block_lot is
simply absent from the project's גוש-חלקה list) — not a code bug, needs a manual data correction.

### BUG-026 — public-use pattern gaps + new municipality-requestor check

Same colleague review flagged 5 more permits as irrelevant that the matcher had surfaced anyway.
Traced each to a specific field-level gap: `בית אבות` (nursing home), `מתקנים הנדסיים`
(engineering installations, e.g. a water-pump booster), and `חדר טרנספורמציה` (transformer room,
distinct from the already-tracked `תחנת טרנספורמציה` station) were all missing from
`_PUBLIC_USE_PATTERNS` — added, confirmed by Rotem. Also added a new requestor-based check: a
permit filed by a municipality/local council (`עיריית`/`עירייה`, or the word pair
`מועצה`+`מקומית` checked independently so the Hebrew definite article inserted between them
still matches) is treated as public-use infrastructure **unless the permit cites an actual
unit_count** — Rotem's explicit exception, since a local council could legitimately be building
public housing.

Left 3 other flagged cases unfixed on Rotem's explicit call, no reliable data signal exists:
- 2 private-individual landed-housing requests with blank `unit_count` — no text field states a
  count, and "requestor looks like an individual" isn't a safe enough proxy
- 1 office-building case ("not for rent or sale") — a blanket `משרדים` exclusion risks wrongly
  dropping legitimate tracked mixed-use projects
- A 4th colleague-flagged `בית אבות` case (`20260639`) where the actual scraped data
  (`shimush_ikari='מגורים , מסחרי ומשרדים'`, blank `bakasha_description`) has zero nursing-home
  signal anywhere — confirmed by inspecting every field; genuinely unconfirmable from our data

### BUG-027 — manual_review no longer suppresses genuine upgrades

The 3 genuine Ramat Gan upgrades found above needed a matcher fix, not just identification: the
manual_review branch applied unconditionally whenever `manual_review_event` was set, with no
check for whether the permit had also genuinely advanced past the tracked project's status.
First attempt (checking upgrade-eligibility before the manual_review flag) had no effect — all 3
still failed `_scraped_date_is_actionable` (BUG-009's fix), which requires a scraped date to be
recent *only* when the project has no existing milestone dates — true for `טרום בקשה` projects,
and these permits' status dates are from 2012-2013. Relaxed that check specifically for
manual_review-flagged permits (skip the "must be recent" fallback, keep the "must be after any
existing project date" rule) since the ambiguous event that gets a permit stuck there is
inherently old by nature — that's not evidence the resulting rank upgrade is fake.
BUG-009's protection is completely unchanged for every other (non-manual_review) permit.
Re-verified: Ramat Gan report stayed at 91 rows (pure reclassification) — `status_advanced` 1 →
4, `manual_review` 85 → 82, confirmed the exact 3 expected permits moved.

### Reports sent to colleague

Both **מורדות כרמל** (`outputs/mordot_carmel_report.xlsx`, 24 rows, current with BUG-025+026) and
**רמת גן** (`outputs/ramat_gan_report.xlsx`, 91 rows, current with BUG-025+026+027) sent to
colleague for review at the end of this session.

---

## Open items carried forward

1. **רחובות (Rehovot) — next city to scrape and match.** Not yet started; explicitly queued by
   Rotem for next session. Confirm system (Complot/Bartech/proprietary) first.
2. **Re-run remaining Complot/Bartech matchers with today's 3 fixes** — אשקלון, the 6 Bartech
   cities (הולון/קריות/חדרה/הראל/זמורה/מיצפה אפק), ירושלים (main + sweep), ישובי הברון. None of
   these have been re-run since BUG-025/026/027 landed; confirmed all have real migrash/requestor
   data so none are structurally immune. See `docs/NEXT_STEPS.md` item #0b for detail.
3. **בת ים** — scrape predates `detail_block_lot`/permit-regex fixes; needs a full rescrape.
4. **קרית אתא** — known missing `היתר` statuses (old scraper code); needs a full rescrape.
5. **תל אביב (GIS)** — 107-row report exists but was never spot-checked for correctness at all.
6. **7 Ramat Gan "behind" manual_review rows** (scraped status shows less progress than tracked)
   — 1 traced in detail this session (likely a superseded/closed request, real approval elsewhere
   under a different request number); the other 6 not yet individually checked.
7. **BUG-025's confirmed data gap**: `עמק הכרמל RESERVE, נשר` project's tracked גוש-חלקה list is
   missing parcel `11236-24` (a likely off-by-one from the tracked `11236-25`) — needs a manual
   correction to the projects file, not a code fix.
8. **Colleague's "+50 on helka" note** — still uninvestigated (carried from earlier sessions).
9. **`_extract_unit_count`** — doesn't parse Hebrew number-words, only digits (carried forward).
10. **קצרין (Qatzrin)** — system still unidentified, no scraper started (carried forward).
11. **נתניה** — confirmed Bartech via recon, never wired up (carried forward).
12. **תל אביב יפו (legacy Selenium scraper)** — on hold pending reCAPTCHA cooldown test (carried
    forward).
13. **V2 consolidated report** — only 6 of ~11 scraped committees wired into `COMMITTEE_CONFIGS`
    (carried forward).
14. **Automatic backoffice writes** — intentionally deferred until manual-review cycle is fully
    validated (carried forward).
15. **Mavat/local-committee plan-search project discovery** — gated on finishing everything above
    (carried forward).

---

## State of key files

| File | State |
|---|---|
| `transform/matcher.py` | BUG-025 (`_norm_migrash()`, applied in `_parse_migrash_set` + `_pick_best_candidate`), BUG-026 (`_PUBLIC_USE_PATTERNS` +3 entries, new `_PUBLIC_BODY_REQUESTOR_PATTERNS`/`_PUBLIC_BODY_REQUESTOR_WORD_PAIRS`, `_is_public_use()` requestor check), BUG-027 (manual_review branch restructured — computes `is_new_permit_case`/`is_upgrade_case` before applying the flag; date-actionability check relaxed only for manual_review-flagged permits) |
| `scripts/run_jerusalem_sweep_matcher.py` | New — matcher runner for the sweep, includes the 3-year `permit_status_date` pre-filter |
| `scripts/run_ramat_gan_matcher.py` | New — first matcher runner for Ramat Gan |
| `outputs/jerusalem_sweep_recent.csv` | New — filtered sweep output (4,284 of 20,693 rows), intermediate file feeding the matcher |
| `outputs/jerusalem_sweep_report.xlsx` | 104 rows (4 new_permit, 100 untracked) — current |
| `outputs/ramat_gan_fresh.csv` | Freshly rescraped, 4,923/4,923 permits, 0 errors |
| `outputs/ramat_gan_report.xlsx` | 91 rows (5 new_permit, 4 status_advanced, 0 untracked, 82 manual_review) — current with all 3 fixes; sent to colleague |
| `outputs/mordot_carmel_report.xlsx` | 24 rows (9 status_advanced, 13 untracked, 2 manual_review) — current with BUG-025+026; sent to colleague |
| `docs/מורדות הכרמל - יולי 2026.xlsx` | Colleague's Mordot Carmel review — committed for the record |
| `docs/BUG_REFERENCE.md` | BUG-025, BUG-026, BUG-027 added, each with full root-cause + fix + verification |
| `docs/NEXT_STEPS.md` | Session X entry added; review-pending-reports table updated for מורדות כרמל + רמת גן; Rehovot + re-run-remaining-cities added as Immediate items |

---

## Commit/push status

Committed and pushed at the end of this session — see `git log` for the actual commit hash and
message.
