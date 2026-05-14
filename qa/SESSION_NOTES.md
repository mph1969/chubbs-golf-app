# Session Notes — last touched 2026-05-14

State at end of day. Pick up from **OPEN ITEMS** below.

## Today's session (2026-05-14) — admin parser + Tier 2c shipped end-to-end

| Version | What |
|---|---|
| Admin | WeChat parser overhaul + roster identity layer (aliases, Levenshtein matcher, stable playerIds, Merge-into-existing modal UI) |
| Admin | Parser T1 — FRI/SAT/SUN labels, Matchplay/MP keyword, 12h→24h time, inline handicaps, status synonyms, sender-prefix skip |
| Admin | Parser T2 — scramble team blocks, stableford groups, Palm A/B (Lychee/Lake/River) |
| Admin | Parser T3 — challenge-hole assignments for both days |
| Admin | Parser T5 — playoff-event harvest (bracket lines + Fireball Cup roster) |
| Admin | Date parser fix — `(?!\d)` lookahead to stop eating year digits; prefer dd-dd-month over month-first |
| Admin | From Bracket name reconciliation uses `findPlayerByAnyName` |
| Admin | 3-Putt Poker default flipped to OFF in `buildEventBundle` |
| Admin | Clear Setup preserves roster + cloud data (was nuking both silently) |
| Admin | Push-confirmation modal surfaces playoffs status ("🏆 Playoffs: 16/16 seeds" or "NOT included") |
| v5.69 | Bracket-tree QF/SF/Final align to R16 midpoints via flex space-around |
| v5.70 | 4 stacked ladders rendered (Cup / Plate / Shield / Spoon) |
| v5.71 | Compact lower-tier ladders + hide until upstream results land |
| v5.72 | Back-9 Foursomes card on Standings tab + brain-trust scorer rule |
| v5.73 | Brain trust order updated: Terry → Jack S → Ryan N → Nick → Hanson → Matt |
| v5.74 | **Tier 2c-1** — score view auto-swaps to back-9 foursome on hole 10+ |
| v5.75 | **Tier 2c-2** — back-9 matchplay banner with Cup QF + Plate QF status |
| v5.76 | Back-9 banner matches by playerId (robust to displayName edits/aliases) |
| v5.77 | **Tier 2c-4** — Firebase sync writes back-9 to its own group node with `half:'back9'` |
| v5.78 | **Tier 2c-4b** — back-9 banner reads via Firebase for non-scorer phones |
| v5.79 | Pre-hole strokes chip always shows; match-container robust to null seeds |
| v5.80 | Score number font bumped to match +/− buttons |
| v5.81 | Leaderboard R16 status case-insensitive lookup |
| v5.82 | Stepper +/− no-shift; Leaderboard closed-match shows winner name; `chubbsTest.seedsOnly()` |
| v5.83 | Sub-tab memory; "Match-Play" label on day2 when seeds locked; tap-target stability for chip/outcome slots |
| v5.84 | Sub-tab memory snapshot on group switch (fixes v5.83 missed-path bug) |

Plus:
- `qa/r16_to_qf_sim.py` — front-9 → back-9 transition harness, 3 scenarios (chalk / all_square_m1 / mixed_upsets), bracket save-state + cascade invariant assertions. 3/3 pass.
- `qa/back9_card_fixture.js` — DevTools console fixture exposing `chubbsTest.{seedsOnly, chalk, upsets, allUpsets, custom, fillEmptyR16, status, bracketStatus, firebaseGroups, clear}`
- Roster seeds: PENGLEI / PAUL / DUSTIN added to `baseRosterData`, handicap refresh for the May 23 team draft, stray RYAN merged into RYAN N via migration

## Validation status (post-2026-05-14)

| Layer | Status |
|---|---|
| Stableford scoring engine | ✅ 211/212 S3 player-events match Terry's spreadsheet |
| Match-play engine | ✅ 11/11 sanity tests pass (qa/matchplay_engine.py) |
| R16 + back-9 reshuffle math | ✅ 3/3 scenarios pass (qa/r16_to_qf_sim.py) |
| Cascade invariants (cup_qf winner ∈ R16 winners; plate_qf winner ∈ R16 losers) | ✅ asserted by harness |
| Pre-event readiness audit (2026-05-10) | ✅ A1–A8 done, A4 bug fixed in v5.58 |
| Firebase rules + indexOn | ✅ Confirmed published 2026-05-14 — matches docs/firebase-rules.md |
| End-to-end dry-run on phone w/ v5.84 | ⏳ Pending; v5.83 + v5.84 dry-run confirmed sub-tab memory works |

