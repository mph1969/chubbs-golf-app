"""
Match-play engine — Python port of the JS helpers in
ChubbsMobileApp_v5/index.html (matchPlayStrokes, matchPlayHoleWinner,
matchPlayStatus). Used to validate the engine against handcrafted scenarios
and (later) Season 3 historical playoff data.

Run from repo root:
    python qa/matchplay_engine.py            # smoke tests
    python qa/matchplay_engine.py --verbose  # also print intermediate state

When the JS helpers change, mirror the change here. Both must agree
hole-for-hole.

Locked assumptions (Michael 2026-05-09):
  - Lower NET wins each hole
  - Strokes = full hcp differential, allocated to hardest holes (lowest SI first)
  - Match closes when leader's lead exceeds holes remaining
  - Tied at H9 → tiebreak by Stableford → lower hcp → arm wrestle (handbook §11)
"""
from __future__ import annotations

import sys


def match_play_strokes(hcp_a, hcp_b, si):
    """Strokes the higher-handicap player gets on this hole."""
    a = max(0, int(hcp_a or 0))
    b = max(0, int(hcp_b or 0))
    diff = abs(a - b)
    if diff == 0:
        return 0
    base = diff // 18
    rem = diff % 18
    return base + (1 if si <= rem else 0)


def hole_winner(gross_a, hcp_a, gross_b, hcp_b, si):
    """Who won this hole? 'a' | 'b' | 'halved' | None (incomplete)."""
    if gross_a is None or gross_b is None:
        return None
    strokes = match_play_strokes(hcp_a, hcp_b, si)
    a_higher = hcp_a > hcp_b
    net_a = gross_a - (strokes if a_higher else 0)
    net_b = gross_b - (0 if a_higher else strokes)
    if net_a < net_b: return 'a'
    if net_b < net_a: return 'b'
    return 'halved'


def freeze_at_close(winners, total=9):
    """Iterative status — once a match closes, freeze the label. Mirrors the
    freeze logic in getActiveMatchPlayMatches() in mobile (index.html). Without
    this, continued stableford scoring after a closed match drifts the
    matchplay label (e.g., "3&2" close → "1 UP" after continued play).
    """
    so_far = []
    for w in winners:
        so_far.append(w)
        if w is None: continue
        s = match_play_status(so_far, total)
        if s.get("closed"): return s
    return match_play_status(winners, total)


def match_play_status(holes, total=9):
    """Aggregate match status from a list of per-hole winners.

    holes: list of 'a' | 'b' | 'halved' | None
    total: total holes in the match (9 for R16/QF/SF, 9 or 18 for finals).

    Returns dict with: played, lead, leader, closed?, dormie?, allSquare?, label.
    """
    played = a_wins = b_wins = 0
    for w in holes:
        if w is None:
            continue
        played += 1
        if w == 'a': a_wins += 1
        elif w == 'b': b_wins += 1
    remaining = max(0, total - played)
    a_up = a_wins - b_wins
    lead = abs(a_up)
    leader = 'a' if a_up > 0 else ('b' if a_up < 0 else None)

    if lead > remaining and played > 0:
        score = f"{lead} UP" if remaining == 0 else f"{lead}&{remaining}"
        return {"played": played, "remaining": remaining, "lead": lead, "leader": leader,
                "closed": True, "dormie": False, "allSquare": False,
                "closedScore": score, "label": score}
    if lead == remaining and lead > 0 and remaining > 0:
        return {"played": played, "remaining": remaining, "lead": lead, "leader": leader,
                "closed": False, "dormie": True, "allSquare": False,
                "label": f"Dormie {lead} UP"}
    if lead == 0:
        return {"played": played, "remaining": remaining, "lead": 0, "leader": None,
                "closed": False, "dormie": False, "allSquare": True,
                "label": f"ALL SQUARE thru {played}" if played else "ALL SQUARE"}
    return {"played": played, "remaining": remaining, "lead": lead, "leader": leader,
            "closed": False, "dormie": False, "allSquare": False,
            "label": f"{lead} UP thru {played}"}


# ─── Smoke tests ────────────────────────────────────────────────────────────

def run_tests():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cases = [
        # (description, assertion-lambda)
        ("equal hcps + same gross → halved",
         lambda: match_play_strokes(15, 15, 1) == 0
              and hole_winner(5, 15, 5, 15, 1) == 'halved'),

        ("18-diff Andy(30)/Matt D(12) → 1 stroke per hole",
         lambda: match_play_strokes(30, 12, 1) == 1
              and match_play_strokes(30, 12, 18) == 1
              and hole_winner(6, 30, 5, 12, 1) == 'halved'),

        ("27-diff Terry(28)/John(1) → 2 strokes on SI 1-9, 1 on SI 10-18",
         lambda: match_play_strokes(28, 1, 1) == 2
              and match_play_strokes(28, 1, 9) == 2
              and match_play_strokes(28, 1, 10) == 1
              and hole_winner(7, 28, 5, 1, 1) == 'halved'),

        ("in-progress: 3 UP thru 5",
         lambda: match_play_status(['a','a','a','halved','halved'])['label'] == '3 UP thru 5'),

        ("dormie: 3 up with 3 to play",
         lambda: match_play_status(['a','a','a','halved','halved','halved'])['dormie'] is True),

        ("closed early: 4&2",
         lambda: match_play_status(['a','a','a','a','a','b','halved'])['label'] == '4&2'),

        ("went to 18, won 1 UP",
         lambda: match_play_status(['a','b','a','b','a','halved','b','a','halved'])['label'] == '1 UP'),

        ("ALL SQUARE thru 9 → handbook §11 tiebreak triggers",
         lambda: 'ALL SQUARE thru 9' in match_play_status(['a','b','a','b','a','b','halved','halved','halved'])['label']),

        # Freeze tests — match closes early, subsequent scoring shouldn't drift the label
        ("freeze: 4&2 close at H7, continued scoring stays 4&2",
         lambda: freeze_at_close(['a','a','a','a','b','halved','a','b','b'])['label'] == '4&2'),

        ("freeze: 5&4 close at H5, continued play stays 5&4",
         lambda: freeze_at_close(['a','a','a','a','a','b','b','b','b'])['label'] == '5&4'),

        ("freeze: never closes (1 UP at 18) — final label preserved",
         lambda: freeze_at_close(['a','b','a','b','a','b','a','halved','halved'])['label'] == '1 UP'),
    ]

    failed = 0
    for desc, assertion in cases:
        try:
            ok = assertion()
        except Exception as e:
            ok = False
            desc = f"{desc} (exception: {e})"
        marker = "[OK]  " if ok else "[FAIL]"
        print(f"{marker} {desc}")
        if not ok: failed += 1
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run_tests()
