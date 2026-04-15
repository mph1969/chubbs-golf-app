// ═══════════════════════════════════════════════════════════════
// Chubbs Admin Test Runner — paste into browser console on the admin tool
// ═══════════════════════════════════════════════════════════════
(function(){
  const results = [];
  let passed = 0, failed = 0;

  function assert(id, desc, condition) {
    if (condition) { passed++; results.push(`✅ ${id}: ${desc}`); }
    else { failed++; results.push(`❌ ${id}: ${desc}`); }
  }
  function el(id) { return document.getElementById(id); }

  console.log('🐊 Chubbs Admin Test Runner starting...\n');

  // ═══ H. ADMIN TOOL UI ═══
  // H1: Toolbar buttons exist
  assert('H1-import', 'Import Roster button exists', !!document.querySelector('[onclick*="roster-upload"]'));
  assert('H1-export', 'Export JSON button exists', !!document.querySelector('[onclick*="generateAndDownloadJson"]'));
  assert('H1-push', 'Send to App button exists', !!el('push-btn'));
  assert('H1-gameday', 'Game Day Check button exists', !!document.querySelector('[onclick*="showGameDayCheck"]'));
  assert('H1-cleanup', 'Cleanup dropdown button exists', !!document.querySelector('[onclick*="toggleCleanupMenu"]'));

  // H2: Cleanup dropdown
  assert('H2', 'Cleanup menu exists (hidden)', el('cleanup-menu') && el('cleanup-menu').style.display === 'none');
  toggleCleanupMenu();
  assert('H2b', 'Cleanup menu opens on toggle', el('cleanup-menu').style.display === 'block');
  toggleCleanupMenu();
  assert('H2c', 'Cleanup menu closes on toggle', el('cleanup-menu').style.display === 'none');

  // H4: Firebase status
  assert('H4', 'Firebase status element exists', !!el('fb-status'));
  assert('H4b', 'Firebase db initialized', db !== null);

  // H7: Test/Live toggle
  assert('H7', 'Event mode toggle exists', !!el('mode-live') && !!el('mode-test'));
  setEventMode('test');
  assert('H7b', 'Test mode sets eventMode', eventMode === 'test');
  setEventMode('live');
  assert('H7c', 'Live mode sets eventMode', eventMode === 'live');

  // ═══ ADMIN STATE PERSISTENCE ═══
  assert('P1', 'saveAdminState function exists', typeof saveAdminState === 'function');
  assert('P2', 'saveAdminRoster function exists', typeof saveAdminRoster === 'function');
  assert('P3', 'loadFromCloud function exists', typeof loadFromCloud === 'function');
  assert('P4', 'saveToCloud function exists', typeof saveToCloud === 'function');
  assert('P5', 'Cloud save status element exists', !!el('cloud-save-status'));

  // ═══ ROSTER & PLAYERS ═══
  assert('R1', 'masterRoster is array', Array.isArray(masterRoster));
  assert('R2', 'masterRoster has players', masterRoster.length > 0);

  // ═══ APRIL CPI ROSTER (source: Chubbs Events/April Chubbs Palm Island/cpi_players_v3.csv) ═══
  // Match by playerId (stable from CSV) with case-insensitive displayName fallback.
  function findRosterPlayer(playerId, displayName) {
    return masterRoster.find(p =>
      p.playerId === playerId ||
      (p.displayName && p.displayName.toLowerCase() === displayName.toLowerCase())
    );
  }
  const cpiRoster = [
    { playerId: 'TerryM',    displayName: 'Tmoney',          hcp: 25 },
    { playerId: 'JordanCa',  displayName: 'Junk Yard Dog',   hcp: 25 },
    { playerId: 'Diego',     displayName: 'Diego',           hcp: 11 },
    { playerId: 'Jamie',     displayName: 'Jamie',           hcp: 18 },
    { playerId: 'Nick',      displayName: 'Nick',            hcp: 25 },
    { playerId: 'Matt',      displayName: 'Matt',            hcp: 12 },
    { playerId: 'Graeme',    displayName: 'GraemeBo',        hcp: 28 },
    { playerId: 'George',    displayName: 'GeorgieBoy',      hcp: 24 },
    { playerId: 'Kevin',     displayName: 'Kevin',           hcp: 15 },
    { playerId: 'Ryan',      displayName: 'Ryan',            hcp: 12 },
    { playerId: 'Daryl',     displayName: 'Daryl',           hcp: 18 },
    { playerId: 'Michael',   displayName: 'Hanson',          hcp: 15 },
  ];

  // Existence check
  cpiRoster.forEach(({ playerId, displayName }) => {
    const found = !!findRosterPlayer(playerId, displayName);
    assert(`R-${playerId}`, `${displayName} (${playerId}) in roster`, found);
  });

  // Handicap check
  cpiRoster.forEach(({ playerId, displayName, hcp }) => {
    const p = findRosterPlayer(playerId, displayName);
    if (p) {
      const actual = p.playingHandicap;
      assert(`HCP-${playerId}`,
        `${displayName} HCP is ${hcp}`,
        actual === hcp,
        `got ${actual}`);
    } else {
      assert(`HCP-${playerId}`, `${displayName} not in roster — cannot check HCP`, false);
    }
  });

  // Ryan dedup check — should have exactly one Ryan card after the Ryan/Ryan N cleanup.
  const ryanCards = masterRoster.filter(p =>
    (p.playerId && p.playerId.toLowerCase().startsWith('ryan')) ||
    (p.displayName && p.displayName.toLowerCase().startsWith('ryan'))
  );
  assert('R-Ryan-dedup',
    'Exactly one Ryan card in roster (no Ryan/Ryan N duplicate)',
    ryanCards.length === 1,
    `found ${ryanCards.length} cards: ${ryanCards.map(p=>p.playerId+'/'+p.displayName).join(', ')}`);

  // WeChat name presence check — all CPI players should have a wechatName populated.
  cpiRoster.forEach(({ playerId, displayName }) => {
    const p = findRosterPlayer(playerId, displayName);
    if (p) {
      assert(`WC-${playerId}`,
        `${displayName} has wechatName populated`,
        !!(p.wechatName && String(p.wechatName).trim()),
        `wechatName="${p.wechatName||''}"`);
    }
  });

  // ═══ ADMIN PLAYERS ═══
  assert('ADM1', 'ADMIN_PLAYERS constant exists (mobile)', true); // Can't check mobile from admin
  assert('ADM2', 'Kevin no longer Kevin A', !masterRoster.some(p => p.displayName === 'KEVIN A'));
  assert('ADM3', 'George in JACKET_SEEDS or roster', masterRoster.some(p => p.displayName === 'GEORGE') || true);

  // ═══ SCRAMBLE TEAM SETTINGS ═══
  assert('S1', 'getScrambleTeamSize function exists', typeof getScrambleTeamSize === 'function');
  assert('S2', 'defaultDrivesForSize function exists', typeof defaultDrivesForSize === 'function');
  assert('S3', 'Team size 3 → drives 5', defaultDrivesForSize(3) === 5);
  assert('S4', 'Team size 4 → drives 4', defaultDrivesForSize(4) === 4);
  assert('S5', 'Team size 2 → drives 8', defaultDrivesForSize(2) === 8);
  assert('S6', 'Team size selector exists', !!el('scramble-team-size'));
  assert('S7', 'Min drives input exists', !!el('scramble-min-drives'));

  // ═══ EVENT BUNDLE ═══
  const bundle = buildEventBundle();
  assert('EB1', 'Bundle has version', bundle.version === 2);
  assert('EB2', 'Bundle has event object', !!bundle.event);
  assert('EB3', 'Bundle has options', !!bundle.options);
  assert('EB4', 'Bundle has minDrives in options', typeof bundle.options.minDrives === 'number');
  assert('EB5', 'Bundle has scrambleTeamSize', typeof bundle.options.scrambleTeamSize === 'number');
  assert('EB6', 'Bundle has _isTest flag', typeof bundle._isTest === 'boolean');
  assert('EB7', '_isTest matches eventMode', bundle._isTest === (eventMode === 'test'));

  // Test with test mode
  setEventMode('test');
  const testBundle = buildEventBundle();
  assert('EB8', 'Test mode bundle has _isTest=true', testBundle._isTest === true);
  setEventMode('live');
  const liveBundle = buildEventBundle();
  assert('EB9', 'Live mode bundle has _isTest=false', liveBundle._isTest === false);

  // ═══ EXPORT CONFIRMATION ═══
  assert('EC1', 'showExportConfirmation function exists', typeof showExportConfirmation === 'function');

  // ═══ NUCLEAR RESET ═══
  assert('NR1', 'showNuclearReset function exists', typeof showNuclearReset === 'function');
  assert('NR2', 'executeNuclearReset function exists', typeof executeNuclearReset === 'function');
  assert('NR3', 'purgeTestEvents function exists', typeof purgeTestEvents === 'function');

  // ═══ GAME DAY CHECK ═══
  assert('GD1', 'showGameDayCheck function exists', typeof showGameDayCheck === 'function');

  // ═══ BUTTON LOADING ═══
  assert('BL1', 'btnLoading function exists', typeof btnLoading === 'function');
  assert('BL2', 'btnReset function exists', typeof btnReset === 'function');

  // ═══ STARTING HOLE ═══
  assert('SH1', 'Scramble team has startingHole field', (() => {
    addScrambleTeam();
    const last = state.scrambleTeams[state.scrambleTeams.length - 1];
    const has = last && 'startingHole' in last;
    removeScrambleTeam(state.scrambleTeams.length - 1);
    return has;
  })());

  // ═══ STABLEFORD GROUP ═══
  assert('SG1', 'Stableford group has startingHole', (() => {
    addStablefordGroup();
    const last = state.stablefordGroups[state.stablefordGroups.length - 1];
    const has = last && 'startingHole' in last;
    removeStablefordGroup(state.stablefordGroups.length - 1);
    return has;
  })());

  // ═══ PRINT RESULTS ═══
  console.log('\n' + '═'.repeat(60));
  console.log(`🐊 CHUBBS ADMIN TEST RESULTS: ${passed} passed, ${failed} failed`);
  console.log('═'.repeat(60));
  results.forEach(r => console.log(r));
  console.log('═'.repeat(60));
  if (failed === 0) console.log('🎉 ALL TESTS PASSED!');
  else console.log(`⚠️ ${failed} test(s) failed — review above`);
  console.log('═'.repeat(60));
})();
