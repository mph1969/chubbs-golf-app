"""
Playoff Bracket Simulation — May/June 2026
==========================================
Loads season-4.json, applies the Final Two signup register (withdrawals),
seeds the top 16 using the app's locked tiebreak, and walks the entire
4-tier cascade (Cup / Plate / Shield / Spoon) under chalk + upset scenarios.

Run:
    python qa/playoff_sim.py                # chalk
    python qa/playoff_sim.py --upsets=1,3   # higher seed loses in M1 and M3
    python qa/playoff_sim.py --terry-order  # use Terry's hand-seeding (Dustin@7)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from season4_qa import aggregate_season, SEASON_JSON

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Per Michael's note 2026-05-09:
WITHDRAWALS = {
    "Mike W":   "won't play",
    "Diego":    "sitting out — missing June",
    "Anthony":  "Fireball Cup — only playing May",
}

# Standard 16-bracket pairings (seed indices, 0-based) — copied from
# index.html:2619 r16Pairs. Keep in lock-step with the app.
R16_PAIRS = [(0,15),(7,8),(4,11),(3,12),(2,13),(5,10),(6,9),(1,14)]

# Cascade graph — copied from index.html:2624 ROUND_FROM
# Each entry: round → {from, role} where players come from the prior round's
# winners (Cup/Plate paths) or losers (Shield/Spoon consolations).
ROUND_FROM = {
    "cup_qf":       ("r16",      "winner"),
    "cup_sf":       ("cup_qf",   "winner"),
    "cup_final":    ("cup_sf",   "winner"),
    "plate_qf":     ("r16",      "loser"),
    "plate_sf":     ("plate_qf", "winner"),
    "plate_final":  ("plate_sf", "winner"),
    "shield_sf":    ("cup_qf",   "loser"),
    "shield_final": ("shield_sf","winner"),
    "spoon_sf":     ("plate_qf", "loser"),
    "spoon_final":  ("spoon_sf", "winner"),
}


def seed_field(season, terry_order=False, best7=False):
    """Return the 16 seeds, with withdrawals removed."""
    rows = aggregate_season(season)
    qualified = [r for r in rows if r["qualified"] and r["name"] not in WITHDRAWALS]
    if best7:
        # Handbook §10.2 reading: best-7 desc → round-avg desc → seedPoints desc → stableford desc
        qualified.sort(key=lambda r: (-r["best7"], -(r["best7"] / max(r["played"], 1)), -r["seedPoints"], -r["stableford"]))
    elif terry_order:
        # Legacy flag — kept for back-compat. Same rule as default now.
        qualified.sort(key=lambda r: (
            -r["seedPoints"],
            -(r["best7"] / max(r["played"], 1)),
            -r["stableford"],
        ))
    else:
        # Active rule per Terry 2026-05-10: seedPoints desc → round-avg desc → stableford desc.
        # Replaces the played-desc rule from 2026-04-29 (Terry didn't remember locking it).
        qualified.sort(key=lambda r: (
            -r["seedPoints"],
            -(r["best7"] / max(r["played"], 1)),
            -r["stableford"],
        ))
    return qualified[:16]


def build_r16_matches(seeds, winner_chooser):
    """seeds: list of 16 player rows. winner_chooser(match_idx, [(seed_idx, name)]): name
    Returns list of 8 dicts with players + winner + loser."""
    matches = []
    for i, (a, b) in enumerate(R16_PAIRS):
        p1 = (a, seeds[a]["name"])
        p2 = (b, seeds[b]["name"])
        winner = winner_chooser(i, [p1, p2])
        loser = p1 if winner == p2 else p2
        matches.append({"idx": i, "p1": p1, "p2": p2, "winner": winner, "loser": loser})
    return matches


def resolve_round(round_name, prior, winner_chooser):
    """Generic resolver — takes the prior round's matches and produces this round's.
    `role` from ROUND_FROM determines whether to pull winners or losers."""
    src_round, role = ROUND_FROM[round_name]
    src = prior[src_round]
    matches = []
    half = len(src) // 2
    for i in range(half):
        a = src[i*2][role]
        b = src[i*2+1][role]
        if a is None or b is None:
            matches.append({"idx": i, "p1": a, "p2": b, "winner": None, "loser": None})
            continue
        winner = winner_chooser(f"{round_name}-{i}", [a, b])
        loser = a if winner == b else b
        matches.append({"idx": i, "p1": a, "p2": b, "winner": winner, "loser": loser})
    return matches


def chalk_chooser(seeds_by_name):
    """Higher seed (lower seed number) always wins."""
    def choose(_idx, players):
        s1 = seeds_by_name[players[0][1]] if isinstance(players[0], tuple) else seeds_by_name[players[0][1]]
        s2 = seeds_by_name[players[1][1]] if isinstance(players[1], tuple) else seeds_by_name[players[1][1]]
        return players[0] if s1 < s2 else players[1]
    return choose


def upset_chooser(seeds_by_name, upset_match_indices):
    """Higher seed wins UNLESS this match is in upset_match_indices, then lower wins."""
    def choose(idx, players):
        s1 = seeds_by_name[players[0][1]] if isinstance(players[0], tuple) else seeds_by_name[players[0][1]]
        s2 = seeds_by_name[players[1][1]] if isinstance(players[1], tuple) else seeds_by_name[players[1][1]]
        higher = players[0] if s1 < s2 else players[1]
        lower  = players[1] if s1 < s2 else players[0]
        # idx for R16 is int; for later rounds it's a string like "cup_qf-2"
        if isinstance(idx, int) and idx in upset_match_indices:
            return lower
        return higher
    return choose


def run_simulation(seeds, chooser):
    rounds = {}
    seeds_by_name = {s["name"]: s["_seed"] for s in seeds}

    # R16
    rounds["r16"] = build_r16_matches(seeds, chooser)
    # Cup path
    rounds["cup_qf"]    = resolve_round("cup_qf",    rounds, chooser)
    rounds["cup_sf"]    = resolve_round("cup_sf",    rounds, chooser)
    rounds["cup_final"] = resolve_round("cup_final", rounds, chooser)
    # Plate path
    rounds["plate_qf"]    = resolve_round("plate_qf",    rounds, chooser)
    rounds["plate_sf"]    = resolve_round("plate_sf",    rounds, chooser)
    rounds["plate_final"] = resolve_round("plate_final", rounds, chooser)
    # Shield path (Cup QF losers)
    rounds["shield_sf"]    = resolve_round("shield_sf",    rounds, chooser)
    rounds["shield_final"] = resolve_round("shield_final", rounds, chooser)
    # Spoon path (Plate QF losers)
    rounds["spoon_sf"]    = resolve_round("spoon_sf",    rounds, chooser)
    rounds["spoon_final"] = resolve_round("spoon_final", rounds, chooser)
    return rounds


def name_of(p):
    if p is None: return "TBD"
    return p[1] if isinstance(p, tuple) else p


def fmt_match(m):
    return f"{name_of(m['p1']):<14} vs {name_of(m['p2']):<14} → {name_of(m['winner'])}"


def print_bracket(rounds, label):
    print(f"\n========== {label} ==========")
    print("\n— R16 (May, Yinli front 9) —")
    for m in rounds["r16"]:
        print(f"  M{m['idx']+1}: {fmt_match(m)}")
    print("\n— Cup QF (May, Yinli back 9) — winners of R16")
    for m in rounds["cup_qf"]:    print(f"  CQ{m['idx']+1}: {fmt_match(m)}")
    print("— Plate QF (May, Yinli back 9) — losers of R16")
    for m in rounds["plate_qf"]:  print(f"  PQ{m['idx']+1}: {fmt_match(m)}")
    print("\n— Cup SF (June, Birds front 9) —")
    for m in rounds["cup_sf"]:    print(f"  CS{m['idx']+1}: {fmt_match(m)}")
    print("— Plate SF (June, Birds front 9) —")
    for m in rounds["plate_sf"]:  print(f"  PS{m['idx']+1}: {fmt_match(m)}")
    print("— Shield SF (June, Birds front 9) — Cup QF losers")
    for m in rounds["shield_sf"]: print(f"  SS{m['idx']+1}: {fmt_match(m)}")
    print("— Spoon SF (June, Birds front 9) — Plate QF losers")
    for m in rounds["spoon_sf"]:  print(f"  PS{m['idx']+1}: {fmt_match(m)}")
    print("\n— Finals (June, Birds back 9) —")
    print(f"  CUP    : {fmt_match(rounds['cup_final'][0])}")
    print(f"  PLATE  : {fmt_match(rounds['plate_final'][0])}")
    print(f"  SHIELD : {fmt_match(rounds['shield_final'][0])}")
    print(f"  SPOON  : {fmt_match(rounds['spoon_final'][0])}")
    cup    = name_of(rounds["cup_final"][0]["winner"])
    plate  = name_of(rounds["plate_final"][0]["winner"])
    shield = name_of(rounds["shield_final"][0]["winner"])
    spoon  = name_of(rounds["spoon_final"][0]["winner"])
    print(f"\n— Trophies — Cup:{cup}  Plate:{plate}  Shield:{shield}  Spoon:{spoon}")


def main():
    season = json.loads(SEASON_JSON.read_text(encoding="utf-8"))

    terry_order = "--terry-order" in sys.argv
    best7 = "--best7" in sys.argv
    upsets = set()
    for arg in sys.argv[1:]:
        if arg.startswith("--upsets="):
            upsets = {int(x) - 1 for x in arg.split("=", 1)[1].split(",") if x.strip()}

    seeds = seed_field(season, terry_order=terry_order, best7=best7)
    for i, s in enumerate(seeds):
        s["_seed"] = i  # 0-indexed for chooser logic

    if best7:
        rule_label = "Handbook §10.2 (best-7 desc → round-avg tiebreak)"
    elif terry_order:
        rule_label = "Legacy --terry-order flag (same as default now)"
    else:
        rule_label = "App locked (sum-of-all → round-avg tiebreak, per Terry 2026-05-10)"
    print(f"Seeding rule: {rule_label}")
    print(f"\nField (post-withdrawals: {', '.join(sorted(WITHDRAWALS.keys()))}):")
    print(f"  {'Seed':>4} {'Player':<14} {'seedPts':>7} {'played':>6}")
    for s in seeds:
        print(f"  {s['_seed']+1:>4} {s['name']:<14} {s['seedPoints']:>7} {s['played']:>6}")

    chooser = upset_chooser({s["name"]: s["_seed"] for s in seeds}, upsets) \
              if upsets else chalk_chooser({s["name"]: s["_seed"] for s in seeds})
    label = f"{'Terry-order' if terry_order else 'App-order'} | upsets={sorted(u+1 for u in upsets) or 'none'}"
    rounds = run_simulation(seeds, chooser)
    print_bracket(rounds, label)


if __name__ == "__main__":
    main()
