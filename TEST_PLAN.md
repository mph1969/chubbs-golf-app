# Chubbs — Pre-Event Test Plan

**Target event:** CPI April 25–26, 2026
**App version under test:** ChubbsMobileApp_v5/index.html + sw.js (~5,808 LOC mobile, ~2,071 LOC admin)
**Scope:** every code path that can affect a player's score, leaderboard position, or the integrity of the event bundle.

This plan is organized by *code area*, not by feature. Each section names the functions the test exercises, cites the line ranges in `ChubbsMobileApp_v5/index.html`, states expected behaviour derived from the code, lists concrete inputs, and calls out edge cases. Run in order — later tests assume earlier ones passed.

Legend: 🔴 must-pass before event · 🟡 high value but can be triaged · 🟢 nice-to-have

---

## 0. Setup: what you need before starting

- Two test devices (or one device + one incognito window). Call them **Scorer** and **Viewer**.
- A third device with the admin tool open (`ChubbsAdmin/index.html`). Optional but recommended.
- Network available — Firebase sync is a load-bearing dependency. Tests require it unless marked "offline."
- Test event in admin set to **Test mode** (`eventMode === 'test'`) so production events stay clean.
- Clear device localStorage before starting Block A (`localStorage.clear()` in devtools) so migration logic runs cleanly.

---

## Pre-Event Access Verification 🔴🔴
> The single most important checklist for game-day reliability. Run on the **actual phones** that Michael and Terry will use on Saturday morning. The other blocks test app correctness; this one tests **whether you can get to the event at all**.

Covers: `pingVerifyHit` + `cacheBundle` + `loadFromCache` (mobile, post-`_doApplyBundle`), `showVerifyMobile` (admin).

### V1. T-7 days — Real-device dress rehearsal 🔴
Run this once for each admin (Michael + Terry), on each admin's game-day phone.

1. In admin (desktop): event mode = **🟢 LIVE**. Hit **☁️ Send to App**.
2. On admin's phone (Safari/Chrome — the one going to the course): open `https://chubbs-golf.netlify.app/`.
3. Confirm cloud-events list shows the event with a **🟢 LIVE** chip prefix. Tap the event.
4. Pick your name from the player picker → load.
5. Navigate to scorer screen for both Day 1 and Day 2. Confirm:
   - Your name appears as scorer (or you're a viewer if you're not the assigned scorer).
   - Hole numbers, par, SI, challenge badges all render.
   - Master mode PIN works (Settings → enter PIN → toggle).
6. Enter and immediately delete a test score.
7. Don't clear browser data on this phone for the next 7 days.

**Expected state after V1:** Bundle is in this device's `chubbs_mobile_event_cache_v1` localStorage. Service worker is registered. You're logged in as the right player.

### V2. T-7 days — End-to-end fetch verification 🔴
On admin (desktop) immediately after V1: click **🩺 Verify Mobile Access** in header.

1. Modal opens with instructions and live status.
2. On phone: refresh the page or re-load the event from cache.
3. Within ~2 seconds the admin modal should tick **✅ N mobile fetches confirmed** with the device's user-agent.
4. Have Terry do the same on his phone — admin should see two separate hits.

**Failure modes to look for:**
- ❌ "No mobile fetches in 60s" → phone has no internet, OR Firebase rules blocked the write, OR event not published. Check **Send to App** status.
- Hits arrive from one phone but not the other → second phone has connection issue or stale cache.

### V3. T-7 days — Offline cache fallback 🔴
On admin's phone, after V1 succeeded:

1. Turn on Airplane Mode.
2. Reload the live URL.
3. Cloud scan should fail/timeout → **📦 Cached Events** card should still appear with the bundle in it.
4. Tap the cached entry → confirms load. Scorer screen should render.
5. Turn Wi-Fi/cellular back on. Firebase sync resumes automatically.

**Expected:** App is fully usable offline once the bundle is cached. Scores entered offline will sync when connection returns.

