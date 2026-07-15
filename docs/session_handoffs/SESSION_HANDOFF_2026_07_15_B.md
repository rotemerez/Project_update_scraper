# Session Handoff — 2026-07-15 B

**Date:** 2026-07-15
**Session:** R (follows Session Q, covered in `SESSION_HANDOFF_2026_07_15_A.md`)
**Scope:** נתניה confirmed Bartech; תל אביב יפו fully reverse-engineered and a working
browser-automation scraper built (pending live validation next session)

---

## What was accomplished

### נתניה — confirmed Bartech

Live recon (`curl` against `https://vaadnet.netanyagis.co.il`) confirmed this is a Bartech
instance, same signature as v-harel/zmora/vmm/Holon/Krayot — `/SearchPermitApplication` →
`/SearchPermitApplicationResults/` → `/PermitApplicationDetails?...`, identical result-table
columns. The dummy `g-recaptcha-response=x` trick (already used by
`scrapers/bartech/api_scraper.py::_fetch_parcel_page()`) works here too — reCAPTCHA v2 on this
endpoint is not strictly server-enforced, unlike Tel Aviv's. **No new scraper code needed.**
Debug snapshots: `outputs/debug_netanya_search.html`, `_results.html`, `_results2.html`.

**Not yet done**: move נתניה from `_EXCLUDED` to the active Bartech list in
`config/committees.py`, write `scripts/run_netanya.py` (copy `run_harel.py` pattern), confirm
`min_year`/pagination live, smoke-test.

### תל אביב יפו — full recon + scraper built

Two recon passes fully reverse-engineered `rishuybniya.tel-aviv.gov.il`:
- **Session 1** (static bundle analysis, this session's CLI): confirmed it's a bespoke Angular
  SPA + .NET REST API, not Complot/Bartech. Couldn't resolve the live API host (injected at
  runtime).
- **Session 2** (Claude Desktop live browser instrumentation): resolved the API host
  (`apimtlvprd.tel-aviv.gov.il`), the search endpoint, request/response schema, and the
  `licenseId` numbering scheme. Full writeups: `docs/tlv_permit_api_findings.md`,
  `docs/tlv_permit_api_findings2.md`.

Key finding: reCAPTCHA Enterprise v3 is **gateway-enforced** (verified: missing/fake token → real
`400`s) — unlike every other committee scraped so far, this cannot be worked around with a
placeholder token. Rotem decided on **Option A**: drive the real search UI with a visible browser
so the page's own JS mints a valid token, rather than replaying a token against the API directly
(riskier — Enterprise scoring ties to the originating session) or a captcha-solving service
(ruled out).

**Built this session** (plan file: see `EnterPlanMode`/`ExitPlanMode` transcript, not persisted to
repo):
- `scrapers/tel_aviv/scraper.py` — `TelAvivPermitsBrowserScraper`, three public methods
  (`scrape_parcels`, `scrape_license_ids`, `scan_license_range`). See BUG-017/BUG-018 in
  `docs/BUG_REFERENCE.md` for two real bugs found and fixed via live browser observation
  (Rotem watching the actual non-headless window) — a form-fill race condition and a
  reCAPTCHA-rejection-mis-counted-as-miss bug. Also confirmed **empirically** that reCAPTCHA
  Enterprise adaptively degrades a session's score based on request frequency/pattern (not just
  headless-ness) — mitigated with the results page's own "חיפוש חדש" button for in-app navigation
  (found via a live screenshot from Rotem) instead of a full page reload per query, plus longer
  inter-query delays and scaling backoff on rejection.
- `scripts/run_tel_aviv.py` — 3-phase orchestration (parcel batch → gap-fill within the found
  range → sequential continue past the max found), excludes `אוכלס` (occupied) projects from the
  query target (cuts 5,640 → 3,893 pairs), `PARCEL_LIMIT = 150` caps the first real run per
  Rotem's explicit request to validate at scale before committing to the full ~3,893-pair run
  (which alone would take 24h+ of continuous, visible-browser runtime).
- `scripts/run_tel_aviv_matcher.py` — standard `matcher.run()` call, no `permit_url_base` (detail
  pages need Azure B2C login, no public URL exists).

**Known, deliberate schema gap**: `request_date`, `request_category`, `requestor`,
`bakasha_description`, `shimush_ikari`, `unit_count` are left blank (not fabricated) — not present
in the public search response, only behind the login-gated detail page.

**Status vocabulary (`STATUS_MAP`) ships empty** — only a handful of real values seen during
testing (`בדיקה מרחבית מחלקת רישוי`, `פניה נדחתה`, `סגירת בקשה-נמסר היתר`,
`סגירת בקשה-פג תקף החלטה`, `סגירת בקשה-נפתחה בטעות`, `סיום רישוי-במערכת קודמת`) — not enough to
classify confidently yet. New values log via `[NEW STATUS]`.

**Explicitly deferred**: live validation of the full pipeline (Rotem: "wait for tomorrow"). Code
is written and syntax-checked but the last live test was interrupted mid-run (killed via
`TaskStop`) after confirming the core mechanism works when the reCAPTCHA score isn't degraded.

---

## Open items carried forward

- **תל אביב יפו live validation** — run `scripts/run_tel_aviv.py` for real (150-pair batch) next
  session, confirm the fixes hold up over a longer session, then decide whether to raise
  `PARCEL_LIMIT`.
- **נתניה wiring** — `config/committees.py` entry, `scripts/run_netanya.py`, smoke test. Not
  started.
- **ירושלים / קצרין** — still fully unidentified, pure recon needed (view-source, network tab,
  robots.txt) before any scraper design.
- **Tel Aviv second site** (`https://handasa.tel-aviv.gov.il/pages/default.aspx`, בדיקת אכלוס) —
  deliberately deferred per Rotem, not investigated at all yet.
- Everything already carried forward from `SESSION_HANDOFF_2026_07_15_A.md` (Complot triage,
  מורדות כרמל re-run, V2 runner missing 5 committees, pending report reviews, Hadera
  classification) is still open — untouched this session.

---

## State of key files

| File | State |
|---|---|
| `scrapers/tel_aviv/scraper.py` | New — browser-automation scraper, built + bug-fixed this session, not yet validated at scale |
| `scripts/run_tel_aviv.py` | New — 3-phase runner, `PARCEL_LIMIT=150` |
| `scripts/run_tel_aviv_matcher.py` | New — standard matcher runner |
| `scripts/_smoke_test_tel_aviv.py` | New — throwaway validation script, still useful for the next live test |
| `docs/tlv_permit_api_findings.md` / `tlv_permit_api_findings2.md` | New — full Tel Aviv API recon |
| `docs/BUG_REFERENCE.md` | Updated — BUG-017, BUG-018 added |
| `docs/NEXT_STEPS.md` | Updated through Session R |
| `outputs/debug_netanya_*.html` | New — Netanya recon snapshots |
| `requirements.txt` deps (`undetected-chromedriver`, `selenium`) | Installed into the global Python 3.13 env this session (were listed but not actually installed); also installed `setuptools` (provides a `distutils` shim `undetected_chromedriver` needs on 3.12+) |

---

## Uncommitted work reminder

Everything from Session R (and everything still uncommitted from Sessions L-Q per the prior
handoff) needs a commit. Also noticed an **unrelated pre-existing untracked file**,
`docs/Kiryat_Ata_July_2026.xlsx` — not created this session, left alone; flagging in case it's
orphaned work from an earlier session that should either be committed or cleaned up.
