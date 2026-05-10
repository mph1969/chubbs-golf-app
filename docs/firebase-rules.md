# Firebase Realtime Database Rules — Chubbs

Source of truth for the Firebase rules used by the mobile PWA + admin portal.
When anything changes here, also paste the JSON into **Firebase Console →
Realtime Database → Rules** and click **Publish** — the file in the repo is
documentation, Firebase enforces what's in the console.

---

## Current full ruleset (post-honeypot removal, v5.59)

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

The `.indexOn` line tells Firebase to maintain a server-side index on the
`bundle/_publishedAt` field of each event. Without it, Firebase warns
"Using an unspecified index" on every read and downloads the full `/events`
node before filtering client-side. With it, queries are filtered server-side.

### What each path does

| Path | Read | Write | Purpose |
|---|---|---|---|
| `/events/{eventId}/bundle` | anyone | anyone | Event config pushed by ChubbsAdmin, consumed by ChubbsMobileApp. Includes seeds, players, lineups, scorers, course config. |
| `/admin` | anyone | anyone | Generic admin scratch (legacy — used for cross-device coordination flags). |

---

## How to apply (step-by-step)

1. Open the Firebase Console for the **chubbs-golf** project.
2. Left sidebar → **Realtime Database**.
3. Top tabs → **Rules**.
4. You'll see your existing rules in a JSON editor.
5. Replace with the JSON block above.
6. Click **Publish** (top-right).

---

## Removed: Honeypot paths (Phase A, was v5.41 → v5.58)

The honeypot UI ("Most Pressed" throne, gator chomp prank, gate modal) was
retired 2026-05-10 in v5.59 after one event of fun-gimmick use. Removed
paths:

- `/chubbs/leaderboardPublished` — was the gate flag
- `/chubbs/presses/{PLAYER_KEY}` — was the press counter with ratchet write rule

When you publish the new rules above, those paths just stop being writable
through the app. Existing data under `/chubbs/` can be deleted from the
Firebase Console (Data tab → expand `chubbs` → trash icon) — purely
cosmetic, doesn't affect anything live.

The `chubbs_admin_unlock_v1` localStorage flag on phones is also harmless
and will age out as players reload the app over time.