### V4. T-1 day (Friday) — Full re-verify 🔴
1. Admin: re-run **✅ Game Day Check** in admin header. All rows green except dates (warn OK if needed).
2. Admin: re-run **🩺 Verify Mobile Access**. Both phones must register a hit.
3. Both admins: download the latest event JSON via admin **💾 Export JSON** → save to your phone's Files app as backup. Filename will be `{eventId}-LIVE-{YYYYMMDD}.json` — easy to identify.
4. Confirm Master PIN is written down somewhere outside the app (Notes app or paper). Both admins should know it.

### V5. T-30 minutes Saturday morning — Final sanity 🔴
1. First admin to arrive at the course: load the live URL on phone.
2. If cloud scan works → load event normally.
3. If cloud scan is slow (>10s) → tap from **📦 Cached Events** card instead.
4. Confirm scorer screen renders. Confirm score lock countdown is correct.
5. **Don't touch admin during the round** unless required — every "Send to App" overwrites the cloud bundle.

### V6. Mid-round emergency recovery 🟡
If a player reports "I can't load the event":

1. **Triage in this order:**
   - Their phone has internet? (try a website)
   - They're using the right URL? (`chubbs-golf.netlify.app`)
   - The cloud-events scan is empty? → admin's bundle isn't published or got purged.
   - They picked the wrong player ID? → reload, pick correct name.
2. **Last resort:** WeChat them the event JSON file. They use **📥 Import from file** on the join screen.
3. **Don't re-publish the bundle from admin** mid-round unless absolutely necessary — it triggers an "update available" banner on every other player's device and risks state confusion.

### V7. Both admins must have viewed the LIVE event before Friday EOD 🔴
This is the single most important pre-flight: if both Michael and Terry have successfully loaded the LIVE event on their game-day phones at least once, the bundle is cached locally and Firebase sync token is established. Even if the venue Wi-Fi is dead Saturday morning, the cached bundle loads instantly.

---

## Block A — Event Bundle Import 🔴

Covers: `importEventBundleText`, `importEventBundleFile`, `applyImportedEventBundle`, `_doApplyBundle` (lines 1682–1830), `normalizeEventBundle` (line 1200), `migrateState` (line 1103).

### A1. Valid bundle import (admin JSON export → mobile)
1. In admin, click **Export JSON** on a complete test event.
2. On mobile Setup tab, upload the file.
**Expected:** `hasImportedEvent()` returns true · setup screen shows "Event loaded" · tabs render in order (Scramble→Stableford if `scrambleBeforeStableford()` returns true, line 3258). · `state.eventBundle.players`, `day1ScrambleTeams`, `day2Groups`, `day1Challenges`, `day2Challenges` are all present.

### A2. Bundle with no scramble challenges
**Expected:** Page renders · `renderChallengesCard()` (line 2274) returns `''` · no "Hole Challenges" card appears on leaderboard.

### A3. Bundle with only stableford challenges, no scramble scores yet
**Expected:** `getChallengesForHole(holeIdx, 'scramble')` returns [] · scramble scorecard shows no badges · stableford badges still appear once scores exist.

### A4. Palm Island front/back combo migration (line 1105)
Import a legacy bundle that has `courseId` but no `roundCourses`.
**Expected:** `migrateState` creates `roundCourses.day1` and `day2` from legacy `palmIsland`, clamps front/back to {A,B,C}, forces back ≠ front.

### A5. Bundle with invalid player IDs 🟡
Hand-edit JSON so one player.playerId is numeric / null / duplicate.
**Expected:** App doesn't crash. `findEventPlayerCatalog` (line 1167) handles it. `hydrateLineupPlayers` (line 1171) falls through for missing IDs.

### A6. Re-import over an existing event (line 1244)
**Expected:** `applyImportedEventBundle` preserves requested playerId if passed · otherwise re-prompts.

### A7. Pending event banner (line 1001, `checkPendingEvent`)
Publish a new bundle from admin while the mobile app is on an older bundle.
**Expected:** Banner offers `importPendingEvent(eid)` · `dismissPendingEvent()` hides banner.

### A8. 🔴 **Firebase event scan** (`scanCloudEvents`, line 1841)
On mobile setup, tap "Scan cloud events". Verify you see the test event and can `confirmCloudLoad(idx)`.
**Edge:** with `eventMode === 'test'` vs `live`, cross-check `_isTest` flag on bundle (see admin test-runner EB7–EB9, test-runner.js line 99).

