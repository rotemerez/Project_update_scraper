# Session Handoff — 2026-07-09 A

**Date:** 2026-07-09  
**Session:** A  
**Scope:** Diagnostic cleanup; committee registry built

---

## What was accomplished

### 1. Diagnostic scripts deleted

`scripts/diagnose_hadera.py` and `scripts/diagnose_hadera2.py` were temporary scripts
from session Z. Deleted.

### 2. Committee registry — `config/committees.py`

Built a complete committee registry mapping all 162 cities from
`docs/all_projects_08072026.xlsx` to their planning portal scrapers.

**Coverage:**
| Category | Count |
|---|---|
| Active Complot | 46 |
| Active Bartech | 27 |
| Excluded — proprietary | 3 |
| Excluded — no_scraper | 84 |
| Excluded — url_unverified | 1 |
| **Total entries** | **161** |
| **Total cities covered** | **162** |

(Krayot = one entry with `cities_hebrew: [קרית מוצקין, קרית ביאליק, קרית ים]`.)

**Key design decisions:**
- One entry per committee portal (not one per city). The nationwide runner runs the
  scraper once per entry, then runs the matcher once per `city_hebrew` in that entry.
- `include_bakasha_meqdamit=True` set for פתח תקווה (site_id=84) and הרצליה (site_id=121)
  per CLAUDE.md city exception.
- Netanya (`vaadnet.netanyagis.co.il`) — marked `exclude=True, exclude_reason='url_unverified'`;
  this is a non-standard URL that may not be a standard Bartech portal. Test before enabling.
- `permit_url_base` populated only for cities already run (Kiryat Ata, Hadera, and all Bartech
  cities using the standard `{base_url}/PermitApplicationDetails?Entity_Number=` pattern).
  Complot cities have `permit_url_base=None` for now except Kiryat Ata.

**Source:** `local_committee_scrapers/unified_scraper/municipal_scraper/registry/dispatcher.py`
(revision 2026-02-25). The main registry (not `permits_scraper_export/registry/`) has site_ids.

**Validation passed:**
- All 162 project cities present in registry
- No duplicate city coverage
- No active Complot entry missing `site_id`
- No active Bartech entry missing `base_url`

---

## Open question going into next session

**72 active committees seems low** — the user recalled more.

The 84 "no_scraper" cities include some with large project counts. Several of these may be
served by regional-council portals that exist in the dispatcher but weren't linked, because
the mapping from English dispatcher key → Hebrew city name wasn't obvious.

Candidates to investigate (sorted by project count):

| City | Projects | Possible portal |
|---|---|---|
| באר יעקב | 96 | Gezer regional council? |
| מזכרת בתיה | 95 | Gezer regional council? |
| טירת הכרמל | 78 | Own Bartech portal? |
| מבשרת ציון | 75 | mateh yehuda (bartech)? |
| זכרון יעקב | 62 | Own portal? |
| אור עקיבא | 45 | hof hacarmel (bartech)? |
| בנימינה גבעת עדה | 42 | emek hefer (bartech)? |
| נשר | 30 | Own portal near Haifa? |
| קרית עקרון | 11 | sorkot (bartech)? |
| בית דגן | 11 | ? |

**Approach for next session:**
1. Open each candidate city's suspected dispatcher portal URL in a browser.
2. Confirm the city's permits appear there (search by city name or address).
3. If confirmed: change `exclude=True` → `exclude=False`, set correct scraper params,
   and set `city_name_hebrew` to the Hebrew name used in portal address fields (may differ
   from the Hebrew name in the projects file).

---

## What to do in the next session

1. **Audit no_scraper cities** — verify whether large-project cities without a scraper are
   actually covered by a regional-council portal in the dispatcher. Update the registry.

2. **SQLite schema** (Step 2 from the session E plan):
   - Create `outputs/permits.db` with the schema described in the E handoff.
   - Write `scripts/migrate_csvs_to_db.py` to load existing CSV outputs into the DB.

3. After schema is done, continue with Steps 3–4 from the E handoff
   (adapt scrapers to write to SQLite, build `scripts/run_all.py`).

---

## State of key files

| File | State |
|---|---|
| `config/committees.py` | NEW — 161 entries, 162 cities, validated |
| `config/__init__.py` | NEW — empty |
| `docs/NEXT_STEPS.md` | Updated — session F done, committee audit as immediate task |
| `transform/matcher.py` | Unchanged from session E |
| `outputs/hadera_report.xlsx` | Final — 53 rows |
| `outputs/kiryat_ata_report.xlsx` | Valid — 89 rows |
| `docs/all_projects_08072026.xlsx` | 24,886 projects, 162 cities |
