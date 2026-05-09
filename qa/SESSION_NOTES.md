# Session Notes — 2026-05-09

State at break. Pick up from any of the **OPEN ITEMS** below.

## What shipped today

| Version | What |
|---|---|
| v5.46 | Course-library audit vs Terry's Season 4 sheet — Birds par/SI fixed (H7/H9 swapped, all 18 SI rewritten); Tangspring + Qingyuan loaded from Jan/Mar sheets. Yinli, Mountain, Valley, Gaoming were already correct. Qingyuan has a flagged note about a duplicate-9-SI guess — confirm with pro-shop card. |
| qa/ harness | `season4_qa.py` + `playoff_sim.py` committed (both runnable from repo root). 110/111 player-events match Terry's stableford. Three single-point standings deltas all explained (2 tiebreak swaps + 1 Terry hand-sum slip). Best-7 vs sum-of-all give identical S4 bracket. |
| v5.47 | Match-play engine helpers — `matchPlayStrokes`, `matchPlayHoleWinner`, `matchPlayStatus`. 8 sanity tests in `qa/matchplay_engine.py`. |
| v5.48 | Match-play overlay banner on score view — live status per match in the foursome. |
| v5.49 | Auto-push closed match to bracket — admin one-tap "Save M{N} to bracket" button when match closes. |
| v5.50 | Per-hole net comparison hint — shows `H6 (par 4, SI 3) · Jordan: 5−2=3n · Ricardo: 5=5n → Jordan wins H6`. |
| v5.51 | §11 tiebreak surface — when match is ALL SQUARE thru 9, banner shows Stableford → lower-hcp → arm-wrestle resolution + save button. |
| v5.52 | UI cleanup phase 0 — hide Playoffs tab for non-admin unless seeds locked; drop 📅/🏆 emojis. Plan for fuller restructure in `NewFeatures/v5.52-ui-cleanup-plan.md`. |

All pushed to `mph1969/chubbs-golf-app` master.

## OPEN ITEMS — pick up here

### 1. Terry WeChat reply on tiebreak rule
WeChat message drafted. Waiting on Terry to confirm: app's locked **played-desc**
(per his own 2026-04-29 lock) vs his current spreadsheet's **round-avg** tiebreak.
Affects only seeds 7/8 (Terry-the-player vs Dustin) — moves the QF opponent from
Nick to Matt D for whoever sits at seed 8. Bracket cut line and 14 of 16 seeds
unchanged either way.

### 2. Lock playoff seeds via admin tool
Once Terry confirms, use the admin app (chubbs-admin.netlify.app) to:
- Load May Yinli event bundle
- Mark Mike W / Diego / Anthony as withdrawn (Fireball Cup)
- Run "Lock Playoff Seeds"
- Push to Firebase

This replaces the localStorage hack we discussed. Do this BEFORE the May 23
event.

### 3. Dry-run matchplay UX on phone
You started this just before the break — got the v5.51 deploy showing in
Chrome, pasted the seed-injection snippet, saw 4 pre-existing console errors
(all harmless — see triage in chat). The active screen was the April Palm
Island event with players KEVIN / MATT / JACK S / HANSON, which doesn't
contain any R16-pair (1+16, 8+9, 5+12, 4+13, 3+14, 6+11, 7+10, 2+15) → banner
correctly empty.

**Resume here:** start a fresh round at Yinli course with these test players
(exact names matter for seed-name matching):
- Matt D (hcp 12)
- Andy (hcp 30)
- Nick (hcp 28)
- Jamie (hcp 20)

This foursome contains M1 (Matt D vs Andy) + M8 (Nick vs Jamie). Tap into
Stableford → banner appears. Enter scores hole-by-hole and watch updates.
Force a match to close at H5 → admin "Save to bracket" button appears.
Force ALL SQUARE thru 9 → tiebreak surface appears.

### 4. UI cleanup — bigger restructure
v5.52 just shaved the obvious noise (emojis, year-round Playoffs tab). The
proposed Phase 1 consolidates 7 tabs to 4 via sub-segmented pills:
- **Round** (Stableford / Scramble / My Card / 3-Putt Poker)
- **Leaderboard**
- **Standings** (Season / Playoffs)
- **Me/Setup**