### A9. Join-code deep link (lines 1962–1985)
Use the join URL with hash. Verify `applyJoinHash` decodes and loads.

### A10. Event bundle too large / corrupt JSON
Paste malformed JSON into the text field.
**Expected:** `importEventBundleText` shows error toast · state unchanged.

---

## Block B — Scorer / Viewer Roles 🔴

Covers: `isCurrentPlayerScorer` (line 2477), `isScoreLocked` (line 2490), `lineupScorerId` (line 2114), `setLineupScorer` (line 2126), `toggleMasterMode` (line 764).

### B1. 🔴 Assigned scorer can enter scores
Bundle assigns `scorerPlayerId` for a team/group; open mobile as that player.
**Expected:** Score steppers active. `isCurrentPlayerScorer('scramble')` returns true.

### B2. 🔴 Non-scorer is view-only
Open the same team on a second device as a different player.
**Expected:** `isScoreLocked('scramble')` returns true · toast "👁 View only — scramble scorer enters scores" · `stepScore` (line 2500) returns early.

### B3. Master mode bypass
Enable master/admin via PIN (line 782, `loadAdminPin`), call `toggleMasterMode()`.
**Expected:** `isCurrentPlayerScorer` returns true regardless of lineup scorer.

### B4. Scorer change mid-round
Admin calls `setLineupScorer('day2', groupId, newPlayerId)`.
**Expected:** New scorer's device unlocks · old scorer's device locks on next render.

### B5. Manual mode (no bundle) 🟡
`hasImportedEvent()` false → `isCurrentPlayerScorer` returns true for everyone. Verify scoring works without an event.

### B6. Missing `eventPlayerId`
`state.eventPlayerId` empty but bundle imported.
**Expected:** Falls through "legacy" path at line 2481 — allow all.

---

## Block C — Score Lock (Time-gated) 🔴

Covers: `getScoreLockStatus` (line 2695), `toggleScoreLockOverride` (line 2748), score lock broadcast via Firebase (line 2753).

### C1. 🔴 Before unlock window
Set event `satDate`/`satTime` to a future date with tee time >2 h away.
**Expected:** Lock active · reason says "Scramble scoring opens Xh Ym before tee time" · countdown visible · steppers disabled.

### C2. Within unlock window (≤ 2 h before tee)
Set tee time to 1 h from now.
**Expected:** Lock released · countdown gone · steppers active.

### C3. Post-event auto-unlock
Set tee time to yesterday.
**Expected:** Midnight-after-event reset kicks in at line 2733 · lock off.

### C4. 🔴 Admin override
On one device, call `toggleScoreLockOverride()` during locked window.
**Expected:** Firebase broadcasts to `/events/{id}/scoreLockOverride` (line 2753) · all connected devices unlock simultaneously.

### C5. Per-group tee time
Bundle `day2Groups[n].teeTime` is set; event `sunTime` is different.
**Expected:** Group's tee time takes precedence (line 2710).

### C6. Missing date → no lock
`satDate` empty.
**Expected:** `getScoreLockStatus` returns `{locked:false}` (line 2713).

---

## Block D — Scramble Scoring 🔴

Covers: `stepScore('scramble', ...)` (line 2500), `setBlob`, `setDriver` (line 2579), `scrambleTotals` (line 2349), scramble hole validation in `navHole` (line 2611).

### D1. 🔴 Team score stepper
Enter gross 4 on par-4 hole 1. Increment once. Decrement once.
**Expected:** `state.scramble.holes[0].gross === 4` · clamp at ≥ 1 (line 2507).

### D2. 🔴 Driver selection
Tap each player tile. Verify `state.scramble.holes[h].driver` toggles 0–3 or back to null on repeat tap.

### D3. 🔴 Advance without score
Tap **Next** without entering gross.
**Expected:** Modal "🏌️ Enter the team score" (line 2615) · hole does not advance.

### D4. 🔴 Advance without driver
Enter gross, don't tap a driver, tap Next.
**Expected:** Modal "🚗 Select whose drive was used" (line 2616).

### D5. Drive minimum enforcement (post-round)
Enter scores for all 18. Make one player's drive count lower than `getMinDrives()` (default 4 for 4-player, 5 for 3-player — see admin test-runner S3/S4, line 85–87).
**Expected:** Leaderboard / export flags "⚠️" status on drive tracker (noted in memory project_sprint_plan).

