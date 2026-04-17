# 🐊 CPI 2026 — Pre-Event Test Week

**Game day:** Saturday April 25, 2026
**Player go-live (driving directions):** **Friday April 24 at NOON**
**Owners:** M = Michael · T = Terry · BOTH = both admins
**Devices needed:** the actual phone you'll use Saturday morning. No "I'll use a different phone on the day."

> ## ⚡ Two non-negotiables
> 1. **By Thursday Apr 23 EOD**, both Michael's phone AND Terry's phone must register a hit on `🩺 Verify Mobile Access`. If both pass, the bundle is locally cached on both devices, sync is fresh, and Saturday is essentially guaranteed.
> 2. **Before Friday noon broadcast to players**, only the 🟢 LIVE event must be visible in the cloud-events list. Any leftover 🧪 TEST event is a hazard — players will tap the wrong one.

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

## SUN Apr 19 — T-6 · Quiet day [~10 min · BOTH]

- Both admins: open `chubbs-golf.netlify.app/` on game-day phone, confirm event still loads from cloud. Don't change anything.
- Keeps the service worker fresh and Firebase auth token alive.

---

## MON Apr 20 — T-5 · Roster freeze (moved up from Tue) [~20 min · M]

### 1. Final roster review
- Admin: confirm every player who's playing is in the roster, marked attending, and assigned to a scramble team + Stableford group.
- Each scramble team has a `scorerPlayerId` set. Each Stableford group has a `scorerPlayerId` set.
- Currency is RMB. Min drives is right for your team sizes.

### 2. Re-publish if anything changed
- If you touched the bundle: **☁️ Send to App** → **🩺 Verify Mobile Access** → both you and Terry reload on your phones.

### 3. Purge old TEST events
- Admin → 🧹 Cleanup ▾ → "Purge test events". Confirm cloud-events list shows ONLY the LIVE event. **This must stay clean from now on — players will see this list on Friday noon.**

---

## TUE Apr 21 — T-4 · Live sync stress test (moved up from Wed) [~30 min · BOTH]

This is the most important test of the week. Both admins on phones, plus one other device (laptop browser is fine).

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

## WED Apr 22 — T-3 · Offline + recovery rehearsal (moved up from Thu) [~20 min · BOTH]

### 1. Offline cache test (each admin on own phone)
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

### 3. Both admins must complete this on their own phones
Don't skip Terry's rehearsal — Saturday morning is too late to discover his cache is empty.

---

## THU Apr 23 — T-2 · LOCKDOWN (moved up from Fri) [~30 min · BOTH]

**This is the final go/no-go.** No bundle changes after today. Tomorrow (Friday) we broadcast to players — tonight everything must be perfect.

### 1. Final Game Day Check (M, admin desktop)
- All rows green. Re-publish if any data changed since Tuesday.

### 2. Final Verify Mobile Access (BOTH)
- M opens admin desktop, hits **🩺 Verify Mobile Access**.
- Both M and T load the event on their phones simultaneously.
- ✅ Pass = modal shows **2 mobile fetches confirmed** with both device IDs visible.
- **This is the non-negotiable pass/fail.** If it fails, fix tonight before going to bed.

### 3. Final cloud-list cleanup
- One last 🧹 purge of any test events. Cloud-events list MUST show only the 🟢 LIVE event when players open the app tomorrow.

### 4. Final cache snapshot (BOTH)
- Both phones: load the event from cloud (not cache) so the latest bundle is in cache.
- Don't clear browser data tonight or tomorrow.

### 5. Master PIN written down
- Both M+T: confirm you know the Master PIN. Write it on paper or in Notes app, OUTSIDE the app. If only one of you knows it, the other can't recover.

### 6. Backup JSON refreshed
- Re-export JSON from admin → AirDrop to both phones → save in Files app, replacing the older Apr 18 file.

### 7. Draft the Friday-noon player broadcast message
- WeChat group message ready to send. See template below.

---

