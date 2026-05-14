// Back-9 Foursomes card — DevTools fixture
// =========================================
// Paste this entire block into the DevTools console on chubbs-golf.netlify.app
// to inject fake R16 results and visually verify the v5.72+ Back 9 Foursomes
// card rendering. Validates the actual JS path (_buildBackNineGroups +
// renderBackNineGroupsCard) which the Python qa/r16_to_qf_sim.py harness
// can't reach.
//
// Prereqs: hard-refresh after the v5.73 deploy lands. For scorer names to
// resolve, you should also have loaded the May 23 event (so state.eventBundle
// is populated). Without a bundle, the card still renders but the scorer
// line will say "⚠️ No scorer auto-assigned".
//
// Usage (after pasting):
//   chubbsTest.chalk()      — higher seed wins every R16 match
//   chubbsTest.upsets()     — M2, M5, M7 upsets (Paul, Ricardo, Jack S)
//   chubbsTest.allUpsets()  — every lower seed wins
//   chubbsTest.custom([0,1,0,0,1,0,1,0])  — 8 ints, 0 = higher seed wins
//   chubbsTest.status()     — log current seeds + r16
//   chubbsTest.clear()      — wipe R16 results, restore TBD state

(function() {
  const STORE_KEY = 'chubbs_seasons_v1';

  // Seed order matches the May 23 bracket. PAIRS visual order:
  //   M1 = #1 Matt   v #16 Jamie
  //   M2 = #8 Terry  v #9  Paul
  //   M3 = #4 George v #13 Anthony
  //   M4 = #5 Ryan N v #12 Kevin
  //   M5 = #2 Nick   v #15 Ricardo
  //   M6 = #7 Dustin v #10 John B
  //   M7 = #3 Jordan v #14 Jack S
  //   M8 = #6 Leigh  v #11 Hanson
  const SEEDS = [
    'Matt','Nick','Jordan','George','Ryan N','Leigh','Dustin','Terry',
    'Paul','John B','Hanson','Kevin','Anthony','Jack S','Ricardo','Jamie'
  ];
  const PAIRS = [[0,15],[7,8],[3,12],[4,11],[1,14],[6,9],[2,13],[5,10]];

  function loadStore() {
    try {
      return JSON.parse(localStorage.getItem(STORE_KEY) || '{"viewingSeasonId":"season-4","seasons":{}}');
    } catch (e) {
      return { viewingSeasonId: 'season-4', seasons: {} };
    }
  }

  function ensureSeason(store) {
    if (!store.seasons) store.seasons = {};
    if (!store.seasons['season-4']) {
      store.seasons['season-4'] = {
        id: 'season-4', name: 'Season 4 (2025-2026)',
        events: [], status: 'active', playoffs: {}
      };
    }
    if (!store.seasons['season-4'].playoffs) store.seasons['season-4'].playoffs = {};
    return store.seasons['season-4'];
  }

  function tryRender() {
    if (typeof renderAll === 'function') { try { renderAll(); return true; } catch (e) {} }
    if (typeof renderSeason === 'function') { try { renderSeason(); return true; } catch (e) {} }
    return false;
  }

  function inject(winnersMask) {
    if (!Array.isArray(winnersMask) || winnersMask.length !== 8) {
      console.error('[Chubbs test] need 8 ints — 0 = higher seed wins, 1 = lower seed wins');
      return;
    }
    const store = loadStore();
    const season = ensureSeason(store);
    season.playoffs.seeds = SEEDS.slice();
    season.playoffs.r16 = PAIRS.map((pair, i) => {
      const winnerIdx = winnersMask[i] === 0 ? pair[0] : pair[1];
      return { winner: SEEDS[winnerIdx], result: winnersMask[i] === 0 ? '3&2' : '2&1' };
    });
    // Clear downstream so the reshuffle is computed fresh
    delete season.playoffs.cup_qf;
    delete season.playoffs.plate_qf;
    delete season.playoffs.cup_sf;
    delete season.playoffs.plate_sf;
    delete season.playoffs.cup_final;
    delete season.playoffs.plate_final;
    delete season.playoffs.shield_sf;
    delete season.playoffs.shield_final;
    delete season.playoffs.spoon_sf;
    delete season.playoffs.spoon_final;
    store.viewingSeasonId = 'season-4';
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
    console.log('[Chubbs test] R16 injected:');
    season.playoffs.r16.forEach((m, i) => {
      const [a, b] = PAIRS[i];
      console.log('  M' + (i+1) + ': ' + SEEDS[a] + ' v ' + SEEDS[b] + ' → ' + m.winner);
    });
    const ok = tryRender();
    console.log('[Chubbs test] ' + (ok ? '✓ Re-rendered.' : '(no renderAll/renderSeason found — tap Standings tab to refresh)'));
  }

  window.chubbsTest = {
    chalk: () => inject([0,0,0,0,0,0,0,0]),
    upsets: () => inject([0,1,0,0,1,0,1,0]),
    allUpsets: () => inject([1,1,1,1,1,1,1,1]),
    custom: (w) => inject(w),
    status: () => {
      const store = loadStore();
      const season = store.seasons && store.seasons['season-4'];
      if (!season || !season.playoffs) { console.log('[Chubbs test] no season-4 data'); return; }
      console.log('[Chubbs test] seeds:', season.playoffs.seeds || '(none)');
      console.log('[Chubbs test] r16:', season.playoffs.r16 || '(none)');
    },
    clear: () => {
      const store = loadStore();
      const season = store.seasons && store.seasons['season-4'];
      if (season && season.playoffs) {
        ['r16','cup_qf','plate_qf','cup_sf','plate_sf','cup_final','plate_final',
         'shield_sf','shield_final','spoon_sf','spoon_final']
          .forEach(k => delete season.playoffs[k]);
        localStorage.setItem(STORE_KEY, JSON.stringify(store));
      }
      tryRender();
      console.log('[Chubbs test] ✓ R16 + downstream cleared.');
    }
  };

  console.log('[Chubbs test] Fixture loaded. Try:');
  console.log('  chubbsTest.chalk()       — all chalk');
  console.log('  chubbsTest.upsets()      — M2/M5/M7 upsets');
  console.log('  chubbsTest.allUpsets()   — every lower seed wins');
  console.log('  chubbsTest.custom([0,1,0,0,1,0,1,0])  — custom (8 ints, 0=higher seed)');
  console.log('  chubbsTest.status()      — show current state');
  console.log('  chubbsTest.clear()       — wipe and restore TBD');
})();
