# Firebase Realtime Database Rules — Chubbs

Source of truth for the Firebase rules used by the mobile PWA + admin portal.
When anything changes here, also paste the JSON into **Firebase Console →
Realtime Database → Rules** and click **Publish** — the file in the repo is
documentation, Firebase enforces what's in the console.

---

## Current full ruleset (Phase A — includes honeypot paths)

**DO NOT add `.read: true` or `.write: true` at the root of `"rules"`.** Firebase
rule cascades: granting access at the root nullifies every stricter child rule
below — specifically, it'd break the press-ratchet rule that prevents malicious
writes bigger than +1.

The shape is path-specific all the way down. Paste this as the full ruleset:

```json
{
  "rules": {
    "events": {
      ".read": true,
      "$eventId": {
        ".write": true
      }
    },
    "admin": {
      ".read": true,
      ".write": true
    },
    "chubbs": {
      "presses": {
        "$player": {
          ".read": true,
          ".write": "newData.isNumber() && newData.val() === (data.val() || 0) + 1 && newData.val() <= 9999"
        }
      },
      "leaderboardPublished": {
        ".read": true,
        ".write": true
      }
    }
  }
}
```

### Merging into your existing rules

If `"events"` and `"admin"` already exist with your own tweaks, keep them as
they are and **add the `"chubbs": { ... }` block alongside** them. Don't nest
`"chubbs"` inside `"events"`. Don't wrap the whole thing in a root `.read/.write`.

### What each path does

| Path | Read | Write | Purpose |
|---|---|---|---|
| `/chubbs/leaderboardPublished` | anyone | anyone (Phase A) | Boolean flag. `true` = leaderboard visible to everyone; `false`/missing = honeypot gate active. Admin toolbar in the mobile app toggles this. |
| `/chubbs/presses/{PLAYER_KEY}` | anyone | ratchet-only (+1 per write, cap 9999) | Counter per player of "admin gate" tap-throughs. Server enforces the ratchet — even if someone tries to write directly, they can only nudge their own counter by +1 at a time. |
| `/events/{eventId}/bundle` | anyone | anyone | Existing — event config pushed by ChubbsAdmin, consumed by ChubbsMobileApp. (Whatever you had before, keep as-is.) |

---

## How to apply (step-by-step)

1. Open the Firebase Console for the **Chubbs** project.
2. Left sidebar → **Realtime Database**.
3. Top tabs → **Rules**.
4. You'll see your existing rules in a JSON editor.
5. Copy the JSON block above and paste it over the existing content.
   - If you had custom paths besides `/events`, merge them in under `"rules"`
     instead of replacing wholesale.
6. Click **Publish** (top-right).
7. Confirm by expanding **Data** tab and writing a test value — the Chubbs
   mobile app will also start recording presses immediately.

---

## Phase B (not yet built — server-side hardening)

If we ever lock down the admin toggle properly:

```json
"leaderboardPublished": {
  ".read": true,
  ".write": false
}
```

Then a Netlify Function using Firebase Admin SDK becomes the only writer.
Not needed for the friends-group scope.

---

## Security notes (Phase A trade-offs)

- **`leaderboardPublished` is world-writable.** In theory any player who finds
  the Firebase credentials in the client bundle could toggle it. Mitigation:
  nobody looks. If it happens, check the Firebase Rules logs and rotate.
- **`ADMIN_SECRET` is baked into the client** at `HONEYPOT.ADMIN_SECRET` in
  `ChubbsMobileApp_v5/index.html`. View-source reveals it. To rotate: edit
  the constant, push, Netlify redeploy. Old bookmarks with `?admin=<old>` stop
  working immediately.
- **Press ratchet rule is the real protection.** Even if someone builds a
  malicious client, they can only `+1` their own counter per write, capped at
  9999. Same rules as honest players. That's the intended game.