### D6. 🟡 Team size 2 (2-person scramble)
Admin sets `scrambleTeamSize=2`, `defaultDrivesForSize(2) === 8`. Verify the app picks up the minDrives from bundle options.

### D7. 🟡 Starting hole rotation
Set starting hole to 10. Play through. Verify `playOrderToHoleIdx` / `holeIdxToPlayOrder` (lines 2324–2329): physical hole 10 shows first, after 17 → 18 complete message.

### D8. Scramble total against par
After 9 holes scored, confirm `scrambleTotals().total`, `parEntered`, `toPar` match manual calc.

### D9. Edge: score of 1 (hole-in-one)
**Expected:** Allowed (no upper cap). `scoreColorClass(1, par)` shows eagle tier.

### D10. Edge: very high score
Step score up past 15. Verify no crash. No penalty, just a large number.

---

## Block E — Stableford Scoring (Critical Math) 🔴🔴

Covers: `shotsReceived` (line 2168), `stablefordPoints` (line 2174), `playerTotals` (line 2405), `suggestPutts` (line 2523).

### E1. 🔴🔴 **Stableford formula correctness**
This is the single most important block. Reference formula from code:

```
shots = floor(hcp/18) + (si ≤ hcp%18 ? 1 : 0)
net = gross - shots
points = (net ≤ par-2) → 4
         (net == par-1) → 3
         (net == par)   → 2
         (net == par+1) → 1
         else           → 0
```

Enter each of the following rows on a par-4 SI-9 hole (pick any hole with those values from your course). Use HCP 18 → shots=1.

| Gross | Net | Expected pts | Formula check |
|-------|-----|--------------|----------------|
| 2 | 1 | 4 | diff=−3 → 4 (capped at 4) |
| 3 | 2 | 4 | diff=−2 → 4 |
| 4 | 3 | 3 | diff=−1 → 3 |
| 5 | 4 | 2 | diff=0 → 2 |
| 6 | 5 | 1 | diff=+1 → 1 |
| 7 | 6 | 0 | diff=+2 → 0 |
| 8 | 7 | 0 | diff=+3 → 0 |

### E2. 🔴 High handicap — two strokes received
HCP 28, par-4 SI-5. `shots = 1 + (5 ≤ 10 ? 1 : 0) = 2`. Gross 6 → net 4 → 2 pts.

### E3. 🔴 High handicap — no stroke
HCP 28, par-3 SI-17. `shots = 1 + (17 ≤ 10 ? 1 : 0) = 1`. Gross 4 → net 3 → 2 pts.

### E4. 🔴 Plus handicap
HCP -2. `Math.max(0, -2) = 0` shots (line 2169). Gross 4 on par-4 → net 4 → 2 pts. ⚠️ **Plus players are not penalized by this code** — if that matters for your comp, flag it.

### E5. 🔴 Hcp 36 exactly
`shots = floor(36/18)=2, rem=0, always 2`. Every hole gets 2 shots.

### E6. 🔴 Hcp 0
Zero shots everywhere. Net = gross.

### E7. Blob
Tap **Blob** on par-3 → gross=7 (line 2568). Par-4 → gross=8. Par-5 → gross=10. Verify `setBlob` triggers `fireSpennyAlert`. Points should be 0.

### E8. 🔴 Putt suggestion
Enter gross without touching putts. `suggestPutts` (line 2523): `gross<=1 → 0, gross<par → 1, else → 2`. Verify auto-fill respects `state.options.threePuttPoker` flag (disabled → no suggestion).

### E9. `playerTotals` correctness (line 2405)
Score all 18 holes for one player with mixed pars/SIs. Hand-compute total points. Compare to `playerTotals(idx).points`. Also verify `back9` sum matches holes 9–17 (0-indexed, lines 2418).

### E10. 🟡 Partial round (9 holes)
`entered === 9`, not 18. Leaderboard should still render. `playerTotalsFromRemote` (line 1052) handles partial.

