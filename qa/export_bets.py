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


def truth_table(bundle, groups_scoring):
    """Compute the ACTUAL results from final Stableford (for --results mode).

    Returns {
        'r16': [[pid_1st, pid_2nd, pid_3rd, pid_4th] for each R16 group],
        'fireballBest': pid,
        'fireballWorst': pid,
        'gold': pid,
        'clown': pid,
    }
    """
    r16, fireball, playing = parse_groups(bundle)
    scores = collect_player_scores(bundle, groups_scoring)
    # Default tiebreak: higher Stableford wins; ties broken by lower handicap,
    # then lower gross total. Matches handbook §11 hierarchy.
    def rank_key(pid):
        s = scores.get(pid) or {'pts': 0, 'hcp': 99, 'gross_total': 999}
        return (-s['pts'], s['hcp'], s['gross_total'])

    truth = {'r16': [], 'fireballBest': None, 'fireballWorst': None, 'gold': None, 'clown': None}
    for g in r16:
        ranked = sorted(g['players'], key=rank_key)
        truth['r16'].append(ranked)
    if fireball:
        ranked = sorted(fireball, key=rank_key)
        truth['fireballBest']  = ranked[0] if ranked else None
        truth['fireballWorst'] = ranked[-1] if ranked else None
    if playing:
        ranked = sorted(playing, key=rank_key)
        truth['gold']  = ranked[0]
        truth['clown'] = ranked[-1]
    return truth, scores


