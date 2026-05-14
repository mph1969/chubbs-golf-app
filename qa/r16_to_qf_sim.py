"""
R16 → QF transition harness — May 23 2026 Yinli matchplay event.

Validates the front-9-to-back-9 flow end-to-end:

  Front 9 (R16, 8 matches in 4 foursomes M1+M2 / M3+M4 / M5+M6 / M7+M8)
    → R16 outcomes derived from gross scores via matchplay_engine
    → Cup QF feeders (R16 winners) + Plate QF feeders (R16 losers)

  Back 9 reshuffle (4 new foursomes)
    → Cup A = M1-M4 winners (Cup QF1 + Cup QF2 simultaneous)
    → Cup B = M5-M8 winners (Cup QF3 + Cup QF4)
    → Plate A = M1-M4 losers (Plate QF1 + Plate QF2)
    → Plate B = M5-M8 losers (Plate QF3 + Plate QF4)

  Scorer auto-nomination per back-9 foursome
    → brain trust priority (Luke / Terry / Jack / Ryan N / Mike W)
    → fallback to lowest playing handicap, excluding Diego
    → flag fallback foursomes for organiser

  Stableford running 18 holes for all 16 players
    → totals computed independently of matchplay status

Run:
    python qa/r16_to_qf_sim.py                  # all scenarios
    python qa/r16_to_qf_sim.py --scenario=chalk # one scenario
    python qa/r16_to_qf_sim.py --verbose        # also print per-hole detail

Locked assumptions (mirroring mobile/admin):
  - PAIRS visual order [[0,15],[7,8],[3,12],[4,11],[1,14],[6,9],[2,13],[5,10]]
  - Match closes when leader's lead exceeds holes remaining
  - Lower NET wins each hole; full hcp differential, lowest SI gets strokes first
  - ALL SQUARE thru 9 → §11 tiebreak chain (Stableford > lower hcp > arm wrestle)
  - Stableford pts: 6/5/4/3/2/1/0 for net diff <= -4/-3/-2/-1/0/+1/>=+2
"""
from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matchplay_engine import freeze_at_close, hole_winner, match_play_status

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ─── May 23 roster (locked seed order, 0-indexed) ─────────────────────────

@dataclass
class Player:
    seed: int          # 1-16 (display)
    name: str
    hcp: int


# Seeds 1-16 per the WeChat bracket confirmation. Handicaps per the team
# draft the user shared 2026-05-14 (John B placeholder until confirmed).
SEEDS = [
    Player( 1, "Matt",    13),   # 0
    Player( 2, "Nick",    24),   # 1
    Player( 3, "Jordan",  22),   # 2
    Player( 4, "George",  20),   # 3
    Player( 5, "Ryan N",  13),   # 4
    Player( 6, "Leigh",   18),   # 5
    Player( 7, "Dustin",  19),   # 6
    Player( 8, "Terry",   28),   # 7
    Player( 9, "Paul",    36),   # 8
    Player(10, "John B",  22),   # 9  (placeholder hcp)
    Player(11, "Hanson",  15),   # 10
    Player(12, "Kevin",   14),   # 11
    Player(13, "Anthony", 22),   # 12
    Player(14, "Jack S",  14),   # 13
    Player(15, "Ricardo", 27),   # 14
    Player(16, "Jamie",   21),   # 15
]
NAME_TO_HCP = {p.name: p.hcp for p in SEEDS}

PAIRS = [(0, 15), (7, 8), (3, 12), (4, 11), (1, 14), (6, 9), (2, 13), (5, 10)]
BRAIN_TRUST = ["Terry", "Jack S", "Ryan N", "Nick", "Hanson", "Matt"]   # updated 2026-05-14
BACKNINE_EXCLUDE = {"Diego"}

