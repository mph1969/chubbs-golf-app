# Activity dashboard — design sketch

**Filed:** 2026-05-16 (task #21)
**Status:** backlog (not building yet)
**Use cases:**
- Pre-event: confirm brain trust is actually testing the app on their phones
- Day-of: confirm scorers are hitting the app live, no silent dropouts
- Post-event: review usage history (who scored what, when, from where)
- Diagnostic: trace "I think my data didn't save" complaints to actual writes

---

## Data already collected (no new plumbing needed)

| Firebase path | What it captures | Volume |
|---|---|---|
| `/events/{eventId}/_loadHits` | Every page load. `{at: timestamp, device: UA, player: playerId}` | ~10-20 per event per player over a session. TEST5 had 187 hits by end of pre-event testing. |
| `/events/{eventId}/groups/{gid}` | Live scoring writes — per-hole grosses, putts, scorerPlayerId | Updates every hole entry from the scorer |
| `/events/{eventId}/groups/{gid}.half` | `'r16'` vs `'back9'` flag (Tier 2c) | One write per group when back-9 swap fires |
| `/events/{eventId}/challengeWinners` | Challenge winner picks | Few writes per event |
| `/chubbs/currentEvent` | Last "marked as live" event | Single record |
| `/chubbs/currentVersion` | Published APP_VERSION marker | Single record |

The dashboard is a UI on top of this — no schema changes.

---

## Sections (4)

### 1. Live now (last 60s)

Top of dashboard, auto-refreshing every 5-10s. Surfaces:

```
🟢 LIVE NOW (12 active in the last minute)

  R16 G1  Matt v Jamie · Terry v Paul
          ✏️ Terry scoring · last write 8s ago · H4
          👁 Matt viewing · 32s ago · iPhone
          👁 Jamie viewing · 47s ago · iPhone

  R16 G2  George v Anthony · Ryan N v Kevin
          ✏️ Ryan N scoring · last write 18s ago · H3
          👁 George viewing · 22s ago · iPhone
          ⚠ Kevin — no activity in last 5 min
```

Heuristics:
- "Scoring" = recent `groups/{gid}.holes[].gross` write
- "Viewing" = recent `_loadHits` entry, no scoring writes
- "No activity" warning if a roster player has no hit in last 5 min during active hours

### 2. Today (since midnight UTC or last 24h)

```
TODAY (2026-05-23 · May Chubbs at Yinli)
  Page loads        342
  Unique players    18 of 22 in roster
  Score writes      168 (avg 9.3 per active scorer)
  Match-play saves  6 of 8 R16 brackets locked
  Console errors    0
```

### 3. Per-player breakdown

Scrollable list:

```
HANSON   ●●●●●●●●  loaded 23 times · last 12s ago · iPhone Safari · v6.1
TERRY    ●●●●●●●●  loaded 19 times · last 1m ago · iPhone Safari · v6.1
JACK S   ●●●●●●●●  loaded 17 times · last 23s ago · iPhone Safari · v6.1
LEIGH    ●●●●●●○○  loaded 11 times · last 8m ago · iPhone Safari · v6.1
KEVIN    ●●●○○○○○  loaded 4 times  · last 2h ago · iPhone Safari · v6.0  ⚠ stale version
DIEGO    ○○○○○○○○  never loaded                                          🚨 no activity
```

The dots are a visual heatmap of recent activity by hour. The stale-version flag uses the v6.x convention to spot devices that haven't upgraded.

### 4. Per-event activity (for backwards exploration)

Dropdown to pick an event ID. Shows the same stats scoped to that event. Useful for post-mortem: "did the brain trust actually test TEST5?" → pick TEST5 in dropdown, see all 14 brain trust members' load history.

---

## Where this lives

**Option A: New Admin sub-pill** — Players / Event / Courses / Settings / Data / **Activity**. Mobile-only, master mode gated. Doesn't add a new top tab.

**Option B: Top tab in admin tool** — moves it out of the mobile app entirely. The ChubbsAdmin desktop UI gets an Activity tab. Better for an organiser sitting at a laptop watching the event unfold. Probably the right home.

**Recommendation:** B. Put it on the admin web app (chubbs-admin.netlify.app). The organiser is the only consumer; the mobile app is for players who don't need this. Also avoids bloating the mobile bundle.

---

## Privacy / consent

`_loadHits` already collects device UA + player ID. This is implicit telemetry. Adding a dashboard makes it visible to organisers (Hanson, Terry per ADMIN_PLAYERS allowlist).

No new data collected — just a new view of existing data. Worth a brief note in the WeChat blast or post-event recap: "the organiser can see device activity for the event (when you loaded, what device, scoring writes). No location, no personal info beyond what you already provide."

---

## Implementation effort

| Piece | Effort |
|---|---|
| Firebase reads + aggregation logic | 1-2 hrs |
| Live-now section with auto-refresh | 1 hr |
| Per-player heatmap rendering | 1 hr |
| Per-event dropdown + scoping | 30 min |
| Stale-version flagging | 30 min |
| Admin-side UI + nav | 1 hr |
| **Total** | **~5-6 hrs** |

---

## Stretch features (post-MVP)

- Slack/WeChat webhook for "no activity in 10min during active event" warning
- CSV export of session activity
- Per-event "scorer compliance" report (designated scorer vs actual scorer)
- Geographic ping (if a player consents to geolocation — useful for hole-by-hole "Hanson is on H7")
- Visualisation: timeline of who-was-where-when during the event

---

## Open questions for when this gets built

1. **Should _loadHits get pruned?** 187 entries from one test session; over a year of LIVE events this grows fast. Add a 30-day TTL cleanup job? (Same Path A/B discussion as `/games/*` cleanup for DX! Golf.)
2. **Track scoring writes too?** Currently only loadHits has explicit timestamps. Scoring writes don't include `at` — would need to add `lastWriteAt: ServerValue.TIMESTAMP` to the scoring group writes for "last scoring touch" to work.
3. **What's "active"?** 60 seconds? 5 minutes? Need a clear definition for the live-now section.
