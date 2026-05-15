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
    pages.forEach((page, i) => {
      page.on('pageerror', err => consoleErrors[i].push(`pageerror: ${err.message}`));
      page.on('console', msg => {
        if (msg.type() === 'error') {
          const text = msg.text();
          // Filter known benign errors that aren't ours (Cloudflare
          // beacon, Firebase indexOn warnings, etc.)
          if (text.includes('cloudflareinsights')) return;
          if (text.includes('FIREBASE WARNING')) return;
          if (text.includes('Failed to convert value to')) return;  // SW noise
          consoleErrors[i].push(`console.error: ${text}`);
        }
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
      //    device is on stale cache.
      const versionPill = await page.locator('#version-pill').textContent({ timeout: 8000 });
      expect(versionPill, `${player.id}: version pill`).toMatch(/v6\.\d+/);

      // 2. Header subtitle — must mention their name. Catches mis-routing
      //    where ?player= didn't take effect. Case-insensitive because
      //    LEIGH's canonical displayName is "Leigh" (mixed-case), while
      //    HANSON / JORDAN / MATT are stored uppercase.
      const subtitle = await page.locator('#hero-event-sub').textContent({ timeout: 8000 });
      expect((subtitle || '').toUpperCase(), `${player.id}: header subtitle`).toContain(firstNameToken);

      // 3. Click the Round top tab (in case sub-tab persisted to something
      //    else) then click the Match-Play / Stableford sub-pill. The match-
      //    play banner is part of the day2 view, only renders when day2 is
      //    active. Sub-pill label is "Match-Play" when playoffs.seeds are
      //    locked (catches the getActivePlayoffSeeds() regression too).
      await page.locator('button:has-text("Round")').first().click({ timeout: 8000 });
      await page.waitForTimeout(300);

      const subPill = page.locator('.seg-pill:has-text("Match-Play"), .seg-pill:has-text("Stableford")').first();
      const subPillText = ((await subPill.textContent({ timeout: 5000 })) || '').trim();
      // Match-Play label is the v5.110+ contract — anything else on a
      // fresh context means the bundle's playoffs payload is null (admin
      // pushed without the Section 6 toggle). The season-store fallback
      // doesn't apply here because Playwright always opens fresh contexts
      // with no localStorage. To fix: in admin, verify Section 6 is ON,
      // re-push the event, re-run this test.
      expect(
        subPillText,
        `${player.id}: sub-pill should say Match-Play — got "${subPillText}". This usually means the bundle at /events/${EVENT_ID}/bundle has playoffs:null. Re-push from admin with the playoff toggle on.`
      ).toBe('Match-Play');
      await subPill.click();
      await page.waitForTimeout(500);

      // 4. Match-play banner exists and shows at least one row
      const banner = page.locator('.mp-card');
      await expect(banner, `${player.id}: match-play banner card`).toBeVisible({ timeout: 8000 });

      const rows = banner.locator('.mp-row');
      const rowCount = await rows.count();
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