def score_punter(picks, truth):
    """Return {'r16': [pts_per_group], 'fireballBest': 0/1, ..., 'total': N}."""
    out = {'r16': [], 'fireballBest': 0, 'fireballWorst': 0, 'gold': 0, 'clown': 0, 'total': 0}
    # R16: 1 point per exactly-placed player (positional match, not "had the right 4")
    actual_r16 = truth.get('r16') or []
    picks_r16 = picks.get('r16') or []
    for gi, actual in enumerate(actual_r16):
        picked = picks_r16[gi] if gi < len(picks_r16) else []
        pts = 0
        for rank in range(min(4, len(actual), len(picked))):
            if actual[rank] == picked[rank]:
                pts += 1
        out['r16'].append(pts)
        out['total'] += pts
    if truth.get('fireballBest') and picks.get('fireballBest') == truth['fireballBest']:
        out['fireballBest'] = 1; out['total'] += 1
    if truth.get('fireballWorst') and picks.get('fireballWorst') == truth['fireballWorst']:
        out['fireballWorst'] = 1; out['total'] += 1
    if truth.get('gold') and picks.get('gold') == truth['gold']:
        out['gold'] = 1; out['total'] += 1
    if truth.get('clown') and picks.get('clown') == truth['clown']:
        out['clown'] = 1; out['total'] += 1
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
        for gi, ranked in enumerate(truth['r16']):
            names = ' · '.join(f'{rank+1}. {n(pid)}' for rank, pid in enumerate(ranked[:4]))
            lines.append(f'R16 G{gi+1}: {names}')
        lines.append(f'Fireball 🥇 best:  {n(truth["fireballBest"])}')
        lines.append(f'Fireball 🥄 worst: {n(truth["fireballWorst"])}')
        lines.append(f'🥇 Gold Jacket:   {n(truth["gold"])}')
        lines.append(f'🤡 Clown Jacket:  {n(truth["clown"])}')
        lines.append('')

    # If we have results, sort punters by their score
    punters = sorted(bets.items(), key=lambda kv: kv[0])
    if results:
        punters = sorted(bets.items(), key=lambda kv: -(results.get(kv[0], {}).get('total', 0)))
        lines.append('── PUNTER LEADERBOARD ──────────────────────────────────')
        for rank, (pid, b) in enumerate(punters, 1):
            r = results.get(pid, {'total': 0})
            marker = '🏆' if rank == 1 else f'{rank:2}.'
            lines.append(f'{marker} {b.get("punter", pid):<20} {r["total"]:>2} / 20')
        lines.append('')

    lines.append('── ALL TICKETS ──────────────────────────────────────────')
    for pid, b in punters:
        r = results.get(pid) if results else None
        submitted = b.get('submittedAt', '?')
        score_tag = f'  [{r["total"]}/20]' if r else ''
        lines.append('')
        lines.append(f'━━ {b.get("punter", pid)} ━━  submitted {submitted}{score_tag}')
        for gi, picks in enumerate(b.get('r16') or []):
            placements = []
            for rank, pp in enumerate(picks):
                tag = ''
                if r:
                    actual = (truth['r16'][gi] if truth else [])
                    if rank < len(actual) and actual[rank] == pp:
                        tag = ' ✓'
                placements.append(f'{rank+1}. {n(pp)}{tag}')
            lines.append(f'  R16 G{gi+1}: ' + ' · '.join(placements))
        lines.append(f'  🔥 Best/Worst: {n(b.get("fireballBest"))} / {n(b.get("fireballWorst"))}')
        lines.append(f'  🥇 Gold: {n(b.get("gold"))}    🤡 Clown: {n(b.get("clown"))}')

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
        body_parts.append('<h2>Actual results</h2><table class="truth">')
        for gi, ranked in enumerate(truth['r16']):
            cells = ''.join(f'<td>{rank+1}. {_h(n(pid))}</td>' for rank, pid in enumerate(ranked[:4]))
            body_parts.append(f'<tr><th>R16 G{gi+1}</th>{cells}</tr>')
        body_parts.append(f'<tr class="award"><th>Fireball best</th><td colspan="4">{_h(n(truth["fireballBest"]))}</td></tr>')
        body_parts.append(f'<tr class="award"><th>Fireball worst</th><td colspan="4">{_h(n(truth["fireballWorst"]))}</td></tr>')
        body_parts.append(f'<tr class="award gold"><th>Gold Jacket</th><td colspan="4">{_h(n(truth["gold"]))}</td></tr>')
        body_parts.append(f'<tr class="award clown"><th>Clown Jacket</th><td colspan="4">{_h(n(truth["clown"]))}</td></tr>')
        body_parts.append('</table>')

    punters = sorted(bets.items(), key=lambda kv: kv[0])
    if results:
        punters = sorted(bets.items(), key=lambda kv: -(results.get(kv[0], {}).get('total', 0)))
        body_parts.append('<h2>Punter leaderboard</h2><ol class="punter-board">')
        for pid, b in punters:
            r = results.get(pid, {'total': 0})
            body_parts.append(f'<li><strong>{_h(b.get("punter", pid))}</strong> — {r["total"]} / 20</li>')
        body_parts.append('</ol>')

    body_parts.append('<h2>All tickets</h2>')
    for pid, b in punters:
        r = results.get(pid) if results else None
        body_parts.append('<div class="ticket">')
        head = f'<h3>{_h(b.get("punter", pid))}'
        if r:
            head += f' <span class="score">{r["total"]} / 20</span>'
        head += '</h3>'
        body_parts.append(head)
        body_parts.append(f'<p class="ts">Submitted {_h(b.get("submittedAt", "?"))}</p>')
        body_parts.append('<table class="picks">')
        for gi, picks in enumerate(b.get('r16') or []):
            row_cells = []
            actual = (truth['r16'][gi] if truth else [])
            for rank, pp in enumerate(picks):
                hit = (rank < len(actual) and actual[rank] == pp) if truth else False
                cls = ' class="hit"' if hit else ''
                row_cells.append(f'<td{cls}>{rank+1}. {_h(n(pp))}</td>')
            body_parts.append(f'<tr><th>R16 G{gi+1}</th>{"".join(row_cells)}</tr>')

        def _pickrow(label, pid_picked, truth_key):
            hit = bool(truth and truth.get(truth_key) == pid_picked)
            cls = ' class="hit"' if hit else ''
            return f'<tr><th>{label}</th><td colspan="4"{cls}>{_h(n(pid_picked))}</td></tr>'

        body_parts.append(_pickrow('🔥 Fireball best',  b.get('fireballBest'),  'fireballBest'))
        body_parts.append(_pickrow('🥄 Fireball worst', b.get('fireballWorst'), 'fireballWorst'))
        body_parts.append(_pickrow('🥇 Gold',           b.get('gold'),          'gold'))
        body_parts.append(_pickrow('🤡 Clown',          b.get('clown'),         'clown'))
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
  td.hit {{ background: #cdf2d1; font-weight: 600; }}
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
        eid = fb_get('chubbs/currentEvent')
        if not eid:
            print('ERROR: no event ID supplied and /chubbs/currentEvent is empty.')
            sys.exit(2)

    print(f'Event:   {eid}')
    bundle = fb_get(f'events/{eid}/bundle')
    if not bundle:
        print(f'ERROR: no bundle at /events/{eid}/bundle')
        sys.exit(2)

    print('Fetching bets (auth required)...')
    bets = fb_get(f'events/{eid}/bets', auth=secret) or {}
    print(f'  -> {len(bets)} bet(s) found.')

    truth = None
    results = None
    if args.results:
        print('Fetching live group scores...')
        groups = fb_get(f'events/{eid}/groups') or {}
        truth, _scores = truth_table(bundle, groups)
        results = {pid: score_punter(b, truth) for pid, b in bets.items()}

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
        print('\nFinal ranking:')
        for rank, (pid, _b) in enumerate(
            sorted(bets.items(), key=lambda kv: -(results.get(kv[0], {}).get('total', 0))), 1
        ):
            r = results.get(pid, {'total': 0})
            name = bets[pid].get('punter', pid)
            print(f'  {rank:2}. {name:<22} {r["total"]:>2} / 20')


if __name__ == '__main__':
    main()