# Yinli stroke-index placeholder (1-18). Real SI would come from the course
# data file; the engine only cares that each hole has a distinct SI.
YINLI_SI = [7, 13, 1, 11, 5, 17, 3, 15, 9,    # front 9
            8, 14, 2, 12, 6, 18, 4, 16, 10]   # back 9
YINLI_PAR = [4] * 18  # par doesn't actually affect matchplay outcomes


# ─── Score generator + scenarios ──────────────────────────────────────────

def stableford_pts(gross: int, par: int, hcp: int, si: int) -> int:
    """6/5/4/3/2/1/0 for net diff <= -4/-3/-2/-1/0/+1/>=+2."""
    strokes = (hcp // 18) + (1 if si <= (hcp % 18) else 0)
    net = gross - strokes
    diff = net - par
    table = {-4: 6, -3: 5, -2: 4, -1: 3, 0: 2, 1: 1}
    if diff <= -4: return 6
    if diff >= 2: return 0
    return table.get(diff, 0)


def gen_gross(player: Player, rng: random.Random, skill_factor: float = 1.0) -> list[int]:
    """Generate 18 plausible gross scores for a player.

    skill_factor multiplies the expected over-par; <1 = better day, >1 = worse.
    Distribution: each hole gross ~ par + max(0, normal(mean=hcp/18, sd=0.8)).
    Output is integer; clamped to par-2..par+5 for realism.
    """
    grosses = []
    for hole in range(18):
        par = YINLI_PAR[hole]
        mean_over = (player.hcp / 18.0) * skill_factor
        noise = rng.gauss(mean_over, 0.9)
        gross = round(par + max(-1.5, noise))
        gross = max(par - 2, min(par + 5, gross))
        grosses.append(int(gross))
    return grosses


def force_match_outcome(grosses_a, grosses_b, hcp_a, hcp_b, outcome: str, holes=range(9)):
    """Mutate first-N hole grosses so the match resolves to `outcome`.

    outcome: 'a_wins_big' | 'b_wins_big' | 'all_square_thru_9'
    Mutates in-place. Adjusts for the hcp-differential stroke allocation
    per SI so net diffs are predictable hole-by-hole.
    """
    from matchplay_engine import match_play_strokes
    holes = list(holes)
    if outcome == 'a_wins_big':
        for h in holes:
            si = YINLI_SI[h]
            s = match_play_strokes(hcp_a, hcp_b, si)
            # Make A's net 3 below B's net on every hole.
            # net_a = gross_a - (s if hcp_a>hcp_b else 0)
            # net_b = gross_b - (s if hcp_b>hcp_a else 0)
            # Want net_a + 3 = net_b → solve for gross_a given gross_b.
            if hcp_a > hcp_b:
                grosses_a[h] = max(2, grosses_b[h] + s - 3)
            else:
                grosses_a[h] = max(2, grosses_b[h] - s - 3)
    elif outcome == 'b_wins_big':
        for h in holes:
            si = YINLI_SI[h]
            s = match_play_strokes(hcp_a, hcp_b, si)
            if hcp_b > hcp_a:
                grosses_b[h] = max(2, grosses_a[h] + s - 3)
            else:
                grosses_b[h] = max(2, grosses_a[h] - s - 3)
    elif outcome == 'all_square_thru_9':
        # Halve every hole: net_a == net_b. Higher-hcp player gets `strokes`
        # strokes, so set their gross = lower-hcp gross + strokes.
        for h in holes:
            si = YINLI_SI[h]
            s = match_play_strokes(hcp_a, hcp_b, si)
            if hcp_a > hcp_b:
                grosses_a[h] = grosses_b[h] + s
            else:
                grosses_b[h] = grosses_a[h] + s


# ─── R16 → QF derivation ──────────────────────────────────────────────────

def run_r16(grosses_by_name) -> list[dict]:
    """For each of the 8 R16 matches, derive the match-play outcome from
    front-9 scores. Returns a list of dicts: matchIdx, p1, p2, hcps, winners,
    status (closed/dormie/all_square), label.
    """
    results = []
    for i, (a, b) in enumerate(PAIRS):
        pa, pb = SEEDS[a], SEEDS[b]
        winners = []
        for h in range(9):
            si = YINLI_SI[h]
            w = hole_winner(grosses_by_name[pa.name][h], pa.hcp,
                            grosses_by_name[pb.name][h], pb.hcp, si)
            winners.append(w)
        status = freeze_at_close(winners, total=9)
        if status.get('closed'):
            winner_name = pa.name if status['leader'] == 'a' else pb.name
            loser_name  = pb.name if status['leader'] == 'a' else pa.name
        elif status.get('allSquare'):
            # §11 tiebreak — Stableford breaker on the front 9
            sa = sum(stableford_pts(grosses_by_name[pa.name][h], YINLI_PAR[h], pa.hcp, YINLI_SI[h]) for h in range(9))
            sb = sum(stableford_pts(grosses_by_name[pb.name][h], YINLI_PAR[h], pb.hcp, YINLI_SI[h]) for h in range(9))
            if sa != sb:
                winner_name = pa.name if sa > sb else pb.name
                loser_name  = pb.name if sa > sb else pa.name
                status['label'] += f' → Stableford {sa}-{sb}'
            else:
                # Lower hcp wins next; arm-wrestle if hcps equal (we model lower hcp here)
                winner_name = pa.name if pa.hcp < pb.hcp else pb.name
                loser_name  = pb.name if pa.hcp < pb.hcp else pa.name
                status['label'] += f' → lower hcp ({winner_name})'
        else:
            # Match ran 9 holes but not closed (1 UP or similar) — leader wins
            winner_name = pa.name if status['leader'] == 'a' else pb.name
            loser_name  = pb.name if status['leader'] == 'a' else pa.name
        results.append({
            'matchIdx': i, 'label': f'M{i+1}',
            'p1': pa.name, 'p2': pb.name,
            'hcps': (pa.hcp, pb.hcp),
            'winner': winner_name, 'loser': loser_name,
            'status': status,
        })
    return results


def build_back9_foursomes(r16: list[dict]) -> list[dict]:
    """4 reshuffled foursomes per the §11 back-9 layout."""
    winners = [r['winner'] for r in r16]
    losers  = [r['loser']  for r in r16]
    return [
        {'id': 'cup-a', 'name': 'Cup A', 'icon': '🏆',
         'players': winners[0:4],
         'matches': [{'type': 'cup_qf', 'index': 0, 'p1': winners[0], 'p2': winners[1]},
                     {'type': 'cup_qf', 'index': 1, 'p1': winners[2], 'p2': winners[3]}]},
        {'id': 'cup-b', 'name': 'Cup B', 'icon': '🏆',
         'players': winners[4:8],
         'matches': [{'type': 'cup_qf', 'index': 2, 'p1': winners[4], 'p2': winners[5]},
                     {'type': 'cup_qf', 'index': 3, 'p1': winners[6], 'p2': winners[7]}]},
        {'id': 'plate-a', 'name': 'Plate A', 'icon': '🍽️',
         'players': losers[0:4],
         'matches': [{'type': 'plate_qf', 'index': 0, 'p1': losers[0], 'p2': losers[1]},
                     {'type': 'plate_qf', 'index': 1, 'p1': losers[2], 'p2': losers[3]}]},
        {'id': 'plate-b', 'name': 'Plate B', 'icon': '🍽️',
         'players': losers[4:8],
         'matches': [{'type': 'plate_qf', 'index': 2, 'p1': losers[4], 'p2': losers[5]},
                     {'type': 'plate_qf', 'index': 3, 'p1': losers[6], 'p2': losers[7]}]},
    ]


def pick_back9_scorer(players: list[str]) -> dict:
    """Mirror _pickBackNineScorerId: brain trust priority, Diego excluded
    from fallback. Returns {name, fallback, reason}."""
    eligible = [n for n in players if n not in BACKNINE_EXCLUDE]
    for bt in BRAIN_TRUST:
        if bt in eligible:
            return {'name': bt, 'fallback': False, 'reason': 'brain-trust'}
    if not eligible:
        return {'name': None, 'fallback': True, 'reason': 'all-excluded'}
    lowest = min(eligible, key=lambda n: NAME_TO_HCP.get(n, 99))
    return {'name': lowest, 'fallback': True, 'reason': 'lowest-hcp'}


# ─── QF back-9 outcomes ───────────────────────────────────────────────────

def run_qf(qf_match: dict, grosses_by_name) -> dict:
    """Compute 9-hole back-9 matchplay status for one QF match."""
    p1, p2 = qf_match['p1'], qf_match['p2']
    h1, h2 = NAME_TO_HCP[p1], NAME_TO_HCP[p2]
    winners = []
    for h in range(9, 18):
        si = YINLI_SI[h]
        w = hole_winner(grosses_by_name[p1][h], h1, grosses_by_name[p2][h], h2, si)
        winners.append(w)
    status = freeze_at_close(winners, total=9)
    if status.get('closed') or status.get('leader'):
        winner_name = p1 if status.get('leader') == 'a' else p2
    elif status.get('allSquare'):
        winner_name = None  # tiebreak needed
    else:
        winner_name = None
    return {**qf_match, 'status': status, 'winner': winner_name}


def stableford_18(grosses) -> int:
    return sum(stableford_pts(grosses[h], YINLI_PAR[h], 0, YINLI_SI[h]) for h in range(18))
    # NOTE: actual app applies player hcp; passing 0 here for net=gross sanity.
    # The harness's per-player Stableford uses player.hcp via stableford_player().


def stableford_player(name: str, grosses: list[int]) -> int:
    hcp = NAME_TO_HCP[name]
    return sum(stableford_pts(grosses[h], YINLI_PAR[h], hcp, YINLI_SI[h]) for h in range(18))


# ─── Save-to-bracket simulation (Tier 2c) ─────────────────────────────────
# Mirrors pushMatchToBracket(matchIdx, winner, label, matchType) in mobile.
# Writes to a Python dict shaped like the JS season.playoffs structure.

def init_playoffs_state():
    """Empty playoffs dict mirroring season.playoffs schema in mobile."""
    return {
        'seeds': [p.name for p in SEEDS],
        'r16':       [{'winner': None, 'result': None} for _ in range(8)],
        'cup_qf':    [{'winner': None, 'result': None} for _ in range(4)],
        'plate_qf':  [{'winner': None, 'result': None} for _ in range(4)],
    }


def save_match_to_bracket(playoffs, match_type, match_idx, winner_name, result_label):
    """Mirror pushMatchToBracket — write to playoffs[type][idx]."""
    if match_type not in playoffs:
        raise ValueError(f'Unknown match type: {match_type}')
    if match_idx < 0 or match_idx >= len(playoffs[match_type]):
        raise IndexError(f'Bad {match_type} idx {match_idx}')
    playoffs[match_type][match_idx] = {'winner': winner_name, 'result': result_label}


# ─── Scenario runners ─────────────────────────────────────────────────────

def make_scenario(name: str, rng: random.Random):
    """Return {grosses_by_name, forced_outcomes} for a scenario."""
    grosses = {p.name: gen_gross(p, rng) for p in SEEDS}

    if name == 'chalk':
        # Higher seed wins each R16
        for i, (a, b) in enumerate(PAIRS):
            higher = SEEDS[a]   # higher seed = lower number = first in pair
            lower  = SEEDS[b]
            force_match_outcome(grosses[higher.name], grosses[lower.name],
                                higher.hcp, lower.hcp, 'a_wins_big', range(9))
    elif name == 'all_square_m1':
        # Force M1 (Matt v Jamie) to ALL SQUARE thru 9; rest chalk
        for i, (a, b) in enumerate(PAIRS):
            higher, lower = SEEDS[a], SEEDS[b]
            outcome = 'all_square_thru_9' if i == 0 else 'a_wins_big'
            force_match_outcome(grosses[higher.name], grosses[lower.name],
                                higher.hcp, lower.hcp, outcome, range(9))
    elif name == 'mixed_upsets':
        # Upsets in M2, M5, M7 (lower seed wins). Rest chalk.
        upsets = {1, 4, 6}
        for i, (a, b) in enumerate(PAIRS):
            higher, lower = SEEDS[a], SEEDS[b]
            outcome = 'b_wins_big' if i in upsets else 'a_wins_big'
            force_match_outcome(grosses[higher.name], grosses[lower.name],
                                higher.hcp, lower.hcp, outcome, range(9))
    return grosses


def run_scenario(name: str, seed: int, verbose: bool) -> int:
    """Returns number of failed assertions."""
    rng = random.Random(seed)
    grosses = make_scenario(name, rng)
    failed = 0

    print(f"\n═══ Scenario: {name} (seed={seed}) ═══")

    r16 = run_r16(grosses)
    for r in r16:
        marker = "TBK" if 'Stableford' in r['status']['label'] or 'lower hcp' in r['status']['label'] else "OK "
        print(f"  [{marker}] {r['label']}: {r['p1']} v {r['p2']} → {r['winner']} ({r['status']['label']})")
    if any(r['winner'] is None for r in r16):
        print("  FAIL: at least one R16 match did not resolve to a winner")
        failed += 1

    foursomes = build_back9_foursomes(r16)
    expected_size = 4
    for f in foursomes:
        actual_players = [p for p in f['players'] if p]
        if len(actual_players) != expected_size:
            print(f"  FAIL: {f['name']} has {len(actual_players)} players (expected {expected_size})")
            failed += 1
        scorer = pick_back9_scorer(f['players'])
        flag = "[OK]  " if not scorer['fallback'] else "[WARN]"
        print(f"  {flag} {f['icon']} {f['name']}: [{', '.join(f['players'])}] · scorer={scorer['name']} ({scorer['reason']})")
        # Validation: scorer must be in foursome
        if scorer['name'] and scorer['name'] not in f['players']:
            print(f"    FAIL: scorer {scorer['name']} not in foursome")
            failed += 1
        # Validation: scorer not in exclude list
        if scorer['name'] in BACKNINE_EXCLUDE:
            print(f"    FAIL: scorer {scorer['name']} is in BACKNINE_EXCLUDE")
            failed += 1
        # Validation: 2 matches per foursome
        if len(f['matches']) != 2:
            print(f"    FAIL: {f['name']} has {len(f['matches'])} matches (expected 2)")
            failed += 1

    # All 16 players accounted for across the 4 back-9 foursomes
    accounted = set()
    for f in foursomes: accounted.update(p for p in f['players'] if p)
    expected = {p.name for p in SEEDS}
    if accounted != expected:
        missing = expected - accounted
        extra   = accounted - expected
        print(f"  FAIL: roster mismatch — missing={missing} extra={extra}")
        failed += 1

    # Run QF matches on back 9 + simulate save-to-bracket (Tier 2c-4)
    print("  ─── Back 9 QF outcomes + save-to-bracket ───")
    playoffs = init_playoffs_state()
    # Pre-fill r16 winners (front-9 saves already happened on R16 close)
    for i, r in enumerate(r16):
        save_match_to_bracket(playoffs, 'r16', i, r['winner'], r['status'].get('label', ''))
    qf_results = []
    for f in foursomes:
        for m in f['matches']:
            qf = run_qf(m, grosses)
            label = f"Cup QF{m['index']+1}" if m['type'] == 'cup_qf' else f"Plate QF{m['index']+1}"
            print(f"    {label}: {m['p1']} v {m['p2']} → {qf['winner'] or 'unresolved'} ({qf['status']['label']})")
            qf_results.append(qf)
            if qf['winner']:
                save_match_to_bracket(playoffs, m['type'], m['index'], qf['winner'], qf['status'].get('label', ''))

    # Bracket-state assertions (Tier 2c-4: saves land in the right buckets)
    r16_saved   = sum(1 for r in playoffs['r16']      if r['winner'])
    cup_saved   = sum(1 for r in playoffs['cup_qf']   if r['winner'])
    plate_saved = sum(1 for r in playoffs['plate_qf'] if r['winner'])
    print(f"  ─── Bracket state: r16 {r16_saved}/8 · cup_qf {cup_saved}/4 · plate_qf {plate_saved}/4 ───")
    if r16_saved != 8:
        print(f"    FAIL: expected 8 r16 winners, got {r16_saved}")
        failed += 1
    unresolved_qf = sum(1 for q in qf_results if q['winner'] is None)
    expected_resolved = 8 - unresolved_qf
    actual_resolved = cup_saved + plate_saved
    if actual_resolved != expected_resolved:
        print(f"    FAIL: bracket save count mismatch — expected {expected_resolved}, got {actual_resolved}")
        failed += 1

    # Cascade invariants: every cup_qf winner came from R16 winners; every
    # plate_qf winner came from R16 losers. Detects routing bugs in the
    # back-9 reshuffle.
    r16_winners_set = {r['winner'] for r in r16}
    r16_losers_set  = {r['loser']  for r in r16}
    for i, cq in enumerate(playoffs['cup_qf']):
        if cq['winner'] and cq['winner'] not in r16_winners_set:
            print(f"    FAIL: Cup QF{i+1} winner {cq['winner']} isn't an R16 winner")
            failed += 1
    for i, pq in enumerate(playoffs['plate_qf']):
        if pq['winner'] and pq['winner'] not in r16_losers_set:
            print(f"    FAIL: Plate QF{i+1} winner {pq['winner']} isn't an R16 loser")
            failed += 1

    # Stableford 18 for all 16
    print("  ─── Stableford totals (18 holes) ───")
    stable_rows = [(p.name, stableford_player(p.name, grosses[p.name])) for p in SEEDS]
    stable_rows.sort(key=lambda r: -r[1])
    for name, pts in stable_rows[:5]:
        print(f"    {name}: {pts}")
    print(f"    ... (top 5 of 16)")

    # Sanity: Stableford runs even for R16 losers (i.e. they still have pts on back 9)
    for r in r16:
        loser = r['loser']
        front = sum(stableford_pts(grosses[loser][h], YINLI_PAR[h], NAME_TO_HCP[loser], YINLI_SI[h]) for h in range(9))
        back  = sum(stableford_pts(grosses[loser][h], YINLI_PAR[h], NAME_TO_HCP[loser], YINLI_SI[h]) for h in range(9, 18))
        if back == 0 and front == 0:
            # Possible if player blew up — flag but don't fail
            print(f"    NOTE: {loser} has 0 Stableford points across both 9s")

    print(f"  Result: {'PASS' if failed == 0 else f'FAIL ({failed} issue(s))'}")
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario', choices=['chalk', 'all_square_m1', 'mixed_upsets', 'all'],
                    default='all')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    scenarios = ['chalk', 'all_square_m1', 'mixed_upsets'] if args.scenario == 'all' else [args.scenario]
    total_failed = 0
    for s in scenarios:
        total_failed += run_scenario(s, args.seed, args.verbose)

    print(f"\n═══ Summary: {len(scenarios) - (1 if total_failed else 0)}/{len(scenarios)} scenarios pass ({total_failed} total issues) ═══")
    sys.exit(1 if total_failed else 0)


if __name__ == '__main__':
    main()
