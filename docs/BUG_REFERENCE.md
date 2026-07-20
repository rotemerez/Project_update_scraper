# Bug Reference — Project Update Scraper

**Last Updated:** 2026-07-20

---

## BUG-022 — Jerusalem scraper: blocked/rate-limited requests silently counted as "not found"

**Severity:** Critical — a WAF rate-limit block corrupted real scrape output with no error surfaced
**Fixed in:** Session U (2026-07-20)
**File:** `scrapers/jerusalem/api_scraper.py` → `_fetch_rishui_bniya()`, `_fetch_pikuah_stages()`,
`_fetch_tik_rushi()`

### Root cause

All three fetch methods caught any request exception (network error, non-2xx HTTP status,
including a WAF `403 Forbidden`) and simply returned an empty list — indistinguishable from a
genuine "no permits at this parcel/תיק" result. `sweep_by_tik_number()`'s miss-streak counter
had no way to tell the difference, so a block was silently absorbed as hundreds of consecutive
real misses.

This was triggered live: an accidental duplicate scrape process (a stale `Start-Process` launch
that an earlier flawed liveness check had wrongly reported as exited) ran concurrently with the
real sweep for about an hour, doubling request volume against `jerbasicserviceapi.jerusalem.muni.il`
and tripping a rate-limit block — 492 consecutive `403 Forbidden` responses, all silently logged
as "not found."

### What broke

Two years of the sweep (2008, 2009) reported suspiciously low/plausible-looking counts that were
actually fabricated by the bug — every request in that window was blocked, not genuinely empty,
but the miss-streak logic ended each year's sweep early on fake "nothing here" data exactly as if
it had reached the real end of that year's תיקים.

### Fix

All three fetch methods now return a 3-way `('ok' | 'blocked' | 'error', data)` outcome — `'ok'`
means a genuine backend response (data may legitimately be empty); `'blocked'`/`'error'` means the
request itself failed and says nothing about whether real data exists. A new `_with_retry()`
helper retries blocked/error outcomes with backoff (up to 3 tries) and logs `[GIVE UP]` +
a final inconclusive-count summary if still unresolved — these numbers/תיקים are explicitly
flagged as needing a manual re-check rather than being silently treated as confirmed misses.
Same pattern already in use in `scrapers/tel_aviv/scraper.py`'s `_query()` (see BUG-021's
neighboring context) — ported over rather than reinvented.

### Prevention

Any scraper with a retry-driven "stop after N consecutive misses" loop must classify a failed
request as inconclusive, never as a miss. A caught exception returning an empty result looks
identical to a genuine empty result to every caller downstream — the distinction has to be made
at the point of the request, not inferred later.

---

## BUG-021 — Tel Aviv scraper: uncaught Selenium exception mid-retry crashed the entire scrape

**Severity:** High — one transient page-load timeout killed a multi-hour unattended run
**Fixed in:** Session S (2026-07-16)
**File:** `scrapers/tel_aviv/scraper.py` → `_query()`

### Root cause

