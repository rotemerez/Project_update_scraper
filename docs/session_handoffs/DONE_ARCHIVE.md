# Done Archive — Sessions A through E (2026-07-08)

Archived from NEXT_STEPS.md on 2026-07-09 to keep the live file small.
Full per-session detail lives in `docs/session_handoffs/SESSION_HANDOFF_*.md`.

---

### Session E — 2026-07-08

- **Hadera matcher run** — 53 rows: 8 `status_advanced`, 45 `untracked`, 0 `manual_review`.
  2,788 permits scraped; 374 matched to projects.

- **BUG-016 fixed** (`transform/matcher.py` → `RELEVANT_TYPE_SUBSTRINGS`):
  Hadera Bartech spells construction type as `בנייה חדשה` (double-yod) while the substring list
  had only `בניה חדשה` (single-yod). 5 matched upgrades and 44 untracked permits were silently
  dropped. Added `'בנייה חדשה'` and `'הריסה ובנייה'` to the list. Before running the matcher
  on any new city, always check `df['request_type'].value_counts()` for spelling variants.
  Documented in `docs/BUG_REFERENCE.md` (BUG-016) and `CLAUDE.md` (New-City Checklist).

- **Unit minimum check added to `status_advanced` and `new_permit` branches** (`transform/matcher.py`):
  These two branches previously skipped `_is_below_unit_minimum`. Single-unit permits (e.g.
  `בית פרטי דו משפחתי`, `unit_count=1`) were surfacing as status updates for multi-unit projects.
  Fixed by computing `waive_unit_min = 'תמ"א 38' in project_sug_bnia` and adding
  `and (waive_unit_min or not _is_below_unit_minimum(permit))` to both conditions.
  תמ"א 38 projects are always tracked regardless of unit count (per נוהל הקמת פרויקטים).

- **Nationwide scrape architecture designed and documented** (see item 8 in Later section):
  Decisions: office-based scraping (fixed IP), incremental mode for regular runs, SQLite for
  permit storage, nation-wide projects export, single consolidated report across all committees.
  `docs/all_projects_08072026.xlsx` reviewed: 24,886 projects, 162 cities. Canonical scraper
  registry source: `C:\R_PROJECTS\local_committee_scrapers\registry\dispatcher.py`.

### Session AA — 2026-07-08

- **`scripts/run_hadera_matcher.py` pre-built** — ready to run once `hadera_fresh.csv` exists.
  Copies the Kiryat Ata matcher pattern; uses `docs/Hadera_Projects_08072026.xlsx`,
  `outputs/hadera_fresh.csv`, city `חדרה`, cache `outputs/hadera_matched_cache.json`,
  `permit_url_base='https://hadera.bartech-net.co.il/PermitApplicationDetails?Entity_Number='`.

- **Hadera stage classifier artifact built**:
  URL: https://claude.ai/code/artifact/c0dae2d0-319e-4123-b580-332c90957984
  All 182 unique `[NEW STAGE] Unmapped` strings from the Hadera scrape log.

### Session Z — 2026-07-08

- **Hadera scraper: reverted to plain type scan** — two-phase parcel approach produced mostly
  duplicates; plain `scraper.scrape()` with `min_year=2010` is equivalent. Reverted.
- **Bartech `scrape_parcels` hardened**: `max_pages` guard, year-based early exit,
  `max_pages_per_parcel=20` cap, zero-new-streak exit (3 pages).

### Session Y — 2026-07-08

- **Bartech scraper: `shimush_ikari` and `unit_count` added** — full data parity with Complot.
- **Bartech scraper: Hadera STATUS_MAP + STAGE_TO_STATUS + `_UNMAPPED_STAGES` batch** (~25 entries).
- **Bartech scraper refactored for two-phase scraping**: `scrape_parcels`, `merge_and_enrich`,
  `early_exit_year` param.

### Session X — 2026-07-08

- **Kiryat Ata scrape F completed** — 3,318 permits, clean run from office IP.
- **Matcher: `הוצאת היתר בניה` manual_review suppression** — 143 → 59 `manual_review` rows.
- **Matcher: new public-use `shimush_ikari` values** + BUG-014 + BUG-015 fixed.
- **Final Kiryat Ata report**: 89 rows — 0 new_permit, 8 status_advanced, 22 untracked, 59 manual_review.

### Session W — 2026-07-07

- **GitHub remote set up**: `https://github.com/rotemerez/Project_update_scraper`
- **Kiryat Ata scrape E failed** (IP block) — re-scraped from office next day.

### Session V — 2026-07-07

- **Matcher: project-criteria filters on `manual_review` branch** — 177 → 143 rows.
- **Matcher: temporal plausibility filter** — prevents decade-old permits matching new projects.
- **Matcher: `permit_url_base` parameter** added; `request_url` column in report.
- **Complot: `תאריך הפקת היתר`** extracted from detail page header.

### Session U — 2026-07-06

- **`bakasha_description` extraction fixed** — was a section header, not a label-value row.
- **`unit_count` field added** to Complot scraper.
- **`manual_review_event` field** added (scraper + matcher); `_MANUAL_REVIEW_EVENTS` set defined.

### Session T — 2026-07-05

- **Matcher fix — `אוכלס` status** treated identically to `הסתיים`.
- **Complot: `shimush_ikari`** extracted; public-building + unit-minimum filters added to matcher.

### Session S — 2026-07-05

- **Bartech: 3 final reviewer annotation decisions applied**.
- **Bartech: Krayot log triage** — 18 STAGE_TO_STATUS + 24 _UNMAPPED_STAGES entries.
- **Krayot matcher**: 38 rows — 1 new_permit, 35 status_advanced, 2 untracked.

### Session R — 2026-07-02

- **Applied all reviewer annotations** to both scrapers (Complot EVENT_TO_STATUS 11→29,
  Bartech STATUS_MAP expanded to 40 entries).

### Sessions A–Q (2026-06-25 to 2026-07-02)

See individual handoff files in `docs/session_handoffs/` for full detail.

**Key milestones:**
- Session A–B: project scaffolding, matcher UC logic, relevant-type filter
- Session D: discovered Complot API (`GetBakashotByNumber`, `GetBakashaFile`)
- Session E–F: built Complot API scraper; fixed BUG-001 (NaN coercion)
- Session H–I: discovered Bartech API; built Bartech scraper
- Session J: `_pick_best_candidate()` disambiguation; incremental scrape mode
- Session K: `_scraped_date_is_actionable()`; detail-page gush/helka (BUG-008)
- Session L: Bartech scraper rebuilt two-phase; Ramat Gan scraper
- Sessions N–Q: Holon, Kiryat Ata, Krayot scraped; annotation artifacts built