### E11. 🔴 handicapAdjustment display (line 2184)
Points tiers:
- `> 45` → −3
- `41–45` → −2
- `36–40` → −1
- `27–35` → No change
- `16–26` → +1
- `<16` → +2

Test values: 46 → −3, 41 → −2, 40 → −1, 36 → −1, 35 → No change, 27 → No change, 26 → +1, 16 → +1, 15 → +2, 0 → +2. ⚠️ **Note** the boundaries: 41→−2 but 40→−1, 36→−1 but 35→No change. Off-by-one risk — verify the displayed HI change on the summary card matches the table.

### E12. Edge: missing par or SI
Course hole with par=null. `playerTotals` skips that hole (guard `Number.isInteger(...)` at line 2412). Total should not include it.

---

## Block F — Three-Putt Poker 🟡

Covers: `currentHolePokerEffect` (line 2363), `pokerSummary` (line 2430), `syncPenaltyStamp` (line 2461), `effectiveLastPenaltyPlayerForHole` (line 2379).

### F1. Putts mapping
- 0 putts → +2 cards, no penalty
- 1 putt → +1 card
- 2 putts → nothing
- 3 putts → penalty3 RMB
- 4+ putts → penalty4 RMB

### F2. 🟡 Last-putt penalty override
Two players both at 3+ putts on the same hole. Both appear in `penaltyPlayersForHole`. Without override, most recent stamp wins (line 2384 loop). Tap override button on the other player and verify `lastPenaltyOverride` persists.

### F3. `pokerSummary` pot calculation
4 players × ante 50 + all penalties + double-ante on last penalty player. Hand-calculate the pot and compare.

### F4. Stamp counter monotonic
Increment putts to 3 on hole 1, then hole 5, then back to hole 1. Verify `puttStamp` array preserves chronological order (`stampCounter` increments, line 2467).

### F5. Clearing a 3+ putt resets stamp
`clearScore('stableford', idx, 'putts')` or step down to 2 putts.
**Expected:** `puttStamp[playerIdx] === null` · removed from penalty list.

### F6. `digitalDeal` invalidation
Any score change should null `state.poker.digitalDeal` (lines 2518, 2545, 2559). Verify if you're using digital deal mode, re-deal happens after edits.

---

## Block G — Leaderboard 🔴

Covers: `leaderboardPlayers` (line 816), `playerTotalsFromRemote` (line 1052), `renderLeaderboard`, `revealDay1` (line 810).

### G1. 🔴 Local group shows with live data
With scores entered on local device.
**Expected:** Leaderboard lists your group with `source: 'local'` · points match `playerTotals`.

### G2. 🔴 Remote group via Firebase
Second device scores a different group. First device leaderboard.
**Expected:** `source: 'remote'` · points computed via `playerTotalsFromRemote` using the remote bundle's hcp.

### G3. 🔴 `source: 'none'` placeholder
Player in bundle is in a group that has no scoring device online yet.
**Expected:** Row shows with 0 points, entered=0 (line 848).

### G4. Badge merging
Roster entry has `goldJackets: 2`, `clownJackets: 1`. Leaderboard row shows both counts.

### G5. 🟡 Ordering / sort stability
Two players tied on points → back9 countback → `entered` → name. Verify wherever your sort lives.

### G6. Day 1 reveal toggle (line 810, `revealDay1`)
Admin toggles leaderboard reveal flag during Saturday play.
**Expected:** Firebase `/events/{id}/leaderboardRevealed` updates · all devices hide/show scramble standings.

### G7. 🟡 HCP discrepancy warning
Bundle hcp differs from locally edited hcp. `playerTotalsFromRemote` uses remote bundle's hcp. Verify there's no silent mismatch — a player's point total should not change based on which device renders the leaderboard.

---

## Block H — Firebase Sync 🔴

Covers: `initFirebase` (line 884), `initSync` (line 900), `pushToFirebase` (line 976), listeners at lines 926–951.

### H1. 🔴 Score write propagation
Scorer enters hole 1 gross. Viewer sees it within ~2 s.

### H2. 🔴 Group vs team write paths
Scramble updates write to `/events/{id}/teams/{tid}` (line 991). Stableford writes to `/events/{id}/groups/{gid}` (line 984). Cross-check both.

