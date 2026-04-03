# Chubbs Peterson Invitational — App Guide

**Version:** 5.0 · Built 2026  
**Mobile app:** https://chubbs-golf.netlify.app  
**Admin app:** https://YOUR-ADMIN-SITE.netlify.app *(update this)*  
**GitHub:** https://github.com/mph1969/chubbs-golf-app  

---

## Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Admin User Guide — Before the Weekend](#2-admin-user-guide--before-the-weekend)
3. [Admin User Guide — During the Weekend](#3-admin-user-guide--during-the-weekend)
4. [Player User Guide](#4-player-user-guide)
5. [Scorer Quick Reference](#5-scorer-quick-reference)
6. [Troubleshooting](#6-troubleshooting)
7. [Deployment & Maintenance](#7-deployment--maintenance)

---

## 1. Architecture Overview

```
ChubbsAdmin (desktop/tablet)
    │
    │  Build event → ☁️ Send to App
    │
    ▼
Firebase Realtime Database
    │                          │
    │ /events/{id}/bundle      │ /events/{id}/groups/{gid}
    │ (event setup)            │ (live scores — written by scorers)
    ▼                          ▼
Mobile App                 Mobile App
?loadEvent= link           live leaderboard
(one-time import)          (?watch= spectators)
```

### Components

| Component | What it is | URL / Location |
|---|---|---|
| **Mobile App** | PWA scorer — Scramble, Stableford, 3-putt poker, leaderboard | `chubbs-golf.netlify.app` |
| **Admin App** | Desktop event builder — players, teams, groups, push to cloud | Your admin Netlify URL |
| **Firebase RTDB** | Cloud sync — event bundles + live score relay | `chubbs-golf-default-rtdb` |
| **GitHub repo** | Source code backup + Netlify auto-deploy trigger | `mph1969/chubbs-golf-app` |

### Key data flows

- **Event setup** flows Admin → Firebase → each player's app (via `?loadEvent=` link, one-time)
- **Live scores** flow Scorer's phone → Firebase → all other phones in real time
- **Leaderboard** is rebuilt locally on each device from Firebase data; no server needed
- **Everything is a PWA** — both apps install to home screen, work offline after first load

---

## 2. Admin User Guide — Before the Weekend

### Step 1 — Open ChubbsAdmin

Open the admin Netlify URL on a desktop or tablet browser. The app saves your roster between sessions in the browser's local storage — your player list will be there from last time.

---

### Step 2 — Confirm the roster

In the **Roster** panel on the left:
- Check all attending players have the correct **handicap**
- Toggle each player's **attendance**: Scramble only · Stableford only · Both · Not coming
- Add any new players with **+ Add player**
- You can import a saved `cpi_roster.json` if you have one backed up

---

### Step 3 — Set event details

In **Event Rules**:
| Field | Example |
|---|---|
| Event name | Chubbs Peterson Invitational |
| Display name | April Chubbs at Palm Island |
| Currency | RMB |
| 3-putt poker ante | 50 |
| 3-putt penalty (3 putts) | 10 |
| 3-putt penalty (4+ putts) | 20 |

In **Scramble** and **Stableford** tabs:
- Set the **date**, **tee time**, and **course** for each day
- For Palm Island — select which 9-hole combinations (A/B/C/D) are in play

---

### Step 4 — Assign teams and groups

**Scramble tab (Saturday):**
- Click **Auto-assign** to randomly distribute players into balanced teams of 4
  *(balances handicaps automatically)*
- Or drag player pills manually into team slots
- Set the **scorer** for each team using the dropdown — scorer is always listed last

**Stableford tab (Sunday):**
- Click **Auto-assign** for random groups
- Set **tee times** per group (8-minute intervals is standard)
- Set the **scorer** per group

> **Tip:** Captains/scorers should be the most experienced players with the app.

---

### Step 5 — Push to app

Click **☁️ Send to App** in the top-right corner.

On success, a **Player Links panel** appears below the header with a personalised link for every player:

```
HANSON   https://chubbs-golf.netlify.app/?loadEvent=2026-Chubbs-Pet&player=HANSON  [Copy]
DIEGO    https://chubbs-golf.netlify.app/?loadEvent=2026-Chubbs-Pet&player=DIEGO   [Copy]
…
[📋 Copy all links]    [Copy organiser import link]
```

---

### Step 6 — Import the event (organiser devices first)

1. Click **Copy organiser import link**
2. Open it on your phone (or Terry's phone)
3. The mobile app loads the full event automatically
4. You'll see a green banner — tap **Import**
5. Verify your scramble team and Stableford group show correctly on the **Me** tab

---

### Step 7 — Send player links via WeChat

1. Click **📋 Copy all links**
2. Paste into the CPI WeChat group
3. Players tap their own name → app opens, event loads, identity set
4. Done — no file sharing, no manual setup

---

## 3. Admin User Guide — During the Weekend

### Scramble day (Saturday)

- Each **team scorer** opens the app and confirms their team on the **Scramble** tab
- Scorers enter the team's gross score hole by hole and mark who drove each hole
- The **drive requirement tracker** at the top shows each player's drive usage in real time

**At the end of the round:**
- Go to the **Leaderboard** tab
- Scramble results are locked until prize giving — tap **Reveal Scramble results** when ready

### Stableford day (Sunday)

- Each **group scorer** opens the app and confirms their group on the **Stableford** tab
- Scores are entered hole by hole; Stableford points calculate automatically based on handicap
- Live scores sync to Firebase and appear on every player's leaderboard in real time

### 3-putt poker

- Toggle poker **on** at the top of the Stableford tab before play starts
- Set ante, 3-putt penalty, and 4+ putt penalty
- Enter putts per player on each hole — the app tracks cards, penalties, and pot
- At round end, tap **Deal digital cards** to run the poker hand from accumulated cards

### Leaderboard paywall

The full individual Stableford leaderboard is behind an honour-system paywall.
Players see the leader only (free). To unlock:
1. Tap **WeChat Pay 🍺** → save QR to photos
2. WeChat → Pay → Photo Library / QR code → scan & pay
3. Tap **Unlocked ✓**

Unlock persists on that device for the weekend.

---

## 4. Player User Guide

### Getting started

**You'll receive a WeChat message with your personal link.** It looks like:
```
HANSON: https://chubbs-golf.netlify.app/?loadEvent=...&player=HANSON
```

Tap it. The app opens in your browser and automatically:
- Loads this weekend's event
- Sets your identity (your name, handicap, team, group)

**Install to home screen** for the best experience:
- **iPhone:** tap Share → Add to Home Screen
- **Android:** tap the browser menu → Install app / Add to Home Screen

---

### The Me tab

Your home screen for the weekend. Shows:
- **Who you're playing as** and your handicap
- **Venue card** — course name, address, map links (CN + EN), address copy buttons
- **Scramble team** — your teammates, tee time, scorer
- **Stableford group** — your groupmates, tee time, scorer
- **Copy my link** — share your personal link to anyone who needs it

---

### The Leaderboard tab

- **Scramble** section — your team's live gross score and to-par (during Saturday's round)
- **Stableford** section — current leader shown free; unlock full board with a small tip
- **3-putt poker** section — pot size and card counts (collapsed until putts start)

Scramble results are locked until prize giving.

---

### The Scramble tab (Saturday)

If you are the **team scorer**:
1. Select the hole using **← Prev / Next →**
2. Enter the **team gross score** with the +/− stepper
3. Mark **who drove** by tapping their name
4. Repeat for all 18 holes

If you are **not the scorer** — this tab shows your team info and drive tracker. You can follow along but cannot enter scores.

---

### The Stableford tab (Sunday)

If you are the **group scorer**:
1. Select the hole
2. Enter each player's **gross score** with the stepper
3. Enter **putts** if 3-putt poker is on
4. Stableford points calculate automatically
5. Scores sync live to the leaderboard

If you are **not the scorer** — tab shows your group's scores in read-only view.

---

## 5. Scorer Quick Reference

| Task | Where |
|---|---|
| Change hole | ← Prev / Next → buttons |
| Enter team score (Scramble) | +/− stepper under "Team gross" |
| Mark driver (Scramble) | Tap player name button |
| Enter player gross (Stableford) | +/− stepper under each player name |
| Enter putts (Stableford + poker) | Putt counter below each player's score |
| See drive tracker | Top of Scramble tab — coloured pills |
| Check to-par | Score summary at top of each tab |
| Export scorecard CSV | Settings → Data → Export |

**Colour coding on drive tracker pills:**
- 🟢 Green — player has used their 4-drive requirement
- 🟡 Amber — on track, still holes to go
- 🔴 Red — not enough holes left to hit 4 drives

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| App shows old event / wrong player | Open your personal `?loadEvent=` link again |
| Scores not appearing on leaderboard | Check internet connection; scores sync on save |
| Can't enter scores (greyed out) | You're in read-only mode — you're not the scorer |
| App won't install to home screen | Use Safari (iPhone) or Chrome (Android) |
| WeChat pay QR not scanning | Save QR image to photos first, then WeChat → Pay → Photo Library |
| Drive tracker showing wrong count | Check hole numbers — a driver can only be recorded once per hole |
| Admin push fails with permission error | Firebase rules — ensure you're writing to `/events/{id}/bundle` |
| Event not loading from `?loadEvent=` link | Check Firebase is reachable; try refreshing once |

---

## 7. Deployment & Maintenance

### Repo structure

```
chubbs-golf-app/
├── ChubbsMobileApp_v5/    ← deployed to chubbs-golf.netlify.app
│   ├── index.html
│   ├── ChubbsGatorIcon.png / .svg
│   ├── cpi_manifest_v4.json
│   ├── _redirects
│   ├── CPI Handbook.pdf
│   ├── mph_contact_qr.png
│   └── mph_pay_code.jpeg
├── ChubbsAdmin/           ← deployed to admin Netlify site
│   ├── index.html
│   ├── ChubbsGatorIcon.png / .svg
│   └── cpi_admin_manifest_v1.json
├── Chubbs Events/         ← event CSV files and example event.json
├── EventSetup/            ← Python scripts to build event.json from CSV
├── Assets/                ← source images, old icons (not deployed)
└── docs/                  ← this document
```

### Deploying a change

```bash
# Edit files locally, then:
git add -A
git commit -m "description of change"
git push
```

Both Netlify sites redeploy automatically within ~30 seconds.

### Netlify settings (both sites)

| Setting | Mobile app | Admin app |
|---|---|---|
| Publish directory | `ChubbsMobileApp_v5` | `ChubbsAdmin` |
| Build command | *(blank)* | *(blank)* |
| Base directory | *(blank)* | *(blank)* |

### Building an event.json manually

If not using ChubbsAdmin, the `EventSetup/` folder contains Python scripts:

```bash
cd EventSetup
# Edit cpi_players_v3.csv, cpi_day1_scramble_teams_v3.csv, cpi_day2_groups_v3.csv
python build_event_json_v3.py
# Outputs event.json — import this in the mobile app via Setup → Import event
```

### Firebase

- Project: `chubbs-golf`
- Database: `chubbs-golf-default-rtdb.asia-southeast1`
- Auth: anonymous / open rules on `/events/` path
- Live score data auto-expires (no manual cleanup needed)
- Pending event notifications: `/events/{id}/bundle` with `_publishedBy: 'ChubbsAdmin'`

### Updating player handicaps

Option A — Edit in ChubbsAdmin roster and re-push before the event.  
Option B — Export `cpi_roster.json` from the mobile app (Setup → Data → Export roster), edit the JSON, re-import.

### Season records (Gold Jacket / Clown Jacket)

Badge counts live in the **roster** stored in each device's `localStorage`. To update after a new Chubbs weekend:
1. Export roster JSON from the mobile app
2. Edit the `goldJackets`, `clownJackets`, `scrambleWins` fields
3. Re-import — the app uses `Math.max()` so it never overwrites a higher value

---

*Built by Michael Hanson + Claude (claude-sonnet-4-6 · Claude Code) · 2026*  
*Chubbs Golf is free for the group. Tip the dev: WeChat Pay → MPH_SIC*
