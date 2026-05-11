# May 23 Yinli Test Plan

Last updated 2026-05-11. Use as a runnable checklist before the event.

**Pass criteria for each test:** all "Expected" rows match the observed behaviour, no console errors that didn't exist pre-test, no data drift between phones.

**Cadence:**
- Run **P0** first — these are the must-pass gates. If any fails, ship-blockers.
- **P1** before the dress rehearsal — should-pass edge cases.
- **P2** is the day-of dress rehearsal — walk-through of a real round with 4 mock players.

Time budget: ~2h for P0 + P1 + P2. Spread over a day or two.

---

## P0 — Must pass before May 22

### P0-1 — Bundle pipeline smoke

**What:** Admin builds a bundle, pushes to Firebase, mobile picks it up.

**Setup:**
1. Open ChubbsAdmin in browser.
2. Build a TEST event with:
   - Display name: "🧪 TEST · Yinli Dry Run"
   - Sat date: today
   - Sun date: tomorrow
   - Stableford course: Yinli
   - 4 players minimum — include at least 2 from `[Matt D, Andy, Nick, Jamie]` so the matchplay banner can activate
3. Push to Firebase via the admin's deploy button.

**Steps:**
1. On mobile, load the app, navigate to the test bundle.
2. Pick "Playing as" → one of the 4 players.
3. Verify the event banner shows the test 🧪 prefix.
4. Verify the Round tab is selected; Stableford is the default sub-pill.

**Expected:**
- Bundle loads without console error
- Header subtitle reads `{playerName} @ Yinli · {date}`
- Round tab visible; Leaderboard / Standings / Me also visible
- If the bundle has `playoffs.seeds`: matchplay banner appears above the scorecard

**Fail mode:**
- Bundle fails to load → check Firebase rules, retry after rules publish
- Banner doesn't appear → verify `season.playoffs.seeds` exists for `season-4` in `chubbs_seasons_v1` localStorage (use the inject snippet in SESSION_NOTES.md)

---

### P0-2 — Single foursome live scoring (no playoffs overlay)

**What:** The bread-and-butter — score a regular Chubbs hole and see the math.

**Setup:** P0-1 done. Active scoring view open. 4 players in the foursome.

**Steps:**
1. On hole 1, tap a player's stepper, enter their gross.
2. Repeat for all 4 players.
3. Tap "Next hole" or navigate to hole 2.
4. Continue through hole 5.

**Expected:**
- Stableford points appear under each player's row (e.g., "2 pts" for par)
- Per-player running totals update at the bottom of each card
- Hole scorecard at the bottom shows the entered scores in the cells

**Fail mode:**
- Points missing → check `stablefordPoints()` function isn't crashing (console)
- Wrong points → verify course par/SI is correct in `state.eventBundle.event.day2CourseId`

---

### P0-3 — Match close → bracket save

**What:** Push a match through to close, save the result, verify it lands in the bracket viewer.

**Setup:** Bundle with `playoffs.seeds` containing 2+ R16-paired players in the active foursome.

**Steps:**
1. Enter scores so one matchplay pair has a clear winner after 5 holes (e.g., Matt D wins H1–H5 outright over Andy).
2. Watch the banner — at some hole, status changes to "🏆 Matt D · 5&4".
3. Tap "📌 Save M1 to bracket".
4. Navigate to Standings tab → Playoffs sub-pill.
5. Verify M1 in the R16 bracket shows Matt D as the winner with "5&4".

**Expected:**
- Banner says "✓ Saved to bracket" after tap
- Bracket viewer reflects the save immediately
- No console errors