### H3. Listener teardown on event change
Switch to a different event. `syncTeardown` (line 892) should remove all listeners. No zombie `on('value')` callbacks firing.

### H4. 🔴 Challenge winner propagation
Admin sets a challenge winner (`setChallengeWinner`, line 2226). Verify Firebase write to `/events/{id}/challengeWinners` (line 2232) and that all devices' `state.challengeWinners` updates (listener at line 948).

### H5. Money Hole pot syncs
`setMoneyHolePot(1000)`. Verify `_moneyHolePot` key is in the Firebase object (line 2238). All devices see the pot.

### H6. Read-only mode
Set `readOnlyMode = true`. Attempt a score change.
**Expected:** `pushToFirebase` returns early (line 977). Local state still updates? (Verify behaviour — depends on intent.)

### H7. 🔴 90-day auto-cleanup
Not directly testable in 3 minutes. Verify the code path: `cleanupOldEvents` (line 955) queries old events and deletes those with `_publishedAt < cutoff`. At minimum, confirm the function fires on boot (line 974, 8 s delay).

### H8. Permission error
Simulate rule denial (firebase console temporarily restricts writes).
**Expected:** Catch blocks at lines 917, 990, 998 swallow errors. Sync badge goes `err`. App still works offline.

### H9. 🟡 Watcher link (`?watch=...`)
Lines 2003–2012. Open URL with watch param. Verify read-only leaderboard for non-participants.

---

## Block I — Starting Hole / Navigation 🟡

Covers: `showStartingHoleModal` (line 2658), `setStartingHole` (line 2757), `navHole` (line 2606), `getHoleOrder` (line 2332), `playOrderToHoleIdx` / `holeIdxToPlayOrder`.

### I1. Starting hole 10 → play order
`setStartingHole('stableford', 10)` → `order === [9,10,...,17,0,1,...,8]` · `displayHoleNum` returns actual course hole + 1.

### I2. Starting hole with existing scores
Score hole 1 first, then try to change starting hole.
**Expected:** `state[key].hole` does NOT reset because `hasScores === true` (line 2763).

### I3. Wrap-around at hole 17 → 0
On hole 17 (last in rotation for starting-hole=10), tap Next.
**Expected:** `playPos >= 17` toast at line 2633 · "Hole 18 complete!" · does not wrap.

### I4. Hole back past starting hole
`dir = -1` at playPos=0. `Math.max(0, ...)` clamps (line 2638). Stays on starting hole.

### I5. `skipHoleWarning` path
Enter incomplete data. Tap Skip →. Advances without validation (line 2648).

---

## Block J — Challenge Winners 🟡

Covers: `getChallengesForHole` (line 2198), `renderChallengesCard` (line 2274), `setChallengeWinner` (line 2226).

### J1. Badge appears on correct hole
Admin assigns challenge "B5" to Stableford. If day2 bundle has `day2PalmIslandFront='B'`, then B5 = course hole index 4. Verify `challengeBadgeHtml(4, 'stableford')` renders badge · `challengeBadgeHtml(0, ...)` doesn't.

### J2. Nine reassignment
Event `day2PalmIslandFront` changes from A to B in admin. Re-import bundle. Verify challenge hole index shifts.

### J3. Challenges don't show before scores exist
`hasD1Scores / hasD2Scores` flags at line 2281. Render nothing until any gross is entered.

### J4. Expanded when winner entered (line 2302)
Set a winner. Section expands with `details open`. Remove winner → collapses.

### J5. Multiple challenges on same hole
If two challenges point at the same hole code (e.g. CTP and Money Hole both on C4).
**Expected:** Both badges render side-by-side (map at line 2220).

---

## Block K — Export / CSV / JSON 🟡

Covers: `exportScrambleCsv` (line 2997), `exportStablefordCsv` (line 3024), `exportSummary` (line 3078), `exportFullEvent` (line 3117), `exportAwardsCard` (line 3211).

### K1. 🔴 Stableford CSV round-trip
Export CSV after a full 18-hole round. Open in Excel/Sheets. Verify:
- One row per hole per player + TOTAL row.
- `stableford_points` column matches `playerTotals(idx).points`.
- `net` = gross − shots_received.
- Header row matches line 3029 exactly.

