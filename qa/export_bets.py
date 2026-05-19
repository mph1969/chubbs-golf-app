"""
Chubbs Playoff Pool — admin export script.

Pulls bets from Firebase (read-locked node, requires admin auth), writes
three audit artefacts to docs/audit/:

  * <eid>-<ts>-snapshot.json   raw bets + bundle snapshot (full data)
  * <eid>-<ts>-picks.txt       WeChat-ready plain text (paste into chat)
  * <eid>-<ts>-picks.html      printable layout (open in browser -> Save as PDF)

With --results the script also reads /events/{id}/groups, computes each
player's final Stableford total, ranks the four R16 foursomes by that
total, picks the Fireball best/worst + Gold/Clown, scores every punter's
ticket (1 point per correct pick, 20 max), and ranks them.

Auth: Firebase rules disallow public reads on /events/{id}/bets. To pull
that node you need a database secret. Get one from:
  Firebase Console > Project Settings > Service Accounts > Database secrets
  > "Show secret"
Save it in a local file (do NOT commit) at one of these locations:

  qa/.firebase-secret              (repo-local; gitignored)
  $env:CHUBBS_FIREBASE_SECRET      (PowerShell env var)

Usage:
  python qa/export_bets.py                       # auto-detect event, snapshot only
  python qa/export_bets.py 2026-LIVE-MAY-...     # specific event
  python qa/export_bets.py --results             # snapshot + computed scoring
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

FB = 'https://chubbs-golf-default-rtdb.asia-southeast1.firebasedatabase.app'
REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = REPO_ROOT / 'docs' / 'audit'

# Yinli course data (mirror of COURSE_LIBRARY['yinli'].holes in the PWA).
# Hard-coded here so the audit script doesn't depend on the bundle including
# course details. If the event is played at a different course, this needs
# to be extended — but for Chubbs through Nov 2026 the course is locked.
YINLI = [
    {'par': 4, 'si': 11}, {'par': 4, 'si': 8},  {'par': 3, 'si': 16},
    {'par': 5, 'si': 4},  {'par': 4, 'si': 18}, {'par': 4, 'si': 6},
    {'par': 4, 'si': 13}, {'par': 3, 'si': 10}, {'par': 5, 'si': 3},
    {'par': 4, 'si': 15}, {'par': 4, 'si': 9},  {'par': 3, 'si': 17},
    {'par': 5, 'si': 5},  {'par': 4, 'si': 12}, {'par': 3, 'si': 14},
    {'par': 4, 'si': 2},  {'par': 4, 'si': 1},  {'par': 5, 'si': 7},
]


# ── Firebase access ───────────────────────────────────────────────────────

def _load_secret():
    """Read the Firebase database secret from env var or local file."""
    env = os.environ.get('CHUBBS_FIREBASE_SECRET')
    if env:
        return env.strip()
    secret_file = REPO_ROOT / 'qa' / '.firebase-secret'
    if secret_file.exists():
        return secret_file.read_text(encoding='utf-8').strip()
    return None


def fb_get(path, auth=None):
    """GET https://.../path.json -> Python value. Returns None on 404."""
    url = f'{FB}/{path}.json'
    if auth:
        url += '?' + urllib.parse.urlencode({'auth': auth})
    try:
        with urllib.request.urlopen(url) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        body = e.read().decode('utf-8', errors='replace')[:400]
        raise SystemExit(f'Firebase {e.code} on {path}: {body}')


# ── Scoring engine ────────────────────────────────────────────────────────

