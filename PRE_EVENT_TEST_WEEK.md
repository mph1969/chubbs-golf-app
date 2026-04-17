# 🐊 CPI 2026 — Pre-Event Test Week

**Game day:** Saturday April 25, 2026
**Owners:** M = Michael · T = Terry · BOTH = both admins
**Devices needed:** the actual phone you'll use Saturday morning. No "I'll use a different phone on the day."

> **Single most important pass/fail:** by Friday April 24, both Michael's phone AND Terry's phone must register a hit on `🩺 Verify Mobile Access` from the LIVE event. If both pass that, the cached bundle is on both devices, sync token is fresh, and Saturday morning is essentially guaranteed to work even if venue Wi-Fi is dead.

---

## SAT Apr 18 (today) — T-7 · Foundation [~45 min · M]

### 1. Publish the LIVE bundle
- Admin desktop: confirm event mode = **🟢 LIVE** (header chip should be green).
- Hit **☁️ Send to App**.
- Hit **✅ Game Day Check** — every row should be green, OR the only warning is "no group has been pre-assigned" (acceptable). Fix any red.

### 2. Confirm cloud state is clean
- Admin: open the desktop link, hit **🩺 Verify Mobile Access** — leave the modal open.
- On your phone: visit `https://chubbs-golf.netlify.app/`. Cloud-events list should show ONLY the LIVE event (no leftover TEST events). The chip should read 🟢 LIVE.
- Tap the event, pick your name, load.
- The verify modal on desktop should tick **✅ 1 mobile fetch confirmed** within 2 seconds.
- **PASS** = green tick. **FAIL** = check Firebase rules + republish.

### 3. Smoke test the scoring screens
- On your phone, navigate to Scramble scorer view → enter a score on hole 1, advance, retreat, delete the score.
- Same for Stableford screen.
- Confirm Master PIN: Settings → enter PIN → confirm "Master mode" toggle works.

### 4. Snapshot the JSON to your phone's Files app
- Admin desktop: hit **💾 Export JSON** → file lands as `2026-Chubbs-Pet-LIVE-20260418.json`.
- AirDrop/email it to your phone, save in Files app under a clear folder name. This is the worst-case manual import file.

### 5. Send Terry these instructions
He should do steps 2–4 on his own game-day phone today or tomorrow.

---

## SUN Apr 19 → MON Apr 20 — T-6/-5 · Quiet days [~10 min · BOTH]

### 1. Both admins do step 2 from Apr 18 once a day
- Open `chubbs-golf.netlify.app/` on your game-day phone, confirm the event still loads from cloud. Don't change anything.
- This keeps your service worker fresh and your Firebase auth token alive.

### 2. Don't touch the admin
…unless you're adding/removing a player. If you do change anything, re-do the Apr 18 full sequence.

---

## TUE Apr 21 — T-4 · Roster freeze [~20 min · M]

### 1. Final roster review
- Admin: confirm every player who's playing is in the roster, marked attending, and assigned to a scramble team + Stableford group.
- Each scramble team has a `scorerPlayerId` set. Each Stableford group has a `scorerPlayerId` set.
- Currency is RMB. Min drives is right for your team sizes.

### 2. Re-publish if anything changed
- If you touched the bundle: **☁️ Send to App** → **🩺 Verify Mobile Access** → both you and Terry reload on your phones.

### 3. Purge old TEST events
- Admin → 🧹 Cleanup ▾ → "Purge test events". Confirm cloud-events list shows ONLY the LIVE event.

---

## WED Apr 22 — T-3 · Live sync stress test [~30 min · BOTH]

This is the most important test before Friday. Both admins on phones, plus one other device (laptop browser is fine).

**Setup:** Both M+T load the LIVE event on their phones. Open a third browser tab as a **viewer** (no scorer assignment).

### Test 1 — Scorer enters score, viewer sees it
- M (scorer for Group X): enter a score on hole 1.
- Viewer tab: refresh leaderboard within 5 seconds → score should appear.
- ✅ Pass = score visible on viewer.

### Test 2 — Two scorers, no collision
- M enters score for Group X player on hole 2.
- T enters score for a different Group Y player on hole 2.
- Both players' scores should land — no overwrites.
- Refresh leaderboard, confirm both rows updated.

### Test 3 — Score lock override
- Admin (one of you): toggle score lock OFF in admin (Master mode → score lock override).
- The other phone: confirm score steppers become active even if before tee time window.
- Toggle back ON.

### Test 4 — Clean up your test data
- Both: clear your test scores via Master mode → "Clear round scores" on each device.
- Confirm leaderboard returns to all-zeros.

---

## THU Apr 23 — T-2 · Offline + recovery rehearsal [~20 min · M]

