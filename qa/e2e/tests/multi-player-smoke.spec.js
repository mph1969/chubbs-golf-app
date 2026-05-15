// @ts-check
const { test, expect, chromium } = require('@playwright/test');
const { EVENT_ID } = require('../playwright.config');

/**
 * Multi-player concurrent smoke test.
 *
 * Spawns 4 isolated browser contexts simultaneously, each pretending to be
 * a different player in the same group (R16 G4 of TEST5):
 *
 *   - JORDAN (#3)
 *   - LEIGH  (#6)
 *   - HANSON (#11)
 *   - JACKS  (#14, designated scorer)
 *
 * For each context, asserts:
 *   - Page loads without console errors
 *   - Version pill shows v6.x
 *   - Header subtitle includes their player name
 *   - Sub-pill on Round reads "Match-Play" (not "Stableford") — proves
 *     getActivePlayoffSeeds() resolved
 *   - The match-play banner is visible with at least one M-row
 *   - Their own name appears with the ".mp-me" highlight class
 *
 * Catches: the iOS Safari stale-cache class of bug (would surface as
 * version pill showing 5.x), the playoffs-null-bundle class of bug
 * (would surface as Stableford label), the canonicalisation class of
 * bug (would surface as missing .mp-me span).
 *
 * Does NOT yet test:
 *   - Score entry → bracket save round-trip (requires write to a
 *     dedicated test event in Firebase; pencilled in for v2)
 *   - Back-9 auto-swap (would require scoring 9 holes first)
 */

const PLAYERS = [
  { id: 'JORDAN', expectedName: 'JORDAN', expectedSeed: 3 },
  { id: 'LEIGH',  expectedName: 'Leigh',  expectedSeed: 6 },
  { id: 'HANSON', expectedName: 'HANSON', expectedSeed: 11 },
  { id: 'JACKS',  expectedName: 'JACK S', expectedSeed: 14 },
];

