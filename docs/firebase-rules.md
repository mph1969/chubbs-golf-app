# Firebase Realtime Database Rules — Chubbs

Source of truth for the Firebase rules used by the mobile PWA + admin portal.
When anything changes here, also paste the JSON into **Firebase Console →
Realtime Database → Rules** and click **Publish** — the file in the repo is
documentation, Firebase enforces what's in the console.

---

## Current full ruleset (v6.0 — version-broadcast paths re-added)

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
    },
    "chubbs": {
      ".read": true,
      ".write": true
    }
  }
}
```

The `.indexOn` line tells Firebase to maintain a server-side index on the
`bundle/_publishedAt` field of each event. Without it, Firebase warns
"Using an unspecified index" on every read and downloads the full `/events`
node before filtering client-side. With it, queries are filtered server-side.

### What each path does

| Path | Read | Write | Purpose |
|---|---|---|---|
| `/events/{eventId}/bundle` | anyone | anyone | Event config pushed by ChubbsAdmin, consumed by ChubbsMobileApp. Includes seeds, players, lineups, scorers, course config. |
| `/admin` | anyone | anyone | Generic admin scratch (legacy — used for cross-device coordination flags). |
| `/chubbs/currentVersion` | anyone | anyone | Master-mode "📌 Publish vX.Y as current" button writes here. Mobile devices subscribe and turn their version pill red when their running APP_VERSION is lower. |
| `/chubbs/forceReload` | anyone | anyone | Master-mode "Broadcast reload to all" button bumps the timestamp here. Mobile devices subscribe and trigger a SW update check + soft-reload banner. |

---

## How to apply (step-by-step)

1. Open the Firebase Console for the **chubbs-golf** project.
2. Left sidebar → **Realtime Database**.
3. Top tabs → **Rules**.
4. You'll see your existing rules in a JSON editor.
5. Replace with the JSON block above.
6. Click **Publish** (top-right).

---

## History — honeypot removal + version-broadcast re-add

The honeypot UI ("Most Pressed" throne, gator chomp prank, gate modal) was
retired 2026-05-10 in v5.59 after one event of fun-gimmick use. That removal
dropped the entire `/chubbs/*` write rule because the only paths under it
at the time were honeypot:

- `/chubbs/leaderboardPublished` — was the gate flag (removed)
- `/chubbs/presses/{PLAYER_KEY}` — was the press counter (removed)

In v6.0 (2026-05-15) two new paths landed under `/chubbs/*` for cross-device
operational coordination:

- `/chubbs/currentVersion` — version-pill staleness signal
- `/chubbs/forceReload` — admin broadcast-reload trigger

Both were silently broken until the `window.SYNC` fix in the v6.1 cache.
Once that fix exposed the calls, the missing `/chubbs/*` write rule started
returning `PERMISSION_DENIED` to every Publish click. **Re-adding the
`/chubbs` block to the rules (above) is required** for the master-mode
Publish + Broadcast buttons to work.

The `chubbs_admin_unlock_v1` localStorage flag on phones is harmless
legacy and will age out as players reload the app over time.
