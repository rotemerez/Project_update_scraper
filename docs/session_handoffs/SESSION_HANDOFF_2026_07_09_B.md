# Session Handoff — 2026-07-09 B

**Date:** 2026-07-09  
**Session:** G  
**Scope:** Committee registry audit — 4 new committees activated, ישובי הברון identified

---

## What was accomplished

### 1. No-scraper city audit — completed

Investigated 8 high-project-count cities that were marked `no_scraper` in the registry.

**Method:**
1. Checked the dispatcher for regional council portals — confirmed hof hacarmel, mateh yehuda,
   and emek hefer serve kibbutzim/moshavim only (not independent cities). Confirmed via live
   HTTP fetches.
2. Tried standard Bartech subdomain patterns (`{city}.bartech-net.co.il`) and Complot
   (`{city}.complot.co.il`) — all returned DNS not found.
3. User identified the correct portals by searching municipal websites directly.

**Results:**

| City | Committee | System | URL |
|---|---|---|---|
| באר יעקב (96) | מיצפה אפק | Bartech | `www.vmm.co.il` |
| מזכרת בתיה (95) | זמורה | Bartech | `www.zmora.org.il` |
| טירת הכרמל (78) | מורדות כרמל | Complot site_id=61 | `mordotcarmel.org/iturbakashot/` |
| נשר (30) | מורדות כרמל | Complot site_id=61 | same |
| מבשרת ציון (75) | הראל | Bartech | `www.v-harel.co.il` |
| זכרון יעקב (62) | ישובי הברון | SharePoint | `vaada-habaron.org.il` |
| אור עקיבא (45) | ישובי הברון | SharePoint | same |
| בנימינה גבעת עדה (42) | ישובי הברון | SharePoint | same |
| ג'סר א זרקא | ישובי הברון | SharePoint | same |

### 2. Committee registry updated — `config/committees.py`

**4 new active entries added:**

| Committee | Section | site_id / base_url | Cities |
|---|---|---|---|
| מורדות כרמל | `_COMPLOT`, Haifa District | site_id=61 | טירת הכרמל, נשר |
| מיצפה אפק | `_BARTECH`, Center District | `www.vmm.co.il` | באר יעקב |
| זמורה | `_BARTECH`, Center District | `www.zmora.org.il` | מזכרת בתיה |
| הראל | `_BARTECH`, Jerusalem District (new section) | `www.v-harel.co.il` | מבשרת ציון |

**1 consolidated excluded entry added:**
- `ישובי הברון` — covers זכרון יעקב, אור עקיבא, בנימינה גבעת עדה, ג'סר א זרקא.
  `exclude=True, exclude_reason='no_scraper'`. Portal is SharePoint-based, not Complot/Bartech.

**9 standalone no_scraper entries removed** (replaced by the 5 entries above).

**Updated counts:**
- Active: 72 → 76
- Complot active: 46 → 47
- Bartech active: 26 → 29
- No scraper entries: 84 → 76

---

## Open questions / caveats

**מורדות כרמל frontend returns 403.** The portal at `mordotcarmel.org` blocks direct HTTP.
The Complot API (`handasi.complot.co.il/handasi2016/api/...`) is independent of the portal
frontend and should still work — but `GetBakashotByNumber(61)` must be tested before building
the runner. The permit_url_base (`mordotcarmel.org/iturbakashot/#request/`) will produce
dead links if the site keeps blocking; leave it for now and update once confirmed.

**ישובי הברון is a SharePoint portal.** The page structure uses SharePoint 2013/2016 routing
(`/newengine/Pages/request2.aspx`). No standard scraper can be used. Cities covered have
combined ~149 projects in the file. Worth building a custom scraper eventually — but scope it
first by fetching the page and seeing what data the SharePoint REST API exposes.

---

## What to do in the next session

### Priority 0 — Trim NEXT_STEPS.md (context reduction)

`docs/NEXT_STEPS.md` is 700+ lines and is read at the start of every session (~12k tokens).
The archive file has already been created: `docs/session_handoffs/DONE_ARCHIVE.md`.

Do this first — it takes 2 minutes and pays off every session:
1. In NEXT_STEPS.md, find the line `### Session E — 2026-07-08` (start of old Done history).
2. Replace everything from that line through the old `---` separator before "## Immediate"
   with: `*Older sessions archived to \`docs/session_handoffs/DONE_ARCHIVE.md\`.*`
3. Verify the file now starts with header → Done (G + F only) → archive pointer → Immediate.

Target: ~150 lines (down from 720).

### Priority 1 — Test and run the 4 new committees

For each new committee, follow this checklist:

**Complot (מורדות כרמל, site_id=61):**
1. Test the API: `GET https://handasi.complot.co.il/handasi2016/api/BakashotHandasa/GetBakashotByNumber/61`
   — confirm it returns data (not an error or empty).
2. Check `request_type` values: `print(df['request_type'].value_counts())` and look for
   double-yod spelling variants (BUG-016 checklist).
3. Create `scripts/run_mordot_carmel.py` using same pattern as `scripts/run_kiryat_ata.py`.
4. Run matcher with `docs/all_projects_08072026.xlsx` filtered to `['טירת הכרמל', 'נשר']`.

**Bartech (מיצפה אפק, זמורה, הראל):**
1. For each: test that `SearchPermitApplicationResults` returns data for type 51.
2. Create runner scripts: `run_mitzpe_afek.py`, `run_zmora.py`, `run_harel.py`.
3. Check `request_type` value counts before running matcher.
4. Run matcher with appropriate city filter.

### Priority 1.5 — Trim global CLAUDE.md (context reduction)

File: `C:\Users\Rotem\.claude\CLAUDE.md` (147 lines, loads on every project).

Two changes:
1. **Remove ILA-specific Python lines** (lines 21–22): the `c:\R_PROJECTS\ILA_scraper\venv\...`
   path and run command belong in the ILA project's own CLAUDE.md, not the global one.
   Replace with: `- Projects use a local venv or system interpreter. Each project's CLAUDE.md specifies its Python path.`

2. **Condense Model Selection section** (currently 46 lines): cut "How to Specify Model"
   and "Cost Reduction Best Practices" blocks (~20 lines of generic advice). Keep the
   Haiku/Sonnet guidance, which is the actually useful part.

3. **Condense Documentation Structure section** (currently 62 lines): cut "Documentation
   Standards", "Auto-Documentation Triggers", and "Documentation Review Checklist" (~36 lines).
   Keep the docs/ folder list and session handoff naming convention.

Target: ~90 lines (down from 147). Saves ~1,000 tokens per session across all projects.

### Priority 2 — SQLite schema (from Session E plan)

See Step 2 in the E handoff (session E, 2026-07-08):
- Create `outputs/permits.db` with the schema described there.
- Write `scripts/migrate_csvs_to_db.py` to load existing CSV outputs.

---

## State of key files

| File | State |
|---|---|
| `config/committees.py` | Updated — 76 active (was 72), 4 new entries, 9 removed |
| `docs/NEXT_STEPS.md` | Updated — session G done, new immediate tasks |
| `scrapers/complot/api_scraper.py` | Unchanged |
| `scrapers/bartech/api_scraper.py` | Unchanged |
| `transform/matcher.py` | Unchanged |
| `outputs/kiryat_ata_report.xlsx` | 89 rows — still awaiting manual review |
| `outputs/hadera_report.xlsx` | 53 rows — still awaiting Hadera stage classification |
