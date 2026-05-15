# Firebase rules tests

Verifies the Realtime Database rules in `database.rules.json` allow / deny
the paths that ChubbsMobileApp + ChubbsAdmin actually use. Specifically
catches the **v5.59 → v6.0 regression class**: someone removes a path
block from the rules without realising downstream code still depends on
it (the honeypot removal silently dropped the `/chubbs/*` write rule,
which broke `Publish v6.0 as current` and `Broadcast reload` 5 deploys
later).

## Why this matters

| Path | Used by |
|---|---|
| `/events/{id}/bundle` | Admin push, mobile pull, cache, verify-mobile |
| `/events/{id}/groups/{g}` | Live scoring sync, back-9 group writes |
| `/events/{id}/_loadHits` | Admin "Verify mobile access" panel |
| `/chubbs/currentVersion` | `publishCurrentVersion()` write, version pill subscribe |
| `/chubbs/forceReload` | `broadcastReload()` write, force-reload subscribe |
| `/admin` | Legacy admin scratch (kept for back-compat) |

If any of these stops working, scoring or operational tools break.

## One-time setup

**Java 17+** is required for the Firebase emulator. Verify:

```bash
java -version
```

Then install Firebase CLI:

```bash
npm install -g firebase-tools
```

From this directory:

```bash
cd qa/firebase_rules
npm install
```

## Running the tests

```bash
# Starts the emulator, runs the tests, tears down. One command.
npm run test:with-emulator
```

Or to keep the emulator running across test iterations (faster
during dev):

```bash
# Terminal 1 — start emulator
npm run emulator

# Terminal 2 — run tests as many times as you like
npm test
```

## Updating rules

The flow:

1. Edit `database.rules.json` here.
2. Re-run `npm run test:with-emulator` — must pass.
3. Copy the JSON to Firebase Console → Realtime Database → Rules.
4. Click **Publish** in the console.
5. Update `docs/firebase-rules.md` with the change reason.

The repo file and the console are independent — tests verify the local
file, but Firebase enforces what's in the console. They drift if you
forget step 3.

## What the tests cover

`tests/rules.spec.js`:

- `/events` read at root (admin scan)
- `/events/{id}/bundle` read + write
- `/events/{id}/groups/{g}` write
- `/events/{id}/_loadHits` push
- `/chubbs/currentVersion` read + write
- `/chubbs/forceReload` read + write
- `/chubbs/arbitrary-future-path` write (regression test — locks down the
  fact that the entire `/chubbs/*` subtree is writable; if a future
  edit narrows it to specific keys only, this test fails loud)
- `/admin` read + write
- `/random-path` denied (read + write)
- `/root-level-key` denied