`_query()`'s retry loop only classified bad *responses* (`'blocked'`/`'error'` from
`_parse_response()`) — it had no guard around Selenium exceptions raised *while attempting* a
query. A `TimeoutException` from `_load_search_form()` on a retry attempt (confirmed live: the
form's `entrance` field never appeared within 15s after a "חיפוש חדש" transition) propagated
uncaught all the way up through `scrape_parcels()` and killed the whole script — including every
query still queued after it.

### Fix

Wrapped the per-attempt body (`_load_search_form()` → `_fill_field()` → `_submit_and_capture()`)
in `try/except WebDriverException`, treating any Selenium-level exception the same as a
`'blocked'`/`'error'` response outcome — logged, backed off, retried. The driver is also
force-restarted on this path (not just the periodic `restart_every` cadence) since an exception
mid-fill can leave the page in a state the next attempt can't recover from.

### When adding a scraper behind bot-defense (CAPTCHA, WAF, rate limiting)

See BUG-018's note below — the same principle extends to the *mechanism* of retrying, not just
classifying responses: any retry loop driving a real browser must assume the browser itself can
throw mid-attempt (stale element, navigation timeout, crashed renderer), and must catch at the
retry-loop level, not just at the response-parsing level. A retry loop that can itself be killed
by the thing it's retrying against defeats its own purpose.

---

## BUG-020 — Bartech scraper: permit_status_date pulled from the wrong track when multiple stage tables share the same status rank

**Severity:** Medium — correct status, wrong milestone date on matched permits (found via
colleague manual review of `harel_report.xlsx`, 2026-07-15/16)
**Fixed in:** Session S (2026-07-16)
**File:** `scrapers/bartech/api_scraper.py` → `_parse_detail()`, new `_parse_certificates()`

### Root cause

A Bartech detail page can have *multiple* `סטטוס שלב` stage tables — e.g. one for the permit-issuance
track (מסלול רישוי) and a separate one for the work-commencement track (צו התחלת עבודה) — and both
can independently reach the same status rank (`היתר`) at different dates. `_parse_detail()`'s
rank-based scan (`if rank > best_rank`) only updates on a *strictly higher* rank, so whichever
table's matching-rank stage is scanned last effectively wins if the correct one was deliberately
left in `_UNMAPPED_STAGES` (e.g. `'הוצאת היתר בניה'` — "permit issued but may not be signed
yet") and a same-rank stage from a different track (`'מתן צו התחלת עבודה'`) is the only one that
actually maps to a status. Confirmed live on two permits: `20240647` reported `היתר` dated
`12/05/2026` (from the work-order track) when the certificate's real issuance date was
`23/03/2026`; `20190029` reported `טופס 4` dated `20/11/2025` instead of the certificate's
`19/11/2025` (off by one day, same root cause).

### Fix

The detail page's `תעודות` (certificates) table — headers `['סוג תעודה', 'מספר', 'תאריך הפקה']`
— is the authoritative record for exactly the two milestones it lists (`היתר`, `טופס 4`/`תעודת
גמר`). New `_parse_certificates()` parses it into `{status: date}`; `_parse_detail()` still uses
the existing rank-based stage scan to determine *which* status was reached (the certificates table
says nothing about `בקשה להיתר`/`היתר בתנאים`), but overrides the *date* with the certificate
table's value whenever the reached status has one.

### General lesson

When a status can be reached via more than one table/track on a detail page, don't assume "highest
rank wins, first-seen date sticks" — check whether the page has a dedicated authoritative-date
table before trusting whatever stage table happens to be scanned first.

---

## BUG-019 — Matcher: migrash tie-break silently never fired, and single-candidate matches were accepted without checking migrash at all

**Severity:** High — wrong project assignment on any gush/helka shared by multiple projects
(found via colleague manual review of `Kiryat_Ata_July_2026.xlsx`, 2026-07-15/16)
**Fixed in:** Session S (2026-07-16)
**File:** `transform/matcher.py` → `_parse_migrash_set()` (was `_parse_migrash()`),
`_pick_best_candidate()`; `scrapers/bartech/api_scraper.py` (migrash scraping added)

### Root cause

Two compounding bugs:
1. `_parse_migrash()` looked for the literal word `מגרש` via regex (`מגרש\s*(\d+)`), but the real
   `תבע+מגרש` project-file column format is `plan+number` (e.g. `תמל/1024+179`, comma-separated
   for multi-lot projects) — the word never appears, so the migrash tie-break was a no-op on every
   real project row.
2. Even with correct parsing, a permit whose gush/helka matched only **one** existing BO project
   was accepted blindly, with no check that the permit's migrash actually belongs to that
   project — a gush/helka can cover many migrashim, each its own project, and new ones get added
   over time, so "only one candidate exists right now" isn't proof the permit belongs to it.
3. Bartech's scraper never captured a `migrash` field at all (only Complot's did), so the fix
   above had no live data to work with on any Bartech city until this session.

### Fix

`_parse_migrash_set()` correctly parses the `plan+number` format (returns a set, since one project
row can list several migrashim). `_pick_best_candidate()` now checks migrash before date/fuzzy-name
tie-breaks for both single- and multi-candidate cases, and returns `None` ("no confident match")
whenever the permit's migrash doesn't belong to any candidate's migrash set that has migrash data
to compare against — instead of silently guessing. `_make_row()` now includes `project_migrash` +
`permit_migrash` columns so this is auditable in every report. Migrash scraping was added to
`scrapers/bartech/api_scraper.py` (list-page `Label12` tooltip + detail-page `מספר מגרש` column),
mirroring the existing `block_lot`/`detail_block_lot` pattern.

### Verified

Kiryat Ata: 5 permits previously misattributed to `מגרש_179_183_האבוקדו`/`מגרש_202_204_האבוקדו`
no longer wrongly match. Zmora: isolated the fix's exact effect by re-running the matcher with
migrash-awareness disabled — confirmed a 162-permit drop in the matched cache is entirely
attributable to the fix, and spot-checked 8 of them plus the 3 lost `status_advanced` rows
individually; all were genuine gush/helka conflicts (one, `20190936`, was actively being
misattributed to a wrong project with `db_status='היתר בניה'` when the correct migrash-matched
project was already `אוכלס`/fully complete — a real false positive, not just a missed match).

### When multiple candidates share a join key but the data source is incomplete

Don't treat "there's only one plausible match right now" as confirmation — if the join key
(gush/helka here) is known to be coarser than the real entity (migrash), a missing competing
candidate can mean "doesn't exist in our data yet," not "this is the only one." Prefer declining
the match over guessing when a finer-grained signal (migrash) is available but doesn't corroborate.

---

## BUG-018 — Tel Aviv scraper: reCAPTCHA gateway rejection mis-counted as a genuine "not found"

**Severity:** High — would silently truncate `scan_license_range()` at a false ceiling  
**Fixed in:** Session R (2026-07-15)  
**File:** `scrapers/tel_aviv/scraper.py` → `_parse_response()`, `_query()`

### Root cause

A `400 Invalid assertion` / `400 Missing assertion` response (the reCAPTCHA Enterprise gateway
rejecting the request) was parsed identically to a genuine `200` response with an empty results
array. Both fed into the scan loop's `consecutive_misses` counter, so a run of gateway rejections
(confirmed live: adaptive rate-limiting kicked in after only 1-2 successful queries in a tight
loop) looked exactly like a run of real "no permit at this number" results — the scan would stop
at a false ceiling, silently under-reporting real data, not because the numbers didn't exist but
because the requests were never actually checked.

### Fix

`_parse_response()` now returns a 3-way outcome — `'ok'` (genuine response, `records` may
legitimately be empty), `'blocked'` (gateway rejection), or `'error'` (anything else malformed).
`_query()` retries `'blocked'`/`'error'` outcomes with scaling backoff (30-75s × attempt, up to 3
tries) and only ever returns `'ok'` (real data) or gives up with an explicit `[GIVE UP]` log line
— callers must never treat a give-up as a confirmed miss.

### When adding a scraper behind bot-defense (CAPTCHA, WAF, rate limiting)

Any query that can fail for a reason unrelated to "does this record exist" (auth/gateway
rejection, transient 5xx, timeout) must be classified separately from a genuine empty result.
Feeding a rejection into the same miss-counter used for real "not found" detection produces a
false stopping point that looks like clean success.

---

## BUG-017 — Tel Aviv scraper: filling form fields before Angular's reactive form finished initializing

**Severity:** High — every query silently searched with default `0` values instead of the real input  
**Fixed in:** Session R (2026-07-15), caught by Rotem watching the live non-headless browser  
**File:** `scrapers/tel_aviv/scraper.py` → `_load_search_form()`, `_fill_field()`

### Root cause

Waiting for a form field's DOM *presence* (`EC.presence_of_element_located`) is not the same as
Angular's reactive `FormGroup` having finished wiring/default-populating that field. Filling
immediately after presence either landed before the binding existed or was silently overwritten
back to `"0"` by Angular's own init logic shortly after — confirmed by direct visual observation
of the field staying at `"0"` despite `send_keys()` appearing to succeed with no exception.

### Fix

Added a settle delay after the presence wait in `_load_search_form()`, and made `_fill_field()`
verify the field's actual value after filling, falling back to a direct `.value` assignment +
manual `input`/`change` event dispatch (what Angular's `matInput` listens on) if `send_keys()`
didn't stick — then raising loudly if it still doesn't take, rather than silently submitting a
wrong value.

### When automating a form on a reactive framework (Angular/React/Vue)

Element presence in the DOM is not a proxy for "the framework has finished binding this element."
Always verify the field's value after filling, not just that the fill call didn't throw —
especially right after a navigation/route change.

---

## BUG-016 — `בנייה חדשה` (double-yod) not matched by `בניה חדשה` (single-yod) substring

**Severity:** Medium — legitimate new-construction upgrades silently dropped for cities using the double-yod spelling  
**Fixed in:** Session E (2026-07-08, after Hadera run)  
**File:** `transform/matcher.py` → `RELEVANT_TYPE_SUBSTRINGS`

### Root cause

Hebrew has two accepted spellings of the word "building": `בניה` (single-yod, traditional) and
`בנייה` (double-yod, academically preferred). Different municipalities use different spellings in
their Bartech portals. Hadera uses `בנייה חדשה` (311 of 902 new-construction permits), while
the matcher only checked for `בניה חדשה`. The mismatch caused all double-yod permits to fail
`_is_relevant_type()` silently, dropping them from all report branches.

### Fix

Added both variants to `RELEVANT_TYPE_SUBSTRINGS`:
```python
'בניה חדשה',
'בנייה חדשה',     # alternate spelling (double-yod) seen in Hadera Bartech
'הריסה ובניה',
'הריסה ובנייה',   # double-yod variant
```

### When adding a new city

**Always check** the `request_type` value distribution in the fresh CSV before running the matcher
(`df['request_type'].value_counts()`). Look for double-yod variants of any construction type
substring. Add the variant if found — do not assume single-yod is universal.

---

## BUG-015 — `unit_count` float parsing silently failed; sub-minimum permits passed through

**Severity:** Medium — permits with 1–2 units were not filtered by `_is_below_unit_minimum`  
**Fixed in:** Session X (2026-07-08)  
**File:** `transform/matcher.py` → `_is_below_unit_minimum()`

### Root cause

`permits_df` is loaded via `pd.read_csv` without `dtype=str`. Because the `unit_count` column
contains NaN values, pandas infers it as `float64`. A value of `2` becomes `np.float64(2.0)`.
`_clean()` converts it to the string `'2.0'`. `int('2.0')` raises `ValueError`, so `units`
falls back to `None`, and the function returns `False` (let through). This silently bypassed
the unit minimum check for all permits with integer unit counts in the CSV.

### Fix

Changed `int(raw_count)` → `int(float(raw_count))`. `float()` handles both `'2'` and `'2.0'`;
the outer `int()` truncates to an integer. Affected 5 `untracked` rows in the Kiryat Ata report
(all sub-minimum בניה חדשה permits with 1–2 units).

---

## BUG-014 — `_is_public_use` not checked in `status_advanced` and `new_permit` branches

**Severity:** Medium — public-use buildings (מבנה ציבור כללי etc.) surfaced as `status_advanced`  
**Fixed in:** Session X (2026-07-08)  
**File:** `transform/matcher.py` → `run()` matched branch

### Root cause

`_is_public_use()` was only called in the `manual_review`, `untracked` (unmatched), and
`הסתיים`/`אוכלס` branches. The `status_advanced` and `new_permit` branches had no such guard.
A permit for a public building (e.g. `שימוש עיקרי = מבנה ציבור כללי`) that matched a project
and showed a status upgrade would be emitted as `status_advanced`.

### Fix

Added `and not _is_public_use(permit)` to both the `status_advanced` and `new_permit` conditions.
Removed 7 rows from the Kiryat Ata report (3 `status_advanced`, 4 others caught by new shimush_ikari
patterns added in the same session).

---

## BUG-013 — `הוצאת היתר בניה` manual_review flag redundant when `תאריך הפקת היתר` confirms היתר

**Severity:** Low — 84 rows flagged for manual review that were already confirmed as `היתר`  
**Fixed in:** Session X (2026-07-08)  
**File:** `transform/matcher.py` → `run()` matched + unmatched branches

### Root cause

`הוצאת היתר בניה` was placed in `_MANUAL_REVIEW_EVENTS` because the event alone does not
confirm that the permit was signed. However, the scraper also extracts `תאריך הפקת היתר` from
the detail page header and sets `permit_status = 'היתר'` when it is present. When both exist,
the manual_review flag was still raised — even though the `תאריך הפקת היתר` field had already
provided a reliable confirmation. Data confirmed: 1,550/1,561 Kiryat Ata permits with this event
also have `permit_status = 'היתר'` (set by the header field).

### Fix

In both the matched and unmatched branches, skip the manual_review flag when
`manual_review_event == 'הוצאת היתר בניה'` and `permit_status == 'היתר'`. Let the permit fall
through to normal `status_advanced`/`untracked` logic. The 11 permits where `permit_status != 'היתר'`
(no `תאריך הפקת היתר` on the page) still flag for manual review.

---

## BUG-012 — `הוצאת היתר בניה` in both `EVENT_TO_STATUS` and `_MANUAL_REVIEW_EVENTS` simultaneously

**Severity:** Medium — caused `permit_status` to show `היתר בתנאים` instead of `היתר` for permits where this was the highest-ranked event  
**Fixed in:** Session V (2026-07-07)  
**File:** `scrapers/complot/api_scraper.py` → `EVENT_TO_STATUS`

### Root cause

Session U intended to remove `הוצאת היתר בניה` from `EVENT_TO_STATUS` and move it exclusively to
`_MANUAL_REVIEW_EVENTS`. The removal did not survive (code was in uncommitted working-tree state).
With the event in both sets, the manual review flag fired correctly but the event also contributed to
`best_rank`, causing `permit_status` to be set inconsistently depending on other events present.
In practice, for permit 20130371, `permit_status = 'היתר בתנאים'` even though the permit had an
`הוצאת היתר בניה` event with higher rank.

### Fix

Removed `'הוצאת היתר בניה': 'היתר'` from `EVENT_TO_STATUS`. The event now lives only in
`_MANUAL_REVIEW_EVENTS`. Status `היתר` is now sourced from the `תאריך הפקת היתר` header field
(see BUG-013) or from other `היתר`-mapping events (`מתן היתר למבקש`, `מסירת היתר`, etc.).

---

## BUG-013 — `permit_status` not set to `היתר` when only `תאריך הפקת היתר` header field is present

**Severity:** Medium — permits with issued permits showed `היתר בתנאים` in the report  
**Fixed in:** Session V (2026-07-07)  
**File:** `scrapers/complot/api_scraper.py` → `_parse_bakasha_file()`, `_merge_permit()`

### Root cause

The permit detail page has a header field `תאריך הפקת היתר` (permit issuance date) that is set
when the permit was formally issued. The scraper only derived `permit_status` from the events table
(`שלבי הבקשה`). If the only `היתר`-level event was `הוצאת היתר בניה` (now removed from
`EVENT_TO_STATUS`), no event mapped to `היתר` and the status remained at `היתר בתנאים`.

### Fix

`_parse_bakasha_file()` now extracts `תאריך הפקת היתר` via `_extract_field()`.
`_merge_permit()` compares its rank (`היתר` = 2) against the event-derived status rank.
If the field implies a higher status, `permit_status` and `permit_status_date` are overridden.
`טופס 4` events (rank 3) still take priority. Requires re-scrape to populate existing CSVs.

---

## BUG-011 — Matched `manual_review` branch applied no project-criteria filters

**Severity:** High — 40 of 177 `manual_review` rows were noise (irrelevant type, public use, stale date)  
**Fixed in:** Session V (2026-07-07)  
**File:** `transform/matcher.py` → `run()` matched branch

### Root cause

When a matched permit had a non-empty `manual_review_event`, the matcher emitted a row immediately
without checking whether the permit met project-creation criteria. The same filters applied to
`untracked` and `הסתיים`/`אוכלס` branches were absent here. Result: permits with irrelevant
construction types (`תוספת למבנה קיים`, `שונות`), public buildings, and unit counts below the
minimum all appeared as `manual_review` rows.

### Fix

Added three guards before emitting a `manual_review` row for a matched permit:
1. `_is_relevant_type(request_type)` — must be True
2. `_is_public_use(permit)` — must be False
3. `_is_below_unit_minimum(permit)` — must be False, with an exception: if the matched project's
   `סוג בנייה` contains `תמ"א 38`, the unit minimum is waived (Complot labels these as `בניה חדשה`).

---

## BUG-010 — Temporal mismatch: old permits matched to new projects via shared gush-helka

**Severity:** High — permits from 2013/2014 matched to projects created in 2020/2021  
**Fixed in:** Session V (2026-07-07)  
**File:** `transform/matcher.py` → `run()`, new `_is_temporally_plausible()`

### Root cause

The gush-helka and address-fallback matching had no temporal guard. A permit from 2013 could match
a project created in 2021 if they shared a parcel — even though they are entirely separate
applications on the same land. Example: permit 20130414 (2013) matched project `הדקלים_3_קרית_אתא`
whose `תאריך בקשה להיתר` is 2021-12-21 (8-year gap).

### Fix

Added `_is_temporally_plausible(permit, proj, max_days_before=365)`: returns False if the permit's
`request_date` is more than 365 days before the project's `תאריך בקשה להיתר`. Applied at both
match methods:
- Gush-helka: candidates are filtered to `plausible` list before `_pick_best_candidate()`
- Address fallback: plausibility check added inline before accepting the match

When no candidates pass the check, `matched_idx` stays None and the permit falls through to the
unmatched path where age and type filters apply.

---

## BUG-009 — `status_advanced` flagged stale statuses older than project's existing dates

**Severity:** High — majority of `status_advanced` rows were false positives  
**Fixed in:** Session K (2026-06-30, handoff A)  
**File:** `transform/matcher.py` → `run()`

### Root cause

`_is_upgrade()` only compared status ranks (e.g. `בקשה להיתר` < `היתר`). It never checked
whether the scraped `permit_status_date` was newer than the project's existing milestone dates.
A permit with a 2011 `היתר` event would flag a project already holding a 2024 `תאריך היתר בתנאים`.

### Fix

Added `_latest_project_date()` (returns max of all non-empty BO milestone date columns) and
`_scraped_date_is_actionable()`:
- If scraped date missing → keep (can't compare)
- If project has dates → scraped date must be strictly after the latest
- If project has no dates → scraped date must be within 1 year

`status_advanced` now requires both `_is_upgrade()` AND `_scraped_date_is_actionable()`.

Result: Bat Yam `status_advanced` dropped from 72 to 2.

---

## BUG-008 — Complot list page returns wrong gush/helka for some permits

**Severity:** High — permits matched to wrong projects  
**Fixed in:** Session K (2026-06-30, handoff A)  
**File:** `scrapers/complot/api_scraper.py` → `_parse_bakasha_file()`, `_merge_permit()`

### Root cause

`GetBakashotByNumber` (permit list page) returns the building file's parcel, not the
individual permit's parcel. For example, permit 20160079 showed `7121-29` in the list
but `7121-54` in its detail page. This caused the permit to match the wrong project.

### Fix

`_parse_bakasha_file` now extracts `gush` and `helka` from the גושים וחלקות table on
the detail page and returns `detail_block_lot`. `_merge_permit` uses this value
preferentially, falling back to the list-page `block_lot` only if the detail page has none.

---

## BUG-007 — Complot list parser concatenates request number + rishuy zamin number

**Severity:** High — affected permits had no detail data; appeared as `scrape_status=success` with all NaN fields  
**Fixed in:** Session I (2026-06-28, handoff C) — partial; completed Session K (2026-06-30, handoff A)  
**File:** `scrapers/complot/api_scraper.py` → `_parse_permit_list()`

### Root cause

Some Complot list-page cells contain two numbers in the same `<td>`: the original request number
and the "מספר הבקשה ברישוי זמין" (rishuy zamin number). The fallback path used
`cells[0].get_text(strip=True)`, which concatenates all text nodes:

```
20180471  +  5176056615  →  201804715176056615
```

The scraper then called `GetBakashaFile?t=201804715176056615`, which returned an error page.
All detail fields (`request_type`, `request_category`, `permit_status`) were silently blank.

### Fix

```python
# Before:
cells[0].get_text(strip=True)

# After:
next(cells[0].stripped_strings, '')  # takes only the first text node
```

### Complete fix (Session K)

The session I fix only covered the fallback path. The primary `row_data` column lookup
(e.g. `row_data.get('מספר בקשה(רישוי זמין)')`) could still return the full concatenated value
if the column header existed in the page. Added a regex post-processor applied after all paths:

```python
_m = re.match(r'(20\d{6})', str(permit_num).strip())
if _m:
    permit_num = _m.group(1)
```

Local permit number format is `YYYY####` (8 digits starting with `20`). Verify for other cities.

### How to spot

Permit number in `bat_yam_fresh.csv` is 18+ digits and starts with a plausible 8-digit number.
Corresponding `request_type` and `permit_status` are NaN despite `scrape_status=success`.

---

## BUG-006 — Matcher year filter used `request_date` instead of `permit_status_date`

**Severity:** Medium — admitted old permits (e.g. 1979 status date) into the report  
**Fixed in:** Session I (2026-06-28, handoff C)  
**File:** `transform/matcher.py` → `run()`

### Root cause

`request_date` in Complot is the date the database record was created, not the actual permit
application date. Filtering by `request_date >= min_year` passed old permits whose record was
created in the cutoff window but whose actual milestone events were from the 1970s–1980s.

### Fix

Filter by `permit_status_date` (the date of the highest-ranked milestone event) instead.
Permits with no `permit_status_date` pass through (can't filter what we don't have).

A second filter on `first_event_date` (earliest event in the events table) was also added to
catch old permits whose first event predates the cutoff even if recent activity exists.
`first_event_date` requires a re-scrape to populate — not yet in existing `bat_yam_fresh.xlsx`.

---

## BUG-005 — Bartech `block_lot` returns raw Hebrew text instead of `GUSH-HELKA` format

**Severity:** Low — data was present but in wrong format (`גוש: 6786, חלקה: 8` vs `6786-8`)  
**Fixed in:** Session I (2026-06-28, handoff C)  
**File:** `scrapers/bartech/api_scraper.py` → `_parse_row()`

### Root cause

BeautifulSoup's `html.parser` lowercases all HTML attribute names. The code used
`label12.get('ToolTip', '')` (capital T) — this always returned `''`, falling through to the
raw text content. `_parse_block_lot('')` returned `''`, so the raw text was used as fallback.

### Fix

```python
# Before:
block_lot = _parse_block_lot(label12.get('ToolTip', '')) or label12.get_text(strip=True)

# After:
tooltip = label12.get('tooltip', '') or label12.get('ToolTip', '')  # try lowercase first
raw_text = label12.get_text(strip=True)
block_lot = _parse_block_lot(tooltip) or _parse_block_lot(raw_text) or raw_text
```

---

## BUG-004 — Bartech STATUS_MAP missing common statuses → silent empty `permit_status`

**Severity:** Low — affected classification accuracy; statuses logged as `[NEW STATUS]`  
**Fixed in:** Session I (2026-06-28, handoff C)  
**File:** `scrapers/bartech/api_scraper.py`

### Root cause

Initial `STATUS_MAP` only covered statuses known from the handoff document. First real scrape
surfaced 7 additional statuses not in the map, all silently mapping to `''`.

### Fix

Added to `STATUS_MAP`:
- `החלטה לאשר בועדה`, `בקרה מרחבית - הוחזר לעורך`, `פתיחת בקשה להיתר` → `בקשה להיתר`
- `העברת היתר לפיקוח על הבני`, `גמר בניה`, `מסירת א. תחילת עבודות` → `היתר`

Added to `_KNOWN_CLOSED` (logged but unmapped by design):
- `סגירת בקשה - פג תוקף החלטה`

---

## BUG-001 — NaN coercion: `float('nan') or ''` returns NaN, not `''`

**Severity:** Critical — caused matcher to produce 0 rows  
**Fixed in:** Session F (2026-06-27, handoff B)  
**File:** `transform/matcher.py`

### Root cause

Python's `or` operator returns the first truthy value. `float('nan')` is truthy (it is a
non-zero float), so `float('nan') or ''` evaluates to `float('nan')`, not `''`.

When pandas reads an empty Excel cell it stores `float('nan')`. The code used:

```python
str(permit.get('request_type', '') or '').strip()
```

This produced the string `'nan'` instead of `''` for every blank `request_type` cell, because:

```python
float('nan') or ''   # → float('nan')  (NaN is truthy!)
str(float('nan'))    # → 'nan'
```

### What broke

1. `type_known = bool('nan') = True` — the matcher thought the request type was known for every
   API-scraped permit, even though the API never returns `request_type`.
2. `type_relevant = _is_relevant_type('nan') = False` — `'nan'` doesn't match any construction type.
3. Combined effect: `(type_relevant or not type_known)` → `False or False` → `False` — the
   `new_permit` branch never fired. **0 rows output.**
4. Same issue in `scraped_status`: `'nan'` → `_is_upgrade()` returns `False` → `status_advanced`
   never fires either.

### Fix

Added `_clean()` helper that explicitly handles `None`, `float('nan')`, and the string `'nan'`:

```python
def _clean(val) -> str:
    if val is None:
        return ''
    if isinstance(val, float) and pd.isna(val):
        return ''
    s = str(val).strip()
    return '' if s.lower() == 'nan' else s
```

Replaced every `str(... or '').strip()` call with `_clean(...)` throughout `run()`.

### Prevention

Never use `x or ''` to guard against NaN. Always check `pd.isna()` or `isinstance(val, float)`
explicitly when the value may come from a DataFrame.

---

## BUG-002 — Matcher returned 0 rows (masked by BUG-001)

**Severity:** Critical — same root cause as BUG-001  
**Fixed in:** Session F (2026-06-27, handoff B)

Documented separately to clarify the symptom: the matcher produced an empty Excel report,
making it appear that there were no matching projects/permits. The actual gush-helka intersection
was 672 pairs (out of 779 project pairs and 2,705 permit pairs) — plenty of matches. The 0-row
output was entirely caused by BUG-001 preventing any branch from firing.

**After fix:** 414 `new_permit` rows, re-scrape in progress to surface `status_advanced` rows.
