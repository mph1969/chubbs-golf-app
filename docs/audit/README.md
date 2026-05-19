# Chubbs Playoff Pool — Audit Trail

This folder is the paper-trail backup for the playoff betting pool.

Every time `qa/export_bets.py` runs, it drops a timestamped triple here:

| File | Purpose |
|---|---|
| `<eid>-<ts>-snapshot.json` | Raw Firebase data (bundle + bets + computed results if `--results`) |
| `<eid>-<ts>-picks.txt`     | WeChat-ready plain-text dump — paste into chat |
| `<eid>-<ts>-picks.html`    | Printable layout — open in browser, Ctrl+P, Save as PDF |

The repo is private and these files are committed, so anyone with repo
access has a tamper-proof record of every pick and the exact timestamp
at which it was captured. If Firebase is wiped or the live app
malfunctions on event day, fall back to the most recent snapshot.

## Suggested capture cadence

- **After bets lock** (Friday morning): one final pre-event snapshot.
  This is the legally-binding picks file.
- **After scoring completes** (Saturday evening): one snapshot with
  `--results` for the winner-payout calculation.

## Privacy

Bets are stored at `/events/{id}/bets/{punterId}` in Firebase Realtime
Database under a `.read: false` rule — only the database secret (held
by the admin) can read them. The form's submit path stays `.write: true`
so anyone with the WeChat link can still submit.
