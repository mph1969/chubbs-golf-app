// @ts-check
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { initializeTestEnvironment, assertSucceeds, assertFails } = require('@firebase/rules-unit-testing');

/**
 * Firebase Realtime Database rules tests.
 *
 * Verifies the production rules in qa/firebase_rules/database.rules.json
 * allow / deny the paths that ChubbsMobileApp and ChubbsAdmin actually
 * read + write. Catches the v5.59 → v6.0 class of regression where the
 * /chubbs/* write rule got dropped silently with the honeypot removal.
 *
 * Run:
 *   1. Install Firebase CLI: `npm install -g firebase-tools`
 *      (one-time, ~100MB. Requires Java 17+ on PATH for emulator.)
 *   2. From qa/firebase_rules/:
 *      npm install
 *      npm run test:with-emulator
 *
 * What this verifies:
 *   - /events/{id}/bundle      — anyone read + write (admin push, mobile pull)
 *   - /events/{id}/groups/{g}  — anyone read + write (live scoring sync)
 *   - /events/{id}/_loadHits   — anyone read + write (verify-mobile pings)
 *   - /events root             — anyone read (so admin can scan for pending)
 *   - /chubbs/currentVersion   — anyone read + write (Publish button)
 *   - /chubbs/forceReload      — anyone read + write (Broadcast button)
 *   - /admin                   — anyone read + write (legacy admin scratch)
 *   - /unknown                 — denied (nothing else is exposed)
 *
 * When rules change in database.rules.json, both the production console
 * (Firebase → Realtime Database → Rules) AND these tests need to update.
 * Drift between them is the same class of latent bug we hit at v5.59.
 */

const RULES = fs.readFileSync(
  path.join(__dirname, '..', 'database.rules.json'),
  'utf-8'
);

let env;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: 'chubbs-rules-test',
    database: { rules: RULES },
  });
});

after(async () => {
  if (env) await env.cleanup();
});

beforeEach(async () => {
  if (env) await env.clearDatabase();
});

describe('/events path', () => {
  it('anyone can read the root /events node (for admin pending-event scan)', async () => {
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(db.ref('events').once('value'));
  });

  it('anyone can write to /events/{id}/bundle (admin push)', async () => {
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(
      db.ref('events/2026-TEST-EVENT/bundle').set({
        event: { eventId: '2026-TEST-EVENT' },
        players: [],
        _publishedAt: Date.now(),
      })
    );
  });

  it('anyone can write to /events/{id}/groups/{groupId} (live scoring)', async () => {
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(
      db.ref('events/2026-TEST-EVENT/groups/G1').set({
        holes: [{ gross: 4 }],
        half: 'r16',
      })
    );
  });

  it('anyone can push to /events/{id}/_loadHits (verify-mobile pings)', async () => {
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(
      db.ref('events/2026-TEST-EVENT/_loadHits').push({
        at: Date.now(),
        device: 'test',
      })
    );
  });

  it('anyone can read /events/{id}/bundle (mobile pulls)', async () => {
    // Seed data first via the privileged path so the read has something to find.
    await env.withSecurityRulesDisabled(async (ctx) => {
      await ctx.database().ref('events/seed-evt/bundle').set({ event: { eventId: 'seed-evt' } });
    });
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(db.ref('events/seed-evt/bundle').once('value'));
  });
});

describe('/chubbs path (v6.0 — version-broadcast paths)', () => {
  it('anyone can write to /chubbs/currentVersion (📌 Publish vX.Y as current)', async () => {
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(
      db.ref('chubbs/currentVersion').set({ version: '6.0', ts: Date.now() })
    );
  });

  it('anyone can read /chubbs/currentVersion (version-pill subscribe)', async () => {
    await env.withSecurityRulesDisabled(async (ctx) => {
      await ctx.database().ref('chubbs/currentVersion').set({ version: '6.0', ts: 1 });
    });
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(db.ref('chubbs/currentVersion').once('value'));
  });

  it('anyone can write to /chubbs/forceReload (📡 Broadcast reload)', async () => {
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(
      db.ref('chubbs/forceReload').set({ ts: Date.now(), message: 'New build pushed' })
    );
  });

  it('anyone can read /chubbs/forceReload (force-reload subscribe)', async () => {
    await env.withSecurityRulesDisabled(async (ctx) => {
      await ctx.database().ref('chubbs/forceReload').set({ ts: 1, message: 'm' });
    });
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(db.ref('chubbs/forceReload').once('value'));
  });

  it('regression: /chubbs/* must remain writable (v5.59 honeypot-removal cautionary)', async () => {
    // The v5.59 honeypot removal dropped the /chubbs rule entirely, breaking
    // /chubbs/currentVersion + /chubbs/forceReload silently in v6.0. This test
    // exists specifically to catch that class of regression on a future rules
    // edit. If anyone removes the /chubbs block again, this fails.
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(db.ref('chubbs/arbitrary-future-path').set({ at: Date.now() }));
  });
});

describe('/admin path', () => {
  it('anyone can write to /admin (legacy scratch)', async () => {
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(db.ref('admin/foo').set({ at: Date.now() }));
  });

  it('anyone can read /admin', async () => {
    await env.withSecurityRulesDisabled(async (ctx) => {
      await ctx.database().ref('admin/foo').set({ at: 1 });
    });
    const db = env.unauthenticatedContext().database();
    await assertSucceeds(db.ref('admin/foo').once('value'));
  });
});

describe('unknown paths (default deny)', () => {
  it('cannot write to /random-path/foo', async () => {
    const db = env.unauthenticatedContext().database();
    await assertFails(db.ref('random-path/foo').set({ at: Date.now() }));
  });

  it('cannot read /random-path/foo', async () => {
    const db = env.unauthenticatedContext().database();
    await assertFails(db.ref('random-path/foo').once('value'));
  });

  it('cannot write to /root-level-key', async () => {
    const db = env.unauthenticatedContext().database();
    await assertFails(db.ref('root-level-key').set('value'));
  });
});
