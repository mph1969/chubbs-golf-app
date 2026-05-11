# Session Notes — last touched 2026-05-11

State at break. Pick up from any of the **OPEN ITEMS** below.

## Everything shipped so far (v5.46 → v5.59)

| Version | What |
|---|---|
| v5.46 | Course-library audit vs Terry's S4 sheet — Birds par/SI fixed, Tangspring + Qingyuan loaded |
| v5.47 | Match-play engine helpers — `matchPlayStrokes`, `matchPlayHoleWinner`, `matchPlayStatus` |
| v5.48 | Match-play overlay banner on score view |
| v5.49 | Auto-push closed match to bracket (admin one-tap) |
| v5.50 | Per-hole net comparison hint |
| v5.51 | §11 tiebreak surface when ALL SQUARE thru 9 |
| v5.52 | Hide Playoffs tab when not relevant + emoji cleanup |
| v5.53 | 4-tab nav restructure (Round / Leaderboard / Standings / Setup) + seg-pills |
| v5.54 | Scorer-aware match-play banner (designated scorer flow) |
| v5.55 | Default-scorer rule (brain trust → lowest hcp) + playoff intro card + sw.js cosmetic fix |
| v5.56 | Header condensation + Setup → Admin label |
| v5.57 | **Tiebreak rule flip** — round-avg per Terry 2026-05-10 (matches his spreadsheet) |
| v5.58 | **Freeze matchplay status at close** — bug fix from readiness audit (A4) |
| v5.59 | **Honeypot module + paths fully removed** — was v5.41 fun-gimmick, net -474 lines |

Plus QA harness (`qa/season4_qa.py`, `qa/playoff_sim.py`, `qa/matchplay_engine.py`), Season 3 extractor (`extract_season3.py`), WeChat blast draft (`NewFeatures/wechat-blast-may23-playoffs.md`), and v5.52 UI plan doc.

## Validation status

| Layer | Status |
|---|---|
| Stableford scoring engine | ✅ 211/212 S3 player-events match Terry's spreadsheet (1 diff is Terry's transcription error: Jack/Oct/Mountain shows 24 in Results sheet but his own hole-by-hole PTS row sums to 35, matching app) |
| Match-play engine | ✅ 11/11 sanity tests pass (qa/matchplay_engine.py) — includes 3 freeze tests added in v5.58 |
| Playoff bracket cascade | ✅ Cup/Plate/Shield/Spoon resolves cleanly under chalk + all-upsets (qa/playoff_sim.py) |
| Seeding tiebreak (round-avg) | ✅ Matches Terry's spreadsheet exactly: Dustin #7, Terry #8 |
| Pre-event readiness audit | ✅ 8 checks ran; 1 bug found and fixed in v5.58 |
| Firebase rules + indexOn | ⏳ User publishes the rules (see below) |

## Pre-event readiness audit findings (2026-05-10)

| # | Check | Result |
|---|---|---|
| A1 | Admin bundle build sets scorerPlayerId correctly | ✅ Clean |
| A2 | Mobile import → matchplay banner activation | ✅ Clean |
| A3 | Designated scorer header correctness | ✅ (cosmetic note: admin masterMode always sees "🎯 You're the scorer" even when not the actual scorer — refine later) |
| A4 | Save to bracket round-trip | ✅ **Bug found + fixed in v5.58** — match-play label drift after close |
| A5 | Cascade auto-population after R16 saves | ✅ Clean |
| A6 | Hero subtitle + sub-pill at narrow widths | ✅ (cosmetic note: subtitle could ellipsize at 360px on long course names — defer to dry-run feedback) |
| A7 | Date-based gates | ✅ Clean |
| A8 | Tiebreak rule (round-avg) applied | ✅ Confirmed in both aggregateSeason + _poTop16 |

## OPEN ITEMS — pick up here

### 1. Lock playoff seeds via admin tool
Final participation list arriving today. Use chubbs-admin.netlify.app:
- Load May Yinli event config
- Mark withdrawals (Mike W / Diego / Anthony / others as needed)
- Run "Lock Playoff Seeds"
- Push to Firebase

Default scorer rule auto-fills brain-trust-or-lowest-hcp per foursome — admin can override per group.

### 2. Publish Firebase rules (5 min)
Paste this in Firebase Console → Realtime Database → Rules:

```json
{
  "rules": {
    "events": {
      ".read": true,
      ".indexOn": "bundle/_publishedAt",
      "$eventId": {
        ".write": true
      }
    },
    "admin": {
      ".read": true,
      ".write": true
    }
  }
}
```

Effect: silences indexOn warning + removes /chubbs honeypot paths from rule surface. Existing /chubbs/* data can be deleted from Data tab (cosmetic).

### 3. Send WeChat blast (~May 16)
Draft in `NewFeatures/wechat-blast-may23-playoffs.md`. Attach 2-3 screenshots from dry-run. Send to brain trust 1 week before May 23.

### 4. Dry-run on phone
Once seeds are locked + bundle pushed:
- Pull-to-refresh app to v5.59+
- Set up fake foursome with seeded names (Matt D + Andy + Nick + Jamie covers M1 + M8)
- Enter scores → matchplay banner appears
- Force a match close → save to bracket
- Force ALL SQUARE thru 9 → tiebreak surface

If anything looks off, flag — most likely areas are visual layout at narrow widths and any first-time scorer-mode confusion.

## Useful copy-paste snippets

### Inject test playoff seeds (browser console, dry-run path)
```javascript
const store = JSON.parse(localStorage.getItem('chubbs_seasons_v1') || '{}');
if (!store.seasons) store.seasons = {};
if (!store.seasons['season-4']) store.seasons['season-4'] = { id:'season-4', name:'Season 4 (2025–2026)', events:[], status:'active' };
store.seasons['season-4'].playoffs = {
  seeds: ['Matt D','Nick','Jordan','George','Ryan N','Leigh','Dustin','Terry','Paul','John','Hanson','Kevin','Jack','Ricardo','Jamie','Andy'],
  seededAt: '2026-05-11'
};
store.viewingSeasonId = 'season-4';
localStorage.setItem('chubbs_seasons_v1', JSON.stringify(store));
localStorage.setItem('cpi_master', '1');
location.reload();
```
(Note: Dustin at #7, Terry at #8 — matches Terry's spreadsheet under v5.57 round-avg rule.)

### Reset
```javascript
localStorage.removeItem('chubbs_seasons_v1');
localStorage.removeItem('cpi_master');
location.reload();
```

### Run QA harness
```bash
python qa/season4_qa.py                       # standings diff vs Terry
python qa/season4_qa.py --per-event --exclude=apr-palm   # per-event drilldown
python qa/playoff_sim.py                      # full bracket sim under v5.57 rule
python qa/playoff_sim.py --best7              # alternative under best-7 primary
python qa/matchplay_engine.py                 # 11 sanity tests on engine helpers
python extract_season3.py                     # regenerate season-3.json from xlsx
```

## Confirmed locked rules (2026-05-10)

- Match-play model: lower NET wins each hole; full hcp differential to higher-hcp player (Terry confirmed via WeChat 2026-05-10)
- 9-hole match tiebreak: Stableford → lower hcp → arm wrestle (handbook §11)
- Season-standings tiebreak: best-7 → **round-avg desc** → seedPoints desc → stableford desc (Terry 2026-05-10, supersedes 2026-04-29 played-desc)
- Playoff seeding tiebreak: seedPoints → **round-avg desc** → stableford desc (same rule)
- 16-player playoff field after withdrawals: Mike W / Diego / Anthony in Fireball (or out) — final list locked via admin today

## Deferred to post-May 23

- Bracket-via-Firebase sync (would remove admin-re-push friction)
- Twosome detection (only if some matches play 2-some)
- S3 history bake into app for "View past seasons"
- Stadium mode for night golf
- "Concede" hole/match button
- Cosmetic refinement: admin masterMode banner label

## Files

- `ChubbsMobileApp_v5/index.html` — mobile PWA (~8580 lines after honeypot removal)
- `ChubbsAdmin/index.html` — admin portal
- `ChubbsMobileApp_v5/CPI Handbook.pdf` — authoritative scoring rules
- `qa/` — Python QA harness + matchplay engine sanity tests
- `NewFeatures/wechat-blast-may23-playoffs.md` — message draft
- `NewFeatures/v5.52-ui-cleanup-plan.md` — UI restructure plan
- `docs/firebase-rules.md` — current Firebase rules + apply instructions
- `season-3.json` (untracked) — extracted S3 data for QA
- `extract_season3.py` (untracked) — S3 extractor