## OPEN ITEMS — pick up here

### 1. Send WeChat blast (~May 16 — 2 days)
Draft in `NewFeatures/wechat-blast-may23-playoffs.md`. Attach 2-3 screenshots from dry-run.

### 2. Final phone dry-run before May 23 — Brain Trust testing
- Multi-phone test: at least 2 devices loading the same event as different players
- Verify Firebase sync of back-9 group nodes across phones
- Stress-test: enter through hole 18 + save all Cup QF + Plate QF results
- Verify Standings tab bracket tree updates live as results land

### 3. Production push of May 23 event (LIVE flag, not TEST)
Currently testing with "(TEST) May Chubbs at Yinli" event. Day-of: switch admin Event Mode → LIVE EVENT, push fresh.

## Deferred to post-May 23

- Mobile-side event-header playoffs indicator chip ("🏆 Playoffs locked · 16 seeds") — proposed for load-side mistake protection
- John B / Mike H / case sensitivity edge cases in roster (the JOHN-with-hcp-1 quirk)
- Bracket-via-Firebase sync (would remove admin-re-push friction)
- Twosome detection
- S3 history bake-in
- Auto-Register + Auto-Load (NewFeatures/auto-register-and-auto-load-spec.md)

## Useful copy-paste snippets

### Latest QA fixture
See `qa/back9_card_fixture.js` for the full version (copy-paste into DevTools console).

### Inject seeds only for live test
```javascript
chubbsTest.seedsOnly()  // clean slate, no pre-saved R16
```

### Fill empty R16 slots so back-9 swap activates during solo testing
```javascript
chubbsTest.fillEmptyR16()  // preserves any actually-saved Mn results
```

### Diagnostic during play
```javascript
chubbsTest.firebaseGroups()   // list all /events/{eid}/groups nodes with half flag
chubbsTest.bracketStatus()    // r16/cup_qf/plate_qf saved buckets
chubbsTest.status()           // local seeds + r16 state
```

### Run QA harness from repo root
```bash
python qa/r16_to_qf_sim.py                       # all 3 scenarios
python qa/r16_to_qf_sim.py --scenario=chalk      # one scenario
python qa/matchplay_engine.py                    # 11 unit tests
python qa/playoff_sim.py                         # bracket cascade sim
```

## Confirmed locked rules (2026-05-10)

- Match-play model: lower NET wins each hole; full hcp differential to higher-hcp player
- 9-hole match tiebreak: Stableford → lower hcp → arm wrestle (handbook §11)
- Season-standings tiebreak: best-7 → round-avg desc → seedPoints desc → stableford desc
- Playoff seeding tiebreak: seedPoints → round-avg desc → stableford desc
- Brain trust (default scorer priority, Diego excluded from fallback): Terry → Jack S → Ryan N → Nick → Hanson → Matt
- Back-9 reshuffle: Cup A = M1–M4 winners; Cup B = M5–M8 winners; Plate A = M1–M4 losers; Plate B = M5–M8 losers

## Files

- `ChubbsMobileApp_v5/index.html` — mobile PWA (~8700 lines after Tier 2c)
- `ChubbsAdmin/index.html` — admin portal (parser overhaul + push modal + Clear-Setup fix)
- `ChubbsMobileApp_v5/CPI Handbook.pdf` — authoritative scoring rules
- `qa/r16_to_qf_sim.py` — R16→QF transition harness (NEW today)
- `qa/back9_card_fixture.js` — DevTools console fixture (NEW today)
- `qa/matchplay_engine.py` — match-play engine sanity tests
- `qa/playoff_sim.py` — bracket cascade simulation
- `qa/season4_qa.py` — Stableford engine validation vs Terry's S4 spreadsheet
- `NewFeatures/wechat-blast-may23-playoffs.md` — Wechat message draft
- `docs/firebase-rules.md` — current Firebase rules + apply instructions