## FRI Apr 24 — T-1 · PLAYER GO-LIVE 🚀

### 12:00 NOON — Broadcast to players (M)

Send to the CPI WeChat group (or whatever channel you use):

```
⛳ CPI 2026 — App is live!

Open this link on your phone for course directions, your tee time,
your team, scorecard preview, and live leaderboard once we tee off:

https://chubbs-golf.netlify.app/

Tap the event → pick your name → you're in.

Add to home screen for quick access (iPhone: Share → Add to Home).

— see you at Palm Island Saturday morning 🐊
```

### 12:00 NOON — Both admins on standby for the next hour

Players will start opening the app immediately. Watch for:

- **🩺 Verify Mobile Access** open on admin desktop → you'll see hits roll in as players load. Each hit = a working device.
- **WeChat questions** like "I don't see my name" → check that player ID is in the bundle's player list. If missing, you'll need to add them in admin → republish → ask them to reload.
- **"It says event not found"** → they probably tapped a stale browser cache. Tell them to fully close Safari, reopen, paste the link.

### 14:00 — Spot-check the player loads (M)

- On admin desktop, hit **🩺 Verify Mobile Access** again. By now you should have multiple hits beyond your own + Terry's.
- If a specific player still hasn't loaded, ping them on WeChat to confirm.

### 18:00 — Final lockdown ritual (BOTH)

- Both admins: do ONE more cloud load on your game-day phones. Confirms cache is fresh.
- Phones charged > 80% before bed.
- Charging brick + cable in your golf bag.

### ⛔ DO NOT after Friday noon
- Do NOT republish the bundle unless absolutely necessary. Every republish risks confusing players who've already loaded.
- Do NOT toggle the event mode (LIVE ↔ TEST). Stays LIVE.
- Do NOT change roster, teams, or groups. If something is wrong, fix it on Saturday morning at the course rather than mid-Friday — players will already be in the app.

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
- Most players already loaded the app on Friday — they should just open it again.
- For stragglers: same drill as Friday noon (`chubbs-golf.netlify.app/` → scan → name → load).
- If a player can't load → triage in this order:
  - Internet on their phone? (test by visiting any website)
  - Right URL? Re-share the link.
  - Wrong name picked? → tap "← Pick a different event" and re-select.
  - Bundle missing from cloud? → unlikely if Thursday verify passed, but if so: WeChat them the JSON file from your phone, they import via "From file…"
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

| Date | Owner | Task | Done? |
|---|---|---|---|
| Sat Apr 18 | M | Publish + verify + JSON snapshot | ☐ |
| Sat Apr 18 | T | Verify on phone + JSON snapshot | ☐ |
| Sun Apr 19 | BOTH | Daily ping load | ☐ |
| Mon Apr 20 | M | Roster freeze + purge tests | ☐ |
| Tue Apr 21 | BOTH | Live sync stress test | ☐ |
| Wed Apr 22 | M | Offline + JSON fallback rehearsal | ☐ |
| Wed Apr 22 | T | Offline + JSON fallback rehearsal | ☐ |
| **Thu Apr 23** | **BOTH** | **🔒 LOCKDOWN — final verify, both phones must hit** | ☐ |
| Thu Apr 23 | BOTH | Master PIN written down | ☐ |
| Thu Apr 23 | BOTH | Refreshed JSON in Files app | ☐ |
| Thu Apr 23 | M | Draft Friday-noon broadcast | ☐ |
| **Fri Apr 24 12:00** | **M** | **🚀 Broadcast app link to players** | ☐ |
| Fri Apr 24 12:00–13:00 | BOTH | On standby for player questions | ☐ |
| Fri Apr 24 14:00 | M | Spot-check player loads via Verify Mobile | ☐ |
| Fri Apr 24 18:00 | BOTH | Final cache load + phones charged | ☐ |
| Sat Apr 25 T-30 | First admin | Arrive + load event | ☐ |
| Sat Apr 25 T-15 | Second admin | Arrive + load event | ☐ |