Full plan: `NewFeatures/v5.52-ui-cleanup-plan.md`. Phase 1 is the biggest
payoff but also the riskiest because Score view has many callers. Estimated
3-4 hrs of work.

### 5. Phase 2 matchplay features (lower priority)
- Designated scorer mode — admin marks 1 of 4 in each foursome as scorer; that
  phone gets entry UI, others get read-only display. Biggest adoption play.
- Twosome detection — handle 2-some matches if any
- "Concede" button — hole or match concession (common matchplay action)

### 6. Onboarding / training (no code, just content)
- One-page WeChat blast 1 week before May 23: screenshot of banner + 3-bullet
  pitch ("designated scorer per group · live matchplay status · auto-Stableford")
- First-launch toast on the playoff bundle

### 7. Cosmetic bugs in `sw.js` (low priority)
Two console errors observed:
- `'put' on 'Cache': Request method 'POST' is unsupported` — SW trying to
  cache Firebase POST writes. Add a method-check guard in the fetch handler
  before `cache.put`. ~5 lines.
- `'put' on 'Cache': Request scheme 'chrome-extension' is unsupported` — same
  fix; add a scheme check.

Both are harmless but pollute the console.

### 8. Firebase index warning
`@firebase/database: FIREBASE WARNING: Using an unspecified index ... bundle/_publishedAt at /events`. Fix in Firebase Realtime DB rules:
```json
"events": {
  ".indexOn": "bundle/_publishedAt"
}
```

## Useful copy-paste snippets

### Inject test playoff seeds (browser console)
```javascript
const store = JSON.parse(localStorage.getItem('chubbs_seasons_v1') || '{}');
if (!store.seasons) store.seasons = {};
if (!store.seasons['season-4']) store.seasons['season-4'] = { id:'season-4', name:'Season 4 (2025–2026)', events:[], status:'active' };
store.seasons['season-4'].playoffs = {
  seeds: ['Matt D','Nick','Jordan','George','Ryan N','Leigh','Terry','Dustin','Paul','John','Hanson','Kevin','Jack','Ricardo','Jamie','Andy'],
  seededAt: '2026-05-09'
};
store.viewingSeasonId = 'season-4';
localStorage.setItem('chubbs_seasons_v1', JSON.stringify(store));
localStorage.setItem('cpi_master', '1');
location.reload();
```

### Reset (remove test seeds + admin)
```javascript
localStorage.removeItem('chubbs_seasons_v1');
localStorage.removeItem('cpi_master');
location.reload();
```

### Run QA harness
```bash
python qa/season4_qa.py                       # standings diff vs Terry
python qa/season4_qa.py --per-event --exclude=apr-palm   # per-event drilldown excluding April
python qa/playoff_sim.py                      # full bracket sim under app rule
python qa/playoff_sim.py --terry-order        # under Terry's round-avg rule
python qa/playoff_sim.py --best7              # under best-7 primary
python qa/matchplay_engine.py                 # 8 sanity tests on engine helpers
```

## Confirmed assumptions (2026-05-09)

- Match-play model: lower NET wins each hole; full hcp differential allocated
  by SI (lowest first). Pending Season 3 historical-data verification when
  that data arrives.
- Tied-at-9 tiebreak: Stableford → lower hcp → arm wrestle (handbook §11).
- Playoff seeding: sum-of-all-rounds (`seedPoints`), per Terry 2026-04-28
  lock. Best-7 produces identical S4 bracket so this isn't tested next season
  yet.
- Cut-line tiebreak: played desc → seedPoints desc → stableford desc, per
  Terry 2026-04-29 lock. Currently disagrees with Terry's spreadsheet
  (round-avg) — see open item #1.
- 16-player playoff field after withdrawals: Mike W (won't play), Diego +
  Anthony (Fireball — missing June). Tony, Pos, Matthew SA, PLZ, Graeme also
  in Fireball (not qualified or missing June).

## Files you'll want open

- `ChubbsMobileApp_v5/index.html` — main app (mobile PWA)
- `ChubbsMobileApp_v5/CPI Handbook.pdf` — authoritative scoring rules
- `qa/season4_qa.py` — standings QA harness
- `qa/playoff_sim.py` — bracket simulation
- `qa/matchplay_engine.py` — engine sanity tests
- `NewFeatures/v5.52-ui-cleanup-plan.md` — UI restructure proposal