### K2. 🔴 Scramble CSV team name required
No team name → toast error (line 3001). With team name → 18 holes + TOTAL.

### K3. Full event bundle export
`exportFullEvent` writes everything (bundle + scores + challenge winners). Round-trip import on another device.

### K4. Awards card export
Verify PDF/image export renders without cropping all gold jackets / clown jackets.

### K5. 🟡 Special-character names in CSV (`csvCell`, line 2849)
Names with commas, quotes, newlines. Verify quoting.

---

## Block L — PWA / Service Worker / Offline 🟡

Covers: `sw.js` cache versioning, install prompt, offline fallback.

### L1. SW registered
On first load, `navigator.serviceWorker.controller` becomes non-null within 2 s.

### L2. 🔴 Offline scoring
Toggle airplane mode mid-round. Enter scores.
**Expected:** `saveState()` still persists · `pushToFirebase` silently fails · scores restored on next online push.

### L3. SW cache version bump
Update `sw.js` version. Reload.
**Expected:** New cache installs · `updateViaCache:'none'` setting takes effect · old cache purged.

### L4. localStorage eviction recovery 🟡
(Same failure mode as DX!Golf roster loss.) Clear localStorage mid-event. Does the bundle reload from Firebase? Check `scanCloudEvents` path.

### L5. PWA install and launch from home screen
iOS + Android. Verify manifest icon, standalone mode, score persistence across app restarts.

---

## Block M — Admin Tool 🟡

Covers: `test-runner.js` already exists — **run it first**. Covers most admin UI checks.

### M1. 🔴 Paste the test-runner into the admin console
Open `ChubbsAdmin/index.html` → DevTools → paste `test-runner.js` → Enter.
**Expected:** All assertions pass (H1, H2, H4, H7, P1–P5, R1–R*, HCP-*, S1–S7, EB1–EB9, EC1, NR1–NR3, GD1, BL1–BL2, SH1, SG1).
**Current known:** The test-runner verifies roster shape, event bundle structure, scramble team size math — but it does NOT verify stableford formula or leaderboard correctness. Blocks D/E/G above cover that gap.

### M2. 🟡 Export/Import Config
Export config from admin → clear admin state → import → verify all fields restored.

### M3. 🟡 Nuclear reset
`executeNuclearReset` wipes admin state. Confirm admin confirms twice before nuking.

### M4. Master PIN on mobile
Set a PIN in admin → use it in mobile via `showAdminPinPrompt` / `doSetAdminPin` (lines 1548, 1585).

---

## Block N — Roster / Jacket Badges 🟡

Covers: `loadRoster` (line 1252), `upsertRosterPlayer` (line 1265), `renderJacketBadges` (line 1386), `seedJacketHistory` (line 1419), `upgradeRosterJackets` (line 1506).

### N1. Badge dot→emoji migration
Older rosters had dots. `upgradeRosterJackets` converts. Run migration manually, verify jacket counts preserved and display as 🧥🤡.

### N2. Gold jacket count reflects on leaderboard row
Award a gold jacket via roster form. Verify row's badges update on next render.

### N3. Scramble wins counter
After a scramble event, admin increments `scrambleWins` on a player. `renderJacketBadges` shows the count.

### N4. Roster JSON import/export (lines 1479–1505)
Round-trip a roster JSON. Verify no data loss. Edge: duplicate `playerId`, missing fields.

---

## Block O — Edge Cases & Gotchas

### O1. 🔴 Scramble-before-Stableford order (line 3258)
Event has `satDate = 4/26`, `sunDate = 4/25`. `scrambleBeforeStableford()` returns false. Tabs render Stableford→Scramble. Verify the flip is consistent everywhere (leaderboard, exports).

### O2. 🔴 A player appears in multiple groups (misconfig)
Admin accidentally assigns a player to both a scramble team and the wrong stableford group.
**Expected:** `leaderboardPlayers` finds them in local group first (line 839) then stops. They appear once. Admin should still flag the misconfig.

### O3. Three-player group (teamSize 3 scramble)
Four-player array padded by `padPlayers` (line 461). Non-existent player 4 has empty name · doesn't accumulate stats · doesn't appear on leaderboard.