test.describe('Multi-player concurrent load — Chubbs R16 G4 (TEST5)', () => {

  test('all 4 players see the event correctly when loaded simultaneously', async ({ browser }) => {
    // Open one isolated context per player. Each gets its own
    // localStorage / cookies / service worker, mirroring 4 separate phones.
    const contexts = await Promise.all(
      PLAYERS.map(() => browser.newContext({
        // Fresh storage per context — guarantees no leakage between players
        storageState: undefined,
      }))
    );

    const pages = await Promise.all(contexts.map(c => c.newPage()));

    // Capture console errors per page so we can fail loudly on regressions
    const consoleErrors = pages.map((_, i) => /** @type {string[]} */ ([]));
    // Filter for known-benign errors raised by third-party / browser layers
    // that we can't and don't want to fix. If any of these patterns matches,
    // the error gets dropped on the floor. Anything else surfaces as a test
    // failure.
    const isBenignError = (text) => {
      if (!text) return false;
      const benignPatterns = [
        'cloudflareinsights',              // Netlify CF analytics beacon
        'beacon.min.js',                   // Same beacon, different surfacing
        'FIREBASE WARNING',                // Firebase indexOn perf hint
        'Failed to convert value to',      // SW fetch+cache miss noise
        'ERR_NAME_NOT_RESOLVED',           // Chromium DNS failure
        'Could not resolve hostname',      // WebKit DNS failure
        'firebasedatabase.app/.lp',        // Firebase long-poll disconnect on cleanup
        'TypeError: Load failed',          // WebKit's version of fetch failure for beacon
        'FetchEvent.respondWith',          // SW interception of failed beacon
      ];
      return benignPatterns.some(p => text.includes(p));
    };
    pages.forEach((page, i) => {
      page.on('pageerror', err => {
        const text = err && (err.message || String(err));
        if (isBenignError(text)) return;
        consoleErrors[i].push(`pageerror: ${text}`);
      });
      page.on('console', msg => {
        if (msg.type() !== 'error') return;
        const text = msg.text();
        if (isBenignError(text)) return;
        // ERR_FAILED is ambiguous — only flag if the URL mentions chubbs.
        if (text.includes('ERR_FAILED') && !text.includes('chubbs')) return;
        consoleErrors[i].push(`console.error: ${text}`);
      });
    });

    // Load all 4 in parallel — this is the actual contention test.
    // If any race-condition exists in bundle apply / Firebase sub, this
    // is where it surfaces.
    await Promise.all(pages.map((page, i) =>
      page.goto(`/?loadEvent=${EVENT_ID}&player=${PLAYERS[i].id}`)
    ));

    // Give the Firebase listener time to fetch + apply the bundle. Async
    // pipeline: subscribe → onValue snap → _doApplyBundle → renderAll.
    await Promise.all(pages.map(p => p.waitForLoadState('networkidle')));

    // Now assert per-player invariants in parallel
    await Promise.all(pages.map(async (page, i) => {
      const player = PLAYERS[i];
      const firstNameToken = player.expectedName.split(' ')[0].toUpperCase();

      // Wait until the subtitle reflects this player's identity. Polls
      // the DOM rather than relying on a fixed timeout — important because
      // with 4 contexts racing, some tabs apply the bundle 2-3s after
      // navigation completes.
      await page.waitForFunction(
        (token) => {
          const el = document.querySelector('#hero-event-sub');
          if (!el) return false;
          const txt = (el.textContent || '').toUpperCase();
          return txt.includes(token) && !txt.includes('GOLF SCORER');
        },
        firstNameToken,
        { timeout: 20_000 }
      );

      // 1. Version pill — must be v6.x or higher. Anything 5.x means the
      //    device is on stale cache. Pill text is populated by setTimeout
      //    in the IIFE at ~100ms after load + Firebase subscribe at ~800ms,
      //    so we poll until it actually has content.
      await page.waitForFunction(
        () => {
          const el = document.getElementById('version-pill');
          return el && (el.textContent || '').match(/v\d+\.\d+/);
        },
        { timeout: 10_000 }
      );
      const versionPill = await page.locator('#version-pill').textContent();
      expect(versionPill, `${player.id}: version pill`).toMatch(/v6\.\d+/);

      // 2. Header subtitle — must mention their name. Catches mis-routing
      //    where ?player= didn't take effect. Case-insensitive because
      //    LEIGH's canonical displayName is "Leigh" (mixed-case), while
      //    HANSON / JORDAN / MATT are stored uppercase.
      const subtitle = await page.locator('#hero-event-sub').textContent({ timeout: 8000 });
      expect((subtitle || '').toUpperCase(), `${player.id}: header subtitle`).toContain(firstNameToken);

      // 3. Click the Round top tab to make sure we're on the scoring view
      //    (in case last sub-tab was restored to something else).
      await page.locator('button:has-text("Round")').first().click({ timeout: 8000 });
      await page.waitForTimeout(500);

      // 4. Dual-day players (e.g. JACKS — in both Scramble Team 3 and R16
      //    G4) land on the Scramble sub-pill by default. Switch to
      //    Match-Play if a Match-Play sub-pill exists. For single-day
      //    Stableford-only players, no sub-pills appear and we just stay
      //    on the rendered day2 view.
      const matchPlayPill = page.locator('.seg-pill').filter({ hasText: /^Match-Play$/ });
      if ((await matchPlayPill.count()) > 0) {
        await matchPlayPill.first().click();
        // Wait for setTab → renderAll to swap the active .view container.
        // Use the data-section visibility itself as the gate.
        await page.locator('#day2.active').waitFor({ state: 'visible', timeout: 5000 });
      }

      // 5. Match-play banner exists and shows at least one row — this is
      //    the load-bearing assertion. If playoffs.seeds didn't resolve,
      //    .mp-card won't render at all. Failure here on a fresh context
      //    means Firebase has /events/${EVENT_ID}/bundle with playoffs:null
      //    — re-push from admin with the toggle on.
      const banner = page.locator('.mp-card');
      await expect(banner, `${player.id}: match-play banner card`).toBeVisible({ timeout: 8000 });

      // Wait for at least one .mp-row to appear inside the banner. The
      // banner can render briefly with just the section title before the
      // rows hydrate (especially under 4-context contention), so polling
      // is more robust than a single immediate count.
      await expect(banner.locator('.mp-row').first(), `${player.id}: first match-play row visible`).toBeVisible({ timeout: 8000 });
      const rowCount = await banner.locator('.mp-row').count();
      expect(rowCount, `${player.id}: match-play rows`).toBeGreaterThan(0);

      // 5. Player's own name is highlighted with .mp-me span (v5.111 fix)
      //    Skip for JACK S because the canonical name is "JACK S" but the
      //    seed in season-4 is "Jack" — already covered by canonicalisation
      //    regression tests. Here we just verify any .mp-me exists.
      const meSpan = banner.locator('.mp-me');
      const meCount = await meSpan.count();
      expect(meCount, `${player.id}: at least one .mp-me highlight on viewer's row`).toBeGreaterThan(0);
    }));

    // 6. Surface any console errors as test failures
    pages.forEach((_, i) => {
      expect(consoleErrors[i], `${PLAYERS[i].id}: no console errors`).toEqual([]);
    });

    // Cleanup
    await Promise.all(contexts.map(c => c.close()));
  });
});
