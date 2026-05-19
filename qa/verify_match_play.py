"""
Verify match-play hole-by-hole correctness against the saved bracket.

Fetches the live Firebase state for an event, then re-computes every
front-9 R16 hole from first principles using the same handicap stroke
allocation + lower-net-wins rule the mobile app uses. Compares the
computed winner against the saved bracket. Flags any mismatches.

Run:
    python qa/verify_match_play.py [EVENT_ID]
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

FB = 'https://chubbs-golf-default-rtdb.asia-southeast1.firebasedatabase.app'
EID = sys.argv[1] if len(sys.argv) > 1 else '2026-TEST5-Brai'

# Yinli course data (mirror of COURSE_LIBRARY['yinli'].holes)
YINLI = [
    {'par': 4, 'si': 11}, {'par': 4, 'si': 8},  {'par': 3, 'si': 16}, {'par': 5, 'si': 4},
    {'par': 4, 'si': 18}, {'par': 4, 'si': 6},  {'par': 4, 'si': 13}, {'par': 3, 'si': 10},
    {'par': 5, 'si': 3},
    {'par': 4, 'si': 15}, {'par': 4, 'si': 9},  {'par': 3, 'si': 17}, {'par': 5, 'si': 5},
    {'par': 4, 'si': 12}, {'par': 3, 'si': 14}, {'par': 4, 'si': 2},  {'par': 4, 'si': 1},
    {'par': 5, 'si': 7},
]

PAIRS = [(0, 15), (7, 8), (3, 12), (4, 11), (1, 14), (6, 9), (2, 13), (5, 10)]


def fb(path):
    url = f'{FB}/{path}.json'
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


# ── Engine logic (mirror of mobile match-play helpers) ─────────────────────

def match_play_strokes(hcp_a, hcp_b, si):
    a, b = max(0, int(hcp_a or 0)), max(0, int(hcp_b or 0))
    diff = abs(a - b)
    if diff == 0:
        return 0
    base, rem = diff // 18, diff % 18
    return base + (1 if si <= rem else 0)


def hole_winner(gross_a, hcp_a, gross_b, hcp_b, si):
    if gross_a is None or gross_b is None:
        return None
    strokes = match_play_strokes(hcp_a, hcp_b, si)
    a_higher = int(hcp_a or 0) > int(hcp_b or 0)
    net_a = gross_a - (strokes if a_higher else 0)
    net_b = gross_b - (0 if a_higher else strokes)
    if net_a < net_b:
        return 'a'
    if net_b < net_a:
        return 'b'
    return 'halved'


def stableford_pts(gross, par, hcp, si):
    if gross is None:
        return None
    safe = max(0, int(hcp or 0))
    shots = (safe // 18) + (1 if si <= (safe % 18) else 0)
    diff = (gross - shots) - par
    return {-4: 6, -3: 5, -2: 4, -1: 3, 0: 2, 1: 1}.get(max(diff, -4) if diff < 1 else diff, 0)


def status(winners, total=9):
    a_wins = sum(1 for w in winners if w == 'a')
    b_wins = sum(1 for w in winners if w == 'b')
    played = sum(1 for w in winners if w is not None)
    remaining = max(0, total - played)
    lead = abs(a_wins - b_wins)
    leader = 'a' if a_wins > b_wins else ('b' if b_wins > a_wins else None)
    if lead > remaining and played > 0:
        return {'closed': True, 'leader': leader,
                'label': f'{lead} UP' if remaining == 0 else f'{lead}&{remaining}',
                'played': played}
    if lead == 0:
        return {'closed': False, 'leader': None,
                'label': f'ALL SQUARE thru {played}',
                'allSquare': True, 'played': played}
    return {'closed': False, 'leader': leader, 'label': f'{lead} UP', 'played': played}


def norm(s):
    return re.sub(r"[.,'\"`]", '', str(s).strip().upper()) if s else ''


def main():
    print(f'Event: {EID}\n{"=" * 60}\n')

    bundle = fb(f'events/{EID}/bundle')
    groups = fb(f'events/{EID}/groups') or {}
    bracket = fb(f'events/{EID}/bracket') or {}
    players = bundle.get('players', [])
    pid_to = {p['playerId']: p for p in players}
    seeds = (bundle.get('playoffs') or {}).get('seeds', [])
    day2_groups = bundle.get('day2Groups', [])

    # Map seed name -> playerId via displayName + aliases
    name_to_pid = {}
    for p in players:
        for k in ('displayName', 'fullName'):
            if p.get(k):
                name_to_pid[norm(p[k])] = p['playerId']
        for alias in (p.get('aliases') or []):
            name_to_pid[norm(alias)] = p['playerId']

    def seed_pid(name):
        return name_to_pid.get(norm(name))

    def group_with(pid):
        for g in day2_groups:
            if pid in (g.get('playerIds') or []):
                return g
        return None

    def grosses_for(pid):
        grp = group_with(pid)
        if not grp:
            return None
        gid = grp['groupId']
        gdata = groups.get(gid)
        if not gdata:
            return None
        rps = gdata.get('players') or []
        ri = next((i for i, rp in enumerate(rps) if rp and rp.get('playerId') == pid), -1)
        if ri < 0:
            return None
        holes = gdata.get('holes') or []
        out = []
        for h in holes:
            if h and isinstance(h.get('gross'), list) and ri < len(h['gross']):
                out.append(h['gross'][ri])
            else:
                out.append(None)
        return out

    # Firebase returns dense arrays as lists, sparse as dict-with-string-keys.
    # Normalise to a dict keyed by stringified index.
    raw_r16 = bracket.get('r16')
    if isinstance(raw_r16, list):
        saved_r16 = {str(i): v for i, v in enumerate(raw_r16) if v}
    elif isinstance(raw_r16, dict):
        saved_r16 = raw_r16
    else:
        saved_r16 = {}
    issues = []

    for mi, (sa, sb) in enumerate(PAIRS):
        name_a = seeds[sa] if sa < len(seeds) else None
        name_b = seeds[sb] if sb < len(seeds) else None
        if not name_a or not name_b:
            continue
        pid_a = seed_pid(name_a)
        pid_b = seed_pid(name_b)
        p_a = pid_to.get(pid_a, {})
        p_b = pid_to.get(pid_b, {})
        hcp_a = p_a.get('playingHandicap', 0) or 0
        hcp_b = p_b.get('playingHandicap', 0) or 0
        disp_a = p_a.get('displayName', name_a or '?')
        disp_b = p_b.get('displayName', name_b or '?')

        grosses_a = grosses_for(pid_a) if pid_a else None
        grosses_b = grosses_for(pid_b) if pid_b else None

        print(f'M{mi + 1}  #{sa + 1} {disp_a} (hcp {hcp_a}) vs #{sb + 1} {disp_b} (hcp {hcp_b})')
        diff = abs(hcp_a - hcp_b)
        higher = disp_a if hcp_a > hcp_b else (disp_b if hcp_b > hcp_a else '(none)')
        if diff > 0:
            stroke_sis = []
            for si in range(1, 19):
                base = diff // 18
                rem = diff % 18
                cnt = base + (1 if si <= rem else 0)
                if cnt > 0:
                    stroke_sis.append(f'SI{si}({cnt})')
            print(f'      diff = {diff} strokes to {higher} on: {", ".join(stroke_sis)}')
        else:
            print(f'      diff = 0 strokes (equal hcps)')

        winners = []
        sb_a = sb_b = 0
        for hi in range(9):
            ch = YINLI[hi]
            ga = grosses_a[hi] if grosses_a and hi < len(grosses_a) else None
            gb = grosses_b[hi] if grosses_b and hi < len(grosses_b) else None
            strokes = match_play_strokes(hcp_a, hcp_b, ch['si'])
            a_higher = hcp_a > hcp_b
            w = hole_winner(ga, hcp_a, gb, hcp_b, ch['si'])
            winners.append(w)
            pa = stableford_pts(ga, ch['par'], hcp_a, ch['si'])
            pb = stableford_pts(gb, ch['par'], hcp_b, ch['si'])
            if pa is not None:
                sb_a += pa
            if pb is not None:
                sb_b += pb
            if ga is None or gb is None:
                print(f'   H{hi + 1} (par {ch["par"]}, SI {ch["si"]:>2}): (no scores)')
                continue
            net_a = ga - (strokes if a_higher else 0)
            net_b = gb - (0 if a_higher else strokes)
            stroke_note = ''
            if strokes > 0:
                recipient = disp_a if a_higher else disp_b
                stroke_note = f'  [+{strokes} to {recipient}]'
            w_str = {'a': disp_a, 'b': disp_b, 'halved': 'HALVED'}.get(w, '?')
            print(f'   H{hi + 1} (par {ch["par"]}, SI {ch["si"]:>2}): '
                  f'{disp_a} {ga} (net {net_a})  |{disp_b} {gb} (net {net_b}){stroke_note}  ->  {w_str}')

        s = status(winners, 9)
        print(f'   COMPUTED status: {s["label"]}')
        print(f'   Stableford tiebreak: {disp_a}={sb_a} pts, {disp_b}={sb_b} pts')

        saved = saved_r16.get(str(mi))
        if saved and saved.get('winner'):
            saved_pid = seed_pid(saved['winner'])
            saved_side = 'a' if saved_pid == pid_a else ('b' if saved_pid == pid_b else '?')
            if s.get('closed'):
                computed_side = s.get('leader')
            elif s.get('played') == 9 and s.get('allSquare'):
                # All-square thru 9 -> apply tiebreak hierarchy
                if sb_a > sb_b:
                    computed_side = 'a'
                elif sb_b > sb_a:
                    computed_side = 'b'
                elif hcp_a < hcp_b:
                    computed_side = 'a'
                elif hcp_b < hcp_a:
                    computed_side = 'b'
                else:
                    computed_side = 'tied'
            else:
                computed_side = None
            if computed_side is None:
                flag = '? (match not closed yet)'
            elif computed_side == saved_side:
                flag = 'OK'
            else:
                flag = f'MISMATCH (computed says {disp_a if computed_side == "a" else disp_b})'
                issues.append(f'M{mi + 1}: saved {saved["winner"]}, expected {disp_a if computed_side == "a" else disp_b}')
            print(f'   SAVED bracket: {saved["winner"]} ({saved.get("result", "?")})  -> {flag}')
        else:
            print(f'   SAVED bracket: (not saved)')

        print()

    print('=' * 60)
    if issues:
        print(f'\nFOUND {len(issues)} mismatch(es):')
        for iss in issues:
            print(f'  - {iss}')
    else:
        print('\nAll saved bracket results match the computed match-play outcomes.')
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