**Edge to verify:** Continue entering scores for the closed match (Andy wins H6–H9). Banner label stays "5&4" — does NOT drift to "1 UP" or similar. (This is the v5.58 freeze fix — confirms it's working.)

**Fail mode:**
- "Save to bracket" button doesn't appear → check masterMode is on OR you're the designated scorer
- Save doesn't persist → check console for Firebase errors

---

### P0-4 — Designated scorer enforcement

**What:** Non-scorer phones can see but can't input. Scorer phone can input.

**Setup:** Two browser tabs/windows (or two physical phones if available) loaded into the same event bundle, picking different "Playing as" identities.

**Steps:**
1. Tab A: log in as the designated scorer (per the bundle's `scorerPlayerId` for the foursome).
2. Tab B: log in as a non-scorer player in the same foursome.
3. On Tab A: enter scores for hole 1.
4. On Tab B: try to tap a stepper.

**Expected:**
- Tab A: scores enter, view updates, no toast
- Tab B: toast appears "👁 View only — stableford scorer enters scores", stepper does NOT change the value
- Tab B: scores appear in the cards as Tab A enters them (via Firebase sync) within ~1-2 seconds

**Fail mode:**
- Tab B can also enter scores → check `isCurrentPlayerScorer('stableford')` returns false for the non-scorer
- Sync doesn't happen → check both tabs are subscribed to the same Firebase room

---

### P0-5 — Hole-by-hole hint correctness

**What:** The "H6: Jordan: 5−2=3n · Ricardo: 5=5n → Jordan wins H6" line shows the right math.

**Setup:** Active matchplay banner visible.

**Steps:**
1. Pick a hole where the two players in a match have different handicaps (e.g., Matt D hcp 12 vs Andy hcp 30).
2. Enter Matt D: 5, Andy: 6 on a hole with SI in 1–18 (Andy gets at least 1 stroke).
3. Read the per-hole hint under the match row.

**Expected:**
- Hint reads something like `H1 (par 4, SI 11) · Matt D: 5=5n · Andy: 6−1=5n → H1 halved`
- Math is correct (gross − strokes = net)
- Outcome label matches the recomputed status

**Fail mode:**
- Wrong stroke count → verify `matchPlayStrokes(hcpHigh, hcpLow, si)` produces the right value (run `qa/matchplay_engine.py`)

---

## P1 — Should pass before May 22

### P1-1 — Tiebreak surface at all-square thru 9

**What:** When match is tied at H9, banner shows the §11 tiebreak resolution.

**Setup:** Enter scores so a match is exactly even after 9 holes.

**Steps:**
1. Score 9 holes such that the matchplay status ends ALL SQUARE (e.g., halve every hole).
2. Look for the tiebreak row beneath the match.

**Expected:**
- Row reads `⚖ Tiebreak (Stableford): {playerA} {sb_a} pts · {playerB} {sb_b} pts → {winnerName}`
- If Stableford is also tied: shows `SB tied at X. Lower hcp wins: ... → {winnerName}`
- If hcps are also tied: shows `ARM WRESTLE (admin enters winner)` — no auto-save button
- Save button uses result label "1 UP (TB-SB)" or "1 UP (TB-Hcp)"

**Fail mode:**
- Tiebreak doesn't fire → verify `status.allSquare && status.played === 9` is true
- Wrong winner → verify Stableford computed over the 9 match holes (not 18)

---

### P1-2 — Match closes early, continued play preserves the closing label

**What:** v5.58 freeze fix regression test.

**Setup:** Single foursome, both players in a match.

**Steps:**
1. Enter scores so a match closes at "3&2" by H7.
2. Tap "📌 Save M{N} to bracket" — verify saved.
3. Continue entering scores for H8 and H9 (Stableford keeps going).
4. Refresh the banner (any score entry triggers re-render).

**Expected:**
- Banner status STAYS at "🏆 {winner} · 3&2" through H8 and H9
- Save status STAYS at "✓ Saved to bracket" — does NOT revert to "Save" button
- Continuing scores still count for Stableford on both players

**Fail mode:**
- Label drifts to "2&1" / "1 UP" / etc. → freeze logic broken; re-check `getActiveMatchPlayMatches` iteration
- Save button reappears → `isSaved` check failing on label mismatch

---

### P1-3 — Late group change (re-push bundle)

**What:** Brain trust shuffles foursomes 15 minutes before tee. Admin re-pushes bundle. Mobile picks up the new groups.

**Setup:** P0-1 done with current foursomes.

**Steps:**
1. On admin: edit a foursome (e.g., swap one player between two groups).
2. Re-export bundle → push to Firebase.
3. On mobile: pull-to-refresh.
4. Open the score view.

**Expected:**
- The foursome composition reflects the new groups
- If the swapped player was the scorer, the new scorer is auto-picked per brain-trust priority
- Matchplay banner re-evaluates and shows / hides matches based on new pairings

**Fail mode:**
- Old foursome still shown → cache issue, force-reload
- Wrong scorer → admin can manually override per group

---

### P1-4 — Withdrawal between R16 and QF

**What:** A player who won R16 can't play QF (injury, ill, leaves). Admin needs to handle.

**Setup:** R16 complete, QF pairings derived.

**Steps:**
1. In admin: find the withdrawn player's R16 result → mark them as withdrawn or replace with their R16 opponent (the loser advances)
2. Push bundle.
3. Open mobile → Standings → Playoffs.

**Expected:**
- QF pairings update to reflect the substitution
- Bracket viewer shows the new player in the QF slot
- No double-count or empty slot

**Fail mode:**
- No clean way to do this in admin UI → for May 23, fall back to manual entry: clear the R16 result and re-save with the new winner. Document the manual procedure.

**Mitigation if it happens on the day:** Admin manually edits `season.playoffs.r16[idx].winner` via the bracket viewer's existing entry modal. Inelegant but works.

---

### P1-5 — Network drop mid-round

**What:** Phone loses WiFi/4G during scoring. Local entry still works. Reconnect syncs.

**Setup:** Active scoring round.

**Steps:**
1. Enter scores for holes 1–5.
2. Turn on airplane mode.
3. Enter scores for holes 6–9.
4. Turn off airplane mode.
5. Wait 5 seconds.

**Expected:**
- Holes 6–9 saved locally (visible on phone)
- After reconnect: other phones see holes 6–9 via Firebase sync
- No "lost" scores or duplicate saves

**Fail mode:**
- Scores lost after reconnect → check `pushState()` retries
- Sync conflicts → last-write-wins is fine; if two scorers entered simultaneously, the last write wins

---

### P1-6 — Hero subtitle at 360px (cosmetic)

**What:** Subtitle doesn't ellipsize badly on small phones.

**Setup:** Resize browser to 360px width, or use a real 360px phone.

**Steps:**
1. With a Yinli bundle loaded: read the hero subtitle.
2. Verify "Hanson @ Yinli · Sat 23 May" (or similar) is fully visible.

**Expected:**
- Full subtitle fits without ellipsis
- If it does ellipsize, the truncation is graceful

**Mitigation if it ellipsizes:** Either accept it (low priority for May 23) or ship a one-line CSS tweak: reduce font-size from 11px → 10px on `.hero .sub` at narrow widths.

---

## P2 — Day-of dress rehearsal (do once, ~1h)

### P2-1 — Full mock round walkthrough

**What:** Simulate the entire May 23 flow with a real bundle and 4 mock identities.

**Setup:**
- Lock the real seeds via admin tool
- Push bundle to Firebase
- 4 browser windows/tabs/phones, each logged in as a different player from one foursome

**Steps:**
1. **Pre-round:** Confirm matchplay banner shows for the foursome's 2 R16 matches (e.g., M1 + M8).
2. **Hole-by-hole:** Enter scores for all 4 players across all 18 holes. The designated scorer's phone enters; others observe.
3. **Front 9 close:** Verify at least one R16 match closes during the front 9. Save to bracket. Verify other phones see the save.
4. **Turn:** At hole 9 end, if any match is ALL SQUARE thru 9, verify tiebreak surface and save.
5. **Back 9:** Score holes 10–18 for Stableford. No matchplay banner activity expected (the R16 matches are already closed).
6. **End-of-round:** Check Standings tab. Player season points should update if the event was saved as a snapshot. Final Two intermission card shouldn't show during the round.

**Pass criteria:**
- All 4 phones show identical scores after each hole
- Both R16 matches in the foursome close cleanly (or one + a tiebreak)
- "Save to bracket" works from the scorer's phone
- Bracket viewer reflects both saves
- No console errors throughout
- Stableford continues for all 18 holes regardless of matchplay closure

**Failure recovery:**
- If something crashes mid-round, the last `state.stableford.holes` is in localStorage. Force-reload the page; it should restore.
- If Firebase sync hangs, the scorer's phone is the source of truth — admin can clear other phones' cache and they'll re-fetch from Firebase.

---

## Recovery procedures (in case of trouble on May 23)

| Symptom | Action |
|---|---|
| Bundle won't load on a phone | Pull-to-refresh; if still stuck, paste reset snippet from SESSION_NOTES.md and rejoin |
| Matchplay banner missing on a foursome with seeded players | Inspect `chubbs_seasons_v1` localStorage; if seeds missing, force re-fetch from admin (admin re-pushes bundle) |
| Save to bracket doesn't work for the scorer | Verify `state.eventPlayerId` matches the bundle's scorer for that group; if mismatched, the scorer should re-pick their identity from the "Playing as" picker |
| Sync between phones lags | Check Firebase status; pull-to-refresh forces re-subscription |
| Match label drift / wrong save status | Should NOT happen post-v5.58; if it does, re-save from the closed banner state |
| Tiebreak misfires | Verify all 9 match holes have grosses entered for both players; gaps cause incomplete tiebreak compute |
| Wrong scorer auto-picked | Admin app supports manual scorer override per foursome — push corrected bundle |

---

## Test data scenarios

### Scenario 1 — chalk path
4 players: seeds 1, 16, 2, 15 (Matt D, Andy, Nick, Jamie). Matt D + Nick win their R16 matches cleanly (3&2 or similar). Used in P0-3 and P2-1.

### Scenario 2 — upset
Same 4 players. Andy beats Matt D (seed 16 over seed 1). Verifies bracket cascade correctly drops Matt D to Plate side. Used in P1-3 follow-up.

### Scenario 3 — ALL SQUARE thru 9
Both players in a match have identical net scores hole-by-hole (e.g., both par every hole). Tiebreak fires. Used in P1-1.

### Scenario 4 — closed early then continued play
Match closes at H5 with "5&4". Players continue through H9 for Stableford. v5.58 freeze fix verified. Used in P1-2.

---

## What's NOT in scope for this test plan

- Match-play handicap differential math (already validated via 11 sanity tests in `qa/matchplay_engine.py`)
- Stableford computation (already validated against 211 S3 player-events)
- Bracket cascade resolution (already validated via `qa/playoff_sim.py`)
- Course par/SI (already validated against Terry's spreadsheet)

These are foundation-layer items that don't need re-testing on the phone — they're proven correct. The P0-P2 tests focus on the **integration layer** (Firebase pipeline, multi-phone sync, UI activation) which can only be verified end-to-end.