def stableford_pts(gross, par, hcp, si):
    """6-5-4-3-2-1 stableford (Chubbs handbook §6.1)."""
    if gross is None:
        return 0
    safe = max(0, int(hcp or 0))
    shots = (safe // 18) + (1 if si <= (safe % 18) else 0)
    net = gross - shots
    diff = net - par
    return {-4: 6, -3: 5, -2: 4, -1: 3, 0: 2, 1: 1}.get(max(diff, -4) if diff < 1 else diff, 0)


def player_stableford(grosses, hcp):
    pts = 0
    for i, ch in enumerate(YINLI):
        if i >= len(grosses):
            break
        g = grosses[i]
        if isinstance(g, (int, float)):
            pts += stableford_pts(int(g), ch['par'], hcp, ch['si'])
    return pts


def collect_player_scores(bundle, groups):
    """Return {playerId: {'name': str, 'hcp': int, 'pts': int, 'holes': int}}."""
    players = bundle.get('players') or []
    pid_to_player = {p['playerId']: p for p in players}
    out = {}
    for gid, g in (groups or {}).items():
        rps = g.get('players') or []
        holes = g.get('holes') or []
        for ri, rp in enumerate(rps):
            if not rp:
                continue
            pid = rp.get('playerId') or rp.get('name')
            if not pid or pid not in pid_to_player:
                continue
            player = pid_to_player[pid]
            grosses = []
            for h in holes:
                if h and isinstance(h.get('gross'), list) and ri < len(h['gross']):
                    grosses.append(h['gross'][ri])
                else:
                    grosses.append(None)
            hcp = int(player.get('playingHandicap') or 0)
            entered = sum(1 for x in grosses if isinstance(x, (int, float)))
            pts = player_stableford(grosses, hcp)
            out[pid] = {
                'name': player.get('displayName') or player.get('fullName') or pid,
                'hcp': hcp,
                'pts': pts,
                'holes': entered,
                'gross_total': sum(int(x) for x in grosses if isinstance(x, (int, float))) or 0,
            }
    return out


# ── Bundle parsing ────────────────────────────────────────────────────────

def parse_groups(bundle):
    """Return (r16_groups, fireball_pids, all_playing_pids)."""
    day2 = bundle.get('day2Groups') or []
    r16 = []
    fireball = set()
    playing = set()
    for g in day2:
        name = g.get('groupName') or ''
        pids = g.get('playerIds') or []
        if re.search(r'R16|M\d', name, re.IGNORECASE):
            r16.append({'name': name, 'players': list(pids)})
            playing.update(pids)
        else:
            fireball.update(pids)
            playing.update(pids)
    return r16, fireball, playing


def _name_to_pid(bundle):
    """Build a normalized-displayName -> playerId lookup. Bracket records
    store the winner as displayName (e.g. "JAMIE", "JACK S"), so we need to
    map back to playerId for cross-referencing against the bundle.players
    + day2Groups data.
    """
    out = {}
    def norm(s):
        return re.sub(r"[.,'\"`\s]+", '', str(s or '').upper())
    for p in (bundle.get('players') or []):
        pid = p['playerId']
        for k in ('displayName', 'fullName', 'shortName'):
            if p.get(k):
                out[norm(p[k])] = pid
        for alias in (p.get('aliases') or []):
            out[norm(alias)] = pid
        out[norm(pid)] = pid  # self-map as fallback
    return lambda name: out.get(norm(name)) if name else None


def _bracket_array(bracket, key):
    """Firebase returns dense arrays as lists, sparse as dict-with-string-keys."""
    raw = (bracket or {}).get(key)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        out = []
        for k, v in raw.items():
            try: out.append((int(k), v))
            except (ValueError, TypeError): pass
        out.sort(key=lambda kv: kv[0])
        return [v for _, v in out]
    return []


def truth_table(bundle, groups_scoring, bracket):
    """Compute the ACTUAL results.

    R16 ranking (per Diego's spec): match-play cascade outcome.
      1st = R16 winner + Cup QF winner   (cup_qf[i].winner)
      2nd = R16 winner + Cup QF loser    (other r16 winner from this G)
      3rd = R16 loser  + Plate QF winner (plate_qf[i].winner)
      4th = R16 loser  + Plate QF loser  (other r16 loser from this G)

    Fireball + Gold/Clown are Stableford-based (the only objective
    measure for non-playoff and across-the-field rankings).

    Returns the truth dict + the raw stableford scores (for debugging).
    """
    r16_groups, fireball_pids, playing_pids = parse_groups(bundle)
    scores = collect_player_scores(bundle, groups_scoring)
    name_to_pid = _name_to_pid(bundle)

    truth = {'r16': [], 'fireballBest': None, 'fireballWorst': None,
             'gold': None, 'clown': None,
             # Notes back to the caller so the audit report can flag missing
             # bracket data explicitly instead of silently falling back.
             '_bracketComplete': True, '_bracketNotes': []}

    r16_matches    = _bracket_array(bracket, 'r16')
    cupqf_matches  = _bracket_array(bracket, 'cup_qf')
    plateqf_matches = _bracket_array(bracket, 'plate_qf')

    # R16 group Gi (0..3) corresponds to matches r16[2i] + r16[2i+1] and
    # bracket nodes cup_qf[i] + plate_qf[i] (each QF node pairs the two
    # winners / two losers from that R16 group).
    for gi, group in enumerate(r16_groups):
        group_pids = set(group['players'])
        m_top    = r16_matches[2*gi]   if 2*gi   < len(r16_matches) else None
        m_bot    = r16_matches[2*gi+1] if 2*gi+1 < len(r16_matches) else None
        cup_qf   = cupqf_matches[gi]   if gi     < len(cupqf_matches) else None
        plate_qf = plateqf_matches[gi] if gi     < len(plateqf_matches) else None

        w_top = name_to_pid((m_top or {}).get('winner')) if m_top else None
        w_bot = name_to_pid((m_bot or {}).get('winner')) if m_bot else None
        winners = [w for w in (w_top, w_bot) if w in group_pids]
        losers  = [pid for pid in group['players'] if pid not in winners]

        if len(winners) != 2 or len(losers) != 2:
            # R16 not fully saved yet — fall back to Stableford ordering for
            # this group so a partial round still produces *some* truth table.
            truth['_bracketComplete'] = False
            truth['_bracketNotes'].append(
                f'R16 G{gi+1}: only {len(winners)} winners resolvable from bracket; falling back to Stableford.'
            )
            def rank_key(pid):
                s = scores.get(pid) or {'pts': 0, 'hcp': 99, 'gross_total': 999}
                return (-s['pts'], s['hcp'], s['gross_total'])
            truth['r16'].append(sorted(group['players'], key=rank_key))
            continue

        cup_winner = name_to_pid((cup_qf or {}).get('winner'))
        if cup_winner not in winners:
            truth['_bracketComplete'] = False
            truth['_bracketNotes'].append(f'R16 G{gi+1}: Cup QF not saved; 1st/2nd cannot be determined.')
            # Still surface SOMETHING — winners in arbitrary order.
            first, second = winners[0], winners[1]
        else:
            first  = cup_winner
            second = next(w for w in winners if w != cup_winner)

        plate_winner = name_to_pid((plate_qf or {}).get('winner'))
        if plate_winner not in losers:
            truth['_bracketComplete'] = False
            truth['_bracketNotes'].append(f'R16 G{gi+1}: Plate QF not saved; 3rd/4th cannot be determined.')
            third, fourth = losers[0], losers[1]
        else:
            third  = plate_winner
            fourth = next(l for l in losers if l != plate_winner)

        truth['r16'].append([first, second, third, fourth])

    # Fireball + Gold/Clown stay Stableford-based.
    def rank_key(pid):
        s = scores.get(pid) or {'pts': 0, 'hcp': 99, 'gross_total': 999}
        return (-s['pts'], s['hcp'], s['gross_total'])
    if fireball_pids:
        ranked = sorted(fireball_pids, key=rank_key)
        truth['fireballBest']  = ranked[0]
        truth['fireballWorst'] = ranked[-1]
        # Full ranking 1..N (1 = best Stableford) — feeds the closeness
        # tiebreak so missing the #1 by one rank still scores something.
        truth['_fireballRanking'] = {pid: i + 1 for i, pid in enumerate(ranked)}
        truth['_fireballPoolSize'] = len(ranked)
    if playing_pids:
        ranked = sorted(playing_pids, key=rank_key)
        truth['gold']  = ranked[0]
        truth['clown'] = ranked[-1]
    return truth, scores


def season_attendance_by_pid(bundle):
    """Read ChubbsMobileApp_v5/season-4.json and return {playerId: events_count}.

    Resolution: the season file stores names ("Matt D", "Ryan N", etc.) while
    everything else in the codebase uses playerIds ("MATT", "RYANN"). Run
    every season-4 name through the bundle's alias-aware name resolver so
    e.g. "Mike H" -> "HANSON" via the Hanson alias entry.

    Used as the final tiebreaker on the playoff pool — rewards punters who
    show up to Chubbs events.
    """
    season_path = REPO_ROOT / 'ChubbsMobileApp_v5' / 'season-4.json'
    if not season_path.exists():
        return {}
    s = json.load(open(season_path, 'r', encoding='utf-8'))
    n2p = _name_to_pid(bundle)
    counts = {}
    for ev in (s.get('events') or []):
        # Each event has a players[] of {name, gross[], hcp}. Presence in
        # players[] counts as attendance (no scoring filter — a player who
        # DNF'd still attended).
        for p in (ev.get('players') or []):
            name = p.get('name')
            if not name:
                continue
            pid = n2p(name)
            if pid:
                counts[pid] = counts.get(pid, 0) + 1
    return counts


def score_punter(picks, truth):
    """Compute a punter's score.

    Rubric (max 22 base pts):
      R16 placements: 1pt each (max 16)
      R16 exact-foursome bonus: +1pt per group where all 4 are exact (max 4)
      Gold Jacket: 1pt
      Clown Jacket: 1pt

    Tiebreaker — Fireball closeness (max 2 * pool_size):
      Best pick:  pool_size + 1 - rank_of_picked_player
      Worst pick: rank_of_picked_player
      (Ranks are 1..N by Stableford within the Fireball pool, 1 = best.)
      A perfect best pick scores pool_size; missing by 1 rank scores
      pool_size - 1; missing by max rank still scores 1. Mirrors for worst.

    Final tiebreak (computed in main, not here):
      events_attended — punter's Season 4 attendance count

    Sort punters by (-total, -tiebreak_total, -events_attended, name).
    """
    out = {
        'r16': [],            # per-group placement pts (0..4)
        'r16_exact': [],      # per-group bonus (0 or 1)
        'gold': 0,
        'clown': 0,
        'fb_best_pts':  0,    # closeness pts on Fireball best pick
        'fb_worst_pts': 0,    # closeness pts on Fireball worst pick
        'total': 0,           # base score, max 22
        'tiebreak_total': 0   # fb_best_pts + fb_worst_pts, max 2*pool_size
    }
    actual_r16 = truth.get('r16') or []
    picks_r16 = picks.get('r16') or []
    for gi, actual in enumerate(actual_r16):
        picked = picks_r16[gi] if gi < len(picks_r16) else []
        compared = min(4, len(actual), len(picked))
        pts = sum(1 for rank in range(compared) if actual[rank] == picked[rank])
        out['r16'].append(pts)
        out['total'] += pts
        # Exact-foursome bonus: all 4 positions correct in this group
        exact = (pts == 4 and compared == 4)
        out['r16_exact'].append(1 if exact else 0)
        if exact:
            out['total'] += 1
    if truth.get('gold') and picks.get('gold') == truth['gold']:
        out['gold'] = 1; out['total'] += 1
    if truth.get('clown') and picks.get('clown') == truth['clown']:
        out['clown'] = 1; out['total'] += 1
    # Fireball closeness tiebreak — uses the full 1..N ranking, not just
    # the binary best/worst-match check. Picking #2 for best in a 6-pool
    # scores 5 (vs 6 for #1, 1 for #6).
    fb_rank = truth.get('_fireballRanking') or {}
    pool = truth.get('_fireballPoolSize') or 0
    if pool > 0:
        rank_best = fb_rank.get(picks.get('fireballBest'))
        if rank_best:
            out['fb_best_pts'] = pool + 1 - rank_best
        rank_worst = fb_rank.get(picks.get('fireballWorst'))
        if rank_worst:
            out['fb_worst_pts'] = rank_worst
        out['tiebreak_total'] = out['fb_best_pts'] + out['fb_worst_pts']
    return out


# ── Render helpers ────────────────────────────────────────────────────────

def name_lookup(bundle):
    pmap = {}
    for p in (bundle.get('players') or []):
        pmap[p['playerId']] = p.get('displayName') or p.get('fullName') or p['playerId']
    return lambda pid: pmap.get(pid, pid or '—')


def render_text(eid, when, bundle, bets, results=None, truth=None):
    """WeChat-ready plain text (UTF-8). One file, all picks visible."""
    n = name_lookup(bundle)
    ev = bundle.get('event') or {}
    title = ev.get('displayName') or ev.get('name') or eid
    lines = []
    lines.append('═' * 60)
    lines.append(f'  CHUBBS PLAYOFF POOL · {title}')
    lines.append(f'  Snapshot: {when}')
    lines.append(f'  Event ID: {eid}')
    lines.append(f'  Punters:  {len(bets)}')
    lines.append('═' * 60)

    if truth:
        lines.append('')
        lines.append('── ACTUAL RESULTS ──────────────────────────────────────')
        if not truth.get('_bracketComplete'):
            lines.append('⚠ Bracket incomplete — some positions fell back to Stableford:')
            for note in (truth.get('_bracketNotes') or []):
                lines.append(f'   · {note}')
            lines.append('')
        for gi, ranked in enumerate(truth['r16']):
            names = ' · '.join(f'{rank+1}. {n(pid)}' for rank, pid in enumerate(ranked[:4]))
            lines.append(f'R16 G{gi+1}: {names}')
        lines.append(f'Fireball 🥇 best:  {n(truth["fireballBest"])}')
        lines.append(f'Fireball 🥄 worst: {n(truth["fireballWorst"])}')
        lines.append(f'🥇 Gold Jacket:   {n(truth["gold"])}')
        lines.append(f'🤡 Clown Jacket:  {n(truth["clown"])}')
        lines.append('')

    # Split into paid (entered) and unpaid (submitted-but-not-entered) buckets.
    # Per Diego's rule: "not marked paid, not entered — even if they submit
    # a form." So unpaid tickets appear in the audit (for transparency) but
    # are excluded from the scoring leaderboard.
    paid_bets   = {pid: b for pid, b in bets.items() if b.get('paid')}
    unpaid_bets = {pid: b for pid, b in bets.items() if not b.get('paid')}

    # Default ordering when no results: alphabetical by punter id
    paid_punters   = sorted(paid_bets.items(),   key=lambda kv: kv[0])
    unpaid_punters = sorted(unpaid_bets.items(), key=lambda kv: kv[0])

    if results:
        def _sort_key(kv):
            r = results.get(kv[0]) or {}
            return (
                -r.get('total', 0),
                -r.get('tiebreak_total', 0),
                -r.get('events_attended', 0),
                kv[1].get('punter', '').upper(),
            )
        paid_punters = sorted(paid_bets.items(), key=_sort_key)
        lines.append('── PUNTER LEADERBOARD (paid entries only) ──────────────')
        if not paid_punters:
            lines.append('(no paid entries yet)')
        for rank, (pid, b) in enumerate(paid_punters, 1):
            r = results.get(pid, {'total': 0, 'tiebreak_total': 0, 'events_attended': 0})
            marker = '🏆' if rank == 1 else f'{rank:2}.'
            tb_parts = []
            if r.get('tiebreak_total'):
                tb_parts.append(f'🔥 {r["tiebreak_total"]}')
            if r.get('events_attended'):
                tb_parts.append(f'attend {r["events_attended"]}')
            tb = '  (' + ' · '.join(tb_parts) + ')' if tb_parts else ''
            lines.append(f'{marker} {b.get("punter", pid):<20} {r["total"]:>2} / 22{tb}')
        lines.append('')

    if unpaid_bets:
        lines.append('── SUBMITTED BUT NOT PAID (excluded from pool) ─────────')
        for pid, b in unpaid_punters:
            lines.append(f'   {b.get("punter", pid):<20} submitted {b.get("submittedAt", "?")}')
        lines.append('')

    # The "all tickets" section below this still walks every submission
    # so the paper trail shows both paid + unpaid.
    punters = paid_punters + unpaid_punters

    lines.append('── ALL TICKETS ──────────────────────────────────────────')
    for pid, b in punters:
        r = results.get(pid) if results else None
        submitted = b.get('submittedAt', '?')
        paid_tag = '  · ✓ PAID' if b.get('paid') else '  · ⚠ UNPAID (not entered)'
        score_tag = ''
        if r and b.get('paid'):
            tb = f' · TB 🔥 {r["tiebreak_total"]}/2' if r.get('tiebreak_total') else ''
            score_tag = f'  [{r["total"]}/22{tb}]'
        lines.append('')
        lines.append(f'━━ {b.get("punter", pid)} ━━  submitted {submitted}{paid_tag}{score_tag}')
        if r and r.get('events_attended') is not None:
            lines.append(f'   Season 4 attendance (final TB): {r["events_attended"]}')
        for gi, picks in enumerate(b.get('r16') or []):
            placements = []
            for rank, pp in enumerate(picks):
                tag = ''
                if r:
                    actual = (truth['r16'][gi] if truth else [])
                    if rank < len(actual) and actual[rank] == pp:
                        tag = ' ✓'
                placements.append(f'{rank+1}. {n(pp)}{tag}')
            bonus = ''
            if r and (r.get('r16_exact') or [])[gi:gi+1] == [1]:
                bonus = '  +1 EXACT 🎯'
            lines.append(f'  R16 G{gi+1}: ' + ' · '.join(placements) + bonus)
        lines.append(f'  🥇 Gold: {n(b.get("gold"))}    🤡 Clown: {n(b.get("clown"))}')
        lines.append(f'  🔥 Fireball best/worst (TB): {n(b.get("fireballBest"))} / {n(b.get("fireballWorst"))}')

    lines.append('')
    lines.append('═' * 60)
    lines.append('  End of audit snapshot')
    lines.append('═' * 60)
    return '\n'.join(lines)


def render_html(eid, when, bundle, bets, results=None, truth=None):
    """Printable HTML — Ctrl+P in any browser -> Save as PDF."""
    n = name_lookup(bundle)
    ev = bundle.get('event') or {}
    title = ev.get('displayName') or ev.get('name') or eid
    body_parts = []
    body_parts.append(f'<h1>Chubbs Playoff Pool · {_h(title)}</h1>')
    body_parts.append(f'<p class="meta">Snapshot: {_h(when)} · Event ID: <code>{_h(eid)}</code> · {len(bets)} punter(s)</p>')

    if truth:
        body_parts.append('<h2>Actual results</h2>')
        if not truth.get('_bracketComplete'):
            notes = ''.join(f'<li>{_h(n)}</li>' for n in (truth.get('_bracketNotes') or []))
            body_parts.append(
                f'<div style="background:#fff4d0;border:1px solid #d6c47a;border-radius:6px;'
                f'padding:8px 12px;margin-bottom:10px;font-size:11px">'
                f'<strong>Bracket incomplete</strong> — some positions fell back to Stableford:'
                f'<ul style="margin:4px 0 0;padding-left:20px">{notes}</ul></div>'
            )
        body_parts.append('<table class="truth">')
        for gi, ranked in enumerate(truth['r16']):
            cells = ''.join(f'<td>{rank+1}. {_h(n(pid))}</td>' for rank, pid in enumerate(ranked[:4]))
            body_parts.append(f'<tr><th>R16 G{gi+1}</th>{cells}</tr>')
        body_parts.append(f'<tr class="award"><th>Fireball best</th><td colspan="4">{_h(n(truth["fireballBest"]))}</td></tr>')
        body_parts.append(f'<tr class="award"><th>Fireball worst</th><td colspan="4">{_h(n(truth["fireballWorst"]))}</td></tr>')
        body_parts.append(f'<tr class="award gold"><th>Gold Jacket</th><td colspan="4">{_h(n(truth["gold"]))}</td></tr>')
        body_parts.append(f'<tr class="award clown"><th>Clown Jacket</th><td colspan="4">{_h(n(truth["clown"]))}</td></tr>')
        body_parts.append('</table>')

    paid_bets   = {pid: b for pid, b in bets.items() if b.get('paid')}
    unpaid_bets = {pid: b for pid, b in bets.items() if not b.get('paid')}
    paid_punters   = sorted(paid_bets.items(),   key=lambda kv: kv[0])
    unpaid_punters = sorted(unpaid_bets.items(), key=lambda kv: kv[0])

    if results:
        def _sort_key(kv):
            r = results.get(kv[0]) or {}
            return (
                -r.get('total', 0),
                -r.get('tiebreak_total', 0),
                -r.get('events_attended', 0),
                kv[1].get('punter', '').upper(),
            )
        paid_punters = sorted(paid_bets.items(), key=_sort_key)
        body_parts.append('<h2>Punter leaderboard <span class="tb">(paid entries only)</span></h2><ol class="punter-board">')
        if not paid_punters:
            body_parts.append('<li class="tb">(no paid entries yet)</li>')
        for pid, b in paid_punters:
            r = results.get(pid, {'total': 0, 'tiebreak_total': 0, 'events_attended': 0})
            parts = []
            if r.get('tiebreak_total'): parts.append(f'🔥 {r["tiebreak_total"]}')
            if r.get('events_attended'): parts.append(f'attend {r["events_attended"]}')
            tb = f' <span class="tb">({" · ".join(parts)})</span>' if parts else ''
            body_parts.append(f'<li><strong>{_h(b.get("punter", pid))}</strong> — {r["total"]} / 22{tb}</li>')
        body_parts.append('</ol>')

    if unpaid_bets:
        body_parts.append('<h2>Submitted but not paid <span class="tb">(excluded from pool)</span></h2><ul class="punter-board">')
        for pid, b in unpaid_punters:
            body_parts.append(f'<li class="tb">{_h(b.get("punter", pid))} — submitted {_h(b.get("submittedAt", "?"))}</li>')
        body_parts.append('</ul>')

    punters = paid_punters + unpaid_punters
    body_parts.append('<h2>All tickets</h2>')
    for pid, b in punters:
        r = results.get(pid) if results and b.get('paid') else None
        body_parts.append(f'<div class="ticket{" unpaid" if not b.get("paid") else ""}">')
        head = f'<h3>{_h(b.get("punter", pid))}'
        if r:
            tb = f' <span class="tb">TB 🔥 {r["tiebreak_total"]}/2</span>' if r.get('tiebreak_total') else ''
            head += f' <span class="score">{r["total"]} / 22</span>{tb}'
        elif not b.get('paid'):
            head += ' <span class="score" style="color:#a04040">⚠ UNPAID</span>'
        head += '</h3>'
        body_parts.append(head)
        paid_line = '✓ Paid' if b.get('paid') else '⚠ Not paid — excluded from pool'
        paid_at = b.get('paidAt')
        if paid_at: paid_line += f' ({_h(paid_at)})'
        body_parts.append(f'<p class="ts">Submitted {_h(b.get("submittedAt", "?"))} · {paid_line}</p>')
        body_parts.append('<table class="picks">')
        exact_groups = (r or {}).get('r16_exact') or []
        for gi, picks in enumerate(b.get('r16') or []):
            row_cells = []
            actual = (truth['r16'][gi] if truth else [])
            for rank, pp in enumerate(picks):
                hit = (rank < len(actual) and actual[rank] == pp) if truth else False
                cls = ' class="hit"' if hit else ''
                row_cells.append(f'<td{cls}>{rank+1}. {_h(n(pp))}</td>')
            bonus_th = 'R16 G' + str(gi+1)
            if exact_groups[gi:gi+1] == [1]:
                bonus_th += ' <span class="bonus">+1 🎯</span>'
            body_parts.append(f'<tr><th>{bonus_th}</th>{"".join(row_cells)}</tr>')

        def _pickrow(label, pid_picked, truth_key):
            hit = bool(truth and truth.get(truth_key) == pid_picked)
            cls = ' class="hit"' if hit else ''
            return f'<tr><th>{label}</th><td colspan="4"{cls}>{_h(n(pid_picked))}</td></tr>'

        body_parts.append(_pickrow('🥇 Gold',           b.get('gold'),          'gold'))
        body_parts.append(_pickrow('🤡 Clown',          b.get('clown'),         'clown'))
        body_parts.append(_pickrow('🔥 Fireball best <span class="tb">(TB)</span>',  b.get('fireballBest'),  'fireballBest'))
        body_parts.append(_pickrow('🥄 Fireball worst <span class="tb">(TB)</span>', b.get('fireballWorst'), 'fireballWorst'))
        body_parts.append('</table></div>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8" />
<title>Chubbs Pool · {_h(title)} · {_h(when)}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 780px; margin: 24px auto; padding: 0 18px; color:#1a1a1a }}
  h1 {{ font-family: Georgia, serif; font-size: 24px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 28px 0 10px; border-bottom: 1px solid #ddd; padding-bottom: 4px; color:#444 }}
  h3 {{ font-size: 14px; margin: 0; }}
  h3 .score {{ float:right; color:#666; font-weight: 400; }}
  .meta {{ color: #666; font-size: 12px; margin-top: 0; }}
  .ts {{ color: #888; font-size: 11px; margin: 2px 0 6px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; font-size: 12px; }}
  th, td {{ padding: 4px 6px; text-align: left; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
  th {{ width: 110px; font-weight: 700; color: #555; background: #fafafa; }}
  .truth tr.award.gold td {{ background: #fff4d0; }}
  .truth tr.award.clown td {{ background: #ffe2dd; }}
  .ticket {{ border: 1px solid #ddd; border-radius: 6px; padding: 10px 12px; margin-bottom: 14px; page-break-inside: avoid; }}
  .ticket.unpaid {{ background: #fff7e6; border-color: #e5c47a; }}
  td.hit {{ background: #cdf2d1; font-weight: 600; }}
  .bonus {{ background: #fff4d0; color: #8a6a00; padding: 1px 6px; border-radius: 6px; font-size: 10px; margin-left: 4px; }}
  .tb {{ color: #999; font-size: 11px; font-weight: 400; }}
  ol.punter-board li {{ margin: 4px 0; font-size: 14px; }}
  code {{ background: #f4f4f4; padding: 1px 5px; border-radius: 3px; font-size: 11px; }}
  @media print {{ body {{ max-width: 100% }} h2 {{ page-break-after: avoid }} }}
</style></head>
<body>
{chr(10).join(body_parts)}
<p style="margin-top:30px;font-size:10px;color:#aaa;text-align:center">
  Generated {_h(when)} · save as PDF via browser print dialog · Chubbs Playoff Pool audit
</p>
</body></html>"""


def _h(s):
    return (str(s) if s is not None else '—').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='Chubbs Playoff Pool — admin export')
    ap.add_argument('event_id', nargs='?', help='Event ID (defaults to /chubbs/currentEvent)')
    ap.add_argument('--results', action='store_true', help='Also compute scoring + winner ranking')
    args = ap.parse_args()

    secret = _load_secret()
    if not secret:
        print('ERROR: no Firebase database secret found.')
        print('  Put it in qa/.firebase-secret (one line) or')
        print('  set $env:CHUBBS_FIREBASE_SECRET in PowerShell.')
        print('  Find the secret at: Firebase Console > Project Settings >')
        print('  Service Accounts > Database secrets > Show secret.')
        sys.exit(2)

    eid = args.event_id
    if not eid:
        # Admin writes /chubbs/currentEvent as
        # { eventId, displayName, ts, publishedBy } rather than a bare
        # string. Unwrap it but stay tolerant of both shapes.
        cur = fb_get('chubbs/currentEvent')
        if isinstance(cur, dict) and cur.get('eventId'):
            eid = cur['eventId']
        elif isinstance(cur, str):
            eid = cur
        if not eid:
            print('ERROR: no event ID supplied and /chubbs/currentEvent is empty.')
            sys.exit(2)

    print(f'Event:   {eid}')
    bundle = fb_get(f'events/{eid}/bundle')
    if not bundle:
        print(f'ERROR: no bundle at /events/{eid}/bundle')
        sys.exit(2)

    print('Fetching bets (auth required)...')
    # Bets live at /bets/{eventId}/{punterId} (not under /events/...) so
    # the .read:false rule can apply without cascading from /events.
    bets = fb_get(f'bets/{eid}', auth=secret) or {}
    print(f'  -> {len(bets)} bet(s) found.')

    # Resolve every punter's typed name -> Season 4 attendance count.
    # Used as the L3 tiebreak; computed unconditionally so audit text can
    # show the full sort hierarchy even in non-results mode.
    attendance_map = season_attendance_by_pid(bundle)
    n2p = _name_to_pid(bundle)
    attendance_per_punter = {
        pid: attendance_map.get(n2p(b.get('punter', '')), 0)
        for pid, b in bets.items()
    }

    truth = None
    results = None
    if args.results:
        print('Fetching live group scores + bracket...')
        groups  = fb_get(f'events/{eid}/groups') or {}
        bracket = fb_get(f'events/{eid}/bracket') or {}
        truth, _scores = truth_table(bundle, groups, bracket)
        if not truth.get('_bracketComplete'):
            print('  WARNING: bracket incomplete:')
            for note in truth.get('_bracketNotes') or []:
                print(f'    - {note}')
        results = {pid: score_punter(b, truth) for pid, b in bets.items()}
        # Stamp each punter's row with their attendance so render functions
        # and sort keys don't need an extra parameter.
        for pid, r in results.items():
            r['events_attended'] = attendance_per_punter.get(pid, 0)

    when = _dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ts_slug = _dt.datetime.now().strftime('%Y%m%d-%H%M%S')

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    eid_slug = re.sub(r'[^A-Za-z0-9_-]+', '-', eid)
    base = AUDIT_DIR / f'{eid_slug}-{ts_slug}'

    snapshot = {
        'eventId': eid,
        'capturedAt': when,
        'bundle': {'event': bundle.get('event'), 'players': bundle.get('players'), 'day2Groups': bundle.get('day2Groups')},
        'bets': bets,
    }
    if truth:
        snapshot['actualResults'] = truth
        snapshot['punterScores'] = results

    (base.with_suffix('.json')).write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding='utf-8')
    (base.with_suffix('.txt')).write_text(render_text(eid, when, bundle, bets, results, truth), encoding='utf-8')
    (base.with_suffix('.html')).write_text(render_html(eid, when, bundle, bets, results, truth), encoding='utf-8')

    print('\nWrote:')
    print(f'  {base.with_suffix(".json")}')
    print(f'  {base.with_suffix(".txt")}')
    print(f'  {base.with_suffix(".html")}')
    if args.results:
        print('\nFinal ranking (paid entries only):')
        def _sk(kv):
            r = results.get(kv[0]) or {}
            return (-r.get('total', 0), -r.get('tiebreak_total', 0),
                    -r.get('events_attended', 0), kv[1].get('punter', '').upper())
        paid = {pid: b for pid, b in bets.items() if b.get('paid')}
        unpaid_count = len(bets) - len(paid)
        if not paid:
            print('  (no paid entries yet)')
        for rank, (pid, _b) in enumerate(sorted(paid.items(), key=_sk), 1):
            r = results.get(pid, {'total': 0, 'tiebreak_total': 0, 'events_attended': 0})
            name = paid[pid].get('punter', pid)
            tbs = []
            if r.get('tiebreak_total'): tbs.append(f'🔥 {r["tiebreak_total"]}')
            if r.get('events_attended'): tbs.append(f'attend {r["events_attended"]}')
            tb = f'  ({" · ".join(tbs)})' if tbs else ''
            print(f'  {rank:2}. {name:<22} {r["total"]:>2} / 22{tb}')
        if unpaid_count:
            print(f'\n  ({unpaid_count} unpaid submission(s) excluded — see audit files)')


if __name__ == '__main__':
    main()
