# Chubbs E2E tests (Playwright)

End-to-end browser automation against `chubbs-golf.netlify.app`. Spawns
multiple isolated browser contexts to simulate the brain-trust dry-run —
catches multi-device timing / sync / canonicalisation regressions that
single-tab manual testing misses.

## First-time setup

```bash
cd qa/e2e
npm install
npx playwright install chromium webkit   # downloads browser binaries (~200MB)
```

## Run

```bash
npm test                    # headless, all projects
npm run test:headed         # see the browsers open
npm run test:debug          # step through with Playwright inspector
npm run report              # open the last HTML report
```

To target a different deployment or event:

```bash
BASE_URL=https://deploy-preview-42--chubbs-golf.netlify.app npm test
EVENT_ID=2026-LIVE-MAY-LIVE-20260523 npm test
```

## What it tests

`tests/multi-player-smoke.spec.js`:
- Spawns 4 isolated browser contexts in parallel (JORDAN / LEIGH / HANSON / JACK S — R16 G4 of TEST5)
- Each loads `?loadEvent=2026-TEST5-Brai&player={id}` simultaneously
- Asserts version pill is v6.x (not stale cache)
- Asserts header shows the right player name (URL param took effect)
- Asserts Match-Play sub-pill renders (not Stableford — means playoffs.seeds resolved)
- Asserts match-play banner is visible with at least one row
- Asserts viewer's own name has `.mp-me` highlight (canonicalisation worked)
- Asserts no console errors (filtered Cloudflare beacon + Firebase indexOn warnings)

## What it does NOT test (yet)

- Score entry → bracket save round-trip via Firebase
- Back-9 auto-swap on hole 10
- Cup QF / Plate QF cascade after R16 closes
- iOS-Safari-specific quirks (use a real device, no good substitute)

## CI

For GitHub Actions, set `CI=1` env so the runner uses the `github`
reporter and enables 1 retry per test. Suggested workflow:

```yaml
- run: cd qa/e2e && npm ci
- run: cd qa/e2e && npx playwright install --with-deps chromium webkit
- run: cd qa/e2e && npm test
  env:
    CI: '1'
```

## Notes

- Tests assume `TEST5-Brai` event exists in Firebase with a valid playoff
  bundle. If you publish a new test event, set `EVENT_ID` accordingly.
- Tests are **read-only** against Firebase by design — they don't push
  scores or save brackets. Adding write tests would require a dedicated
  sandbox event so they don't pollute LIVE data.