### 1. Offline cache test
- On phone: enable Airplane Mode.
- Reload `chubbs-golf.netlify.app/`.
- Cloud scan will fail/timeout. **📦 Cached Events** card should still appear with the bundle.
- Tap it → loads from cache. Scorer screen renders.
- Turn data back on. Sync resumes.
- ✅ Pass = scorer screen usable while offline.

### 2. JSON file fallback test
- Still in Airplane Mode (or just simulate): use the JSON file you saved Apr 18 in Files app.
- Open `chubbs-golf.netlify.app/` → on the import screen, find the "Import from file" option → pick your saved JSON.
- ✅ Pass = event loads from disk.

### 3. Have Terry do the same offline test on his phone

---

## FRI Apr 24 — T-1 · LOCKDOWN [~30 min · BOTH]

**This is the final go/no-go.** No code changes after today.

### 1. Final Game Day Check (M, admin desktop)
- All rows green. Re-publish if any data changed since Wednesday.

### 2. Final Verify Mobile Access (BOTH)
- M opens admin desktop, hits **🩺 Verify Mobile Access**.
- Both M and T load the event on their phones simultaneously.
- ✅ Pass = modal shows **2 mobile fetches confirmed** with both device IDs visible.

### 3. Final cache snapshot (BOTH)
- Both phones: load the event from cloud (not cache) so the latest bundle is in cache.
- Don't clear browser data tonight.

### 4. Master PIN written down
- Both M+T: confirm you know the Master PIN. Write it on paper or in Notes app, OUTSIDE the app. If only one of you knows it, the other can't recover.

### 5. Backup JSON refreshed
- Re-export JSON from admin → AirDrop to both phones → save in Files app, replacing the older Apr 18 file.

### 6. Battery check
- Both phones charged > 80% the night before. Bring a charging brick + cable.

---

## SAT Apr 25 — GAME DAY · First 30 min protocol

### T-30 min — first admin to arrive
1. Open `chubbs-golf.netlify.app/` on your phone.
2. Cloud scan should be fast (<5s). If slow → tap from **📦 Cached Events** instead.
3. Pick your name, load.
4. Navigate to Scramble scorer screen, confirm hole 1 par+SI render.
5. ✅ Green light. Don't touch admin.

### T-15 min — second admin arrives
1. Same as above.
2. Confirm with the first admin that you're both on the LIVE event (chip says 🟢 LIVE).

### T-0 — players arrive
- Players go to `chubbs-golf.netlify.app/`, scan cloud, pick their name, load.
- If a player can't load → triage in this order:
  - Internet on their phone? (test by visiting any website)
  - Right URL? Re-share the link.
  - Wrong name picked? → tap "← Pick a different event" and re-select.
  - Bundle missing from cloud? → unlikely if Friday verify passed, but if so: WeChat them the JSON file from your phone, they import via "From file…"
- **DO NOT republish the bundle from admin** during the round unless you have no choice. Republishing nukes everyone's stored state.

---

## ⚠️ Emergency contacts during the round

If something breaks mid-round and you need to fix it:
- **Wrong score entered:** scorer can edit any prior hole — non-destructive.
- **Wrong scorer assigned:** master-mode override on the affected device. Don't change scorer assignment in admin mid-round.
- **Score lock blocking entry:** master mode → score lock override.
- **A player's app crashes:** they reload the URL. Their scores survive (they're in Firebase, not local).
- **Firebase outage:** scoring continues offline (writes are queued in localStorage). Don't panic. When Firebase comes back, writes flush automatically.

---

## ✅ Daily checklist (tear-off summary)

| Date | Owner | Done? |
|---|---|---|
| Sat Apr 18 | M — publish + verify + JSON snapshot | ☐ |
| Sat Apr 18 | T — verify on phone + JSON snapshot | ☐ |
| Sun Apr 19 | BOTH — daily ping load | ☐ |
| Mon Apr 20 | BOTH — daily ping load | ☐ |
| Tue Apr 21 | M — roster freeze + purge tests | ☐ |
| Wed Apr 22 | BOTH — live sync stress test | ☐ |
| Thu Apr 23 | M — offline + JSON fallback | ☐ |
| Thu Apr 23 | T — offline + JSON fallback | ☐ |
| Fri Apr 24 | BOTH — FINAL verify, both phones must hit | ☐ |
| Fri Apr 24 | BOTH — Master PIN written down | ☐ |
| Fri Apr 24 | BOTH — refreshed JSON in Files app | ☐ |
| Fri Apr 24 | BOTH — phones charged | ☐ |
| Sat Apr 25 | T-30 first admin arrives, loads event | ☐ |
| Sat Apr 25 | T-15 second admin arrives, loads event | ☐ |