### O4. 🔴 Race: two devices score the same hole simultaneously
Last write wins on Firebase. Verify no catastrophic merge — both writes end up in `/groups/{gid}` with the later `ts`. Missing a score entry from the earlier write is acceptable; crashing is not.

### O5. 🔴 Score entered as 0 (not null, not cleared)
Clear on a hole sets null. Stepping down from 1 goes to... check line 2514 `Math.max(0, current + delta)` — you can get 0. For gross, 0 is nonsense.
**Expected:** `stablefordPoints` with gross=0 → net<par → returns 4 pts (cap). ⚠️ **This is a bug surface.** Flag and consider a minimum of 1 for gross.

### O6. 🟡 Hcp stored as string
Bundle import might carry hcp as `"18"`. `shotsReceived` calls `parseInt(hcp || 0, 10)` (line 2169) → safe. But downstream subtractions might coerce to NaN. Verify leaderboard row with stringy hcp renders correctly.

### O7. 🔴 Event date parsing edge (line 851)
`parseEventDate`: supports MM/DD/YYYY and YYYY-MM-DD. Other formats return null. Score lock then returns `{locked:false}` (line 2716). Misconfigured date ≠ locked event. Verify your test event date format.

### O8. 🟡 Deep clone via `JSON.parse(JSON.stringify(...))` (line 699)
Functions, Dates, undefined are all stripped. Any state field relying on these would silently lose data on clone. Audit `resetRoundData`, `restoreSnapshot`.

### O9. iPhone Safari private mode
localStorage may be throttled or in-memory only. App should still function within the session; flag the user that data won't persist.

### O10. 🔴 Bundle mismatch between devices
Scorer on bundle v3, viewer on bundle v2.
**Expected:** `checkPendingEvent` (line 1001) shows banner on the stale device. Viewer's leaderboard may be inconsistent until they accept. Flag if any sync operations fail silently.

---

## Block P — Performance / Load

### P1. 20-player bundle with 5 groups
Render leaderboard. Should complete under 300 ms per render cycle.

### P2. 🟡 100 snapshots in history (line 1613)
`loadHistory` and `restoreSnapshot` — verify UI doesn't freeze with many saved events.

### P3. `renderAll()` frequency
Every state change calls `saveState()` then `renderAll()`. On a slow Android mid-range phone, the full re-render should stay < 200 ms. If you can profile, flag any hot path (challenge badge rendering is loop-heavy).

---

## Final checklist before April 25

- [ ] All 🔴 tests passing
- [ ] Admin test-runner.js passing 100%
- [ ] One full 18-hole dress rehearsal with 2 devices
- [ ] Test event purged after rehearsal; live event bundle published
- [ ] Firebase security rules reviewed (currently allow open writes — consider tightening before scaling)
- [ ] Offline mode verified on the specific devices players will use
- [ ] Score-lock unlock time matches real tee times in the bundle
- [ ] Scramble minDrives matches the team size in admin
- [ ] Challenge hole codes (B5, C4, C8, etc.) match the Palm Island front/back combo in the event JSON
- [ ] Money Hole pot zeroed or set to the event-day value
- [ ] All scorers can successfully enter a test score under their own player ID
- [ ] A viewer on a different account sees the score update within 3 s
- [ ] SW cache version bumped since last production push
- [ ] Export Full Event JSON archived before the event

---

## Code surfaces intentionally NOT covered by this plan

- `index.html` CSS / layout / mobile responsiveness — visual QA only, no deep tests
- Heckle audio/animations (`checkHoleHeckle`) — nice-to-have
- Tooltip positioning
- Gold jacket SVG rendering
- Printed scorecards — rely on CSS print styles; eyeball only

## What to do if you find a bug

1. Record: test ID (e.g. E2), expected vs actual, exact steps.
2. Check Firebase console to see what actually got written.
3. If critical (🔴 fail), hold the deploy. If 🟡, log and triage post-event.
4. For formula bugs in `stablefordPoints` or `shotsReceived`: STOP the event. These cascade to every score.

---

*Test plan generated 2026-04-15 from code inspection of `ChubbsMobileApp_v5/index.html` (5,808 LOC) + `ChubbsAdmin/index.html` (2,071 LOC) + existing `test-runner.js` (151 LOC).*
