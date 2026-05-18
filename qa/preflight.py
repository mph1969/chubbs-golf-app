"""
Pre-flight checklist for a Chubbs event in Firebase.

Run this BEFORE telling the brain trust their links are ready. It fetches
the live bundle from Firebase REST and asserts every invariant that has
ever bitten us during pre-event push. Each failure includes a specific
actionable fix.

Usage:
    python qa/preflight.py                          # checks the most recent event
    python qa/preflight.py 2026-LIVE-MAY-LIVE-XYZ   # checks a specific event ID
    python qa/preflight.py --verbose                # detail on each check
    python qa/preflight.py --list                   # list event IDs in Firebase

Exit code: 0 = all clear · 1 = one or more failures.

Failure modes this catches (and the date we got bitten):
  * 2026-05-15 --admin pushed without Playoff Setup toggle on (silent null)
  * 2026-05-15 --mobile's initSync.set() clobbered admin's playoffs payload
  * 2026-05-15 --canonicalisation gap: "Jack" in seeds, "JACK S" in roster
  * 2026-05-15 --`/chubbs/currentEvent` pointer set to wrong / stale event
  * 2026-05-13 --Krungthep SI duplicate (course data corruption)
  * 2026-05-14 --group's scorerPlayerId not in the group's players[]

When this script passes, the bundle is structurally ready for production.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

FIREBASE_BASE = 'https://chubbs-golf-default-rtdb.asia-southeast1.firebasedatabase.app'
INDEX_HTML = Path(__file__).resolve().parent.parent / 'ChubbsMobileApp_v5' / 'index.html'


# ── Firebase REST helpers ──────────────────────────────────────────────────

def fb_get(path: str, params: dict | None = None):
    """GET https://{base}/{path}.json[?params] --returns parsed JSON or None on 404/empty."""
    qs = ''
    if params:
        qs = '?' + '&'.join(f'{k}={v}' for k, v in params.items())
    url = f'{FIREBASE_BASE}/{path.lstrip("/")}.json{qs}'
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
            if not data or data == b'null':
                return None
            return json.loads(data)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def list_events() -> list[str]:
    """Return all event IDs in Firebase /events."""
    data = fb_get('events', params={'shallow': 'true'})
    return sorted(data.keys()) if isinstance(data, dict) else []


def most_recent_event_id() -> str | None:
    """Pick the event most likely to be 'the current one'. Preference order:
      1. The event ID stored in /chubbs/currentEvent (admin's explicit pointer)
      2. The event with the highest bundle._publishedAt
      3. The lexicographically-largest event ID (year-prefixed IDs sort by date)
    """
    ptr = fb_get('chubbs/currentEvent')
    if isinstance(ptr, dict) and ptr.get('eventId'):
        return str(ptr['eventId'])
    ids = list_events()
    if not ids:
        return None
    if len(ids) == 1:
        return ids[0]
    best = None
    best_ts = -1
    for eid in ids:
        ts = fb_get(f'events/{eid}/bundle/_publishedAt')
        if isinstance(ts, (int, float)) and ts > best_ts:
            best_ts = ts
            best = eid
    return best or sorted(ids)[-1]


# ── Canonicalisation (Python port of canonicaliseSeedName) ─────────────────


def norm(s) -> str:
    if s is None:
        return ''
    out = str(s).strip().upper()
    out = re.sub(r"[.,'\"`]", '', out)
    out = re.sub(r'\s+', ' ', out)
    return out


def canonicalise(seed_name, roster):
    """Mirror the mobile-side canonicaliseSeedName logic exactly. Returns the
    canonical displayName if matched, else the original seed_name."""
    target = norm(seed_name)
    if not target or not roster:
        return seed_name
    for p in roster:
        if not p:
            continue
        if norm(p.get('displayName')) == target:
            return p['displayName']
        if norm(p.get('fullName')) == target:
            return p['displayName']
        for alias in (p.get('aliases') or []):
            if norm(alias) == target:
                return p['displayName']
    # Pass 2 --Levenshtein <=1 fallback for length >=4
    if len(target) >= 4:
        def lev(a, b):
            if abs(len(a) - len(b)) > 1:
                return 2
            m, n = len(a), len(b)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            for i in range(m + 1):
                dp[i][0] = i
            for j in range(n + 1):
                dp[0][j] = j
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    dp[i][j] = dp[i - 1][j - 1] if a[i - 1] == b[j - 1] else 1 + min(
                        dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
            return dp[m][n]
        for p in roster:
            cands = [p.get('displayName'), p.get('fullName')] + (p.get('aliases') or [])
            for cand in cands:
                if cand and len(cand) >= 4 and lev(target, norm(cand)) <= 1:
                    return p['displayName']
    return seed_name


# ── Course library extraction (mirrors course_data_qa.py regex) ────────────


def extract_courses() -> dict[str, dict]:
    """Parse COURSE_LIBRARY from index.html. Returns {courseId: {par_sum, si_ok}}."""
    html = INDEX_HTML.read_text(encoding='utf-8')
    block_re = re.compile(
        r'(\w+):\s*\{\s*'
        r'name:\s*[\'"]([^\'"]+)[\'"]'
        r'.*?'
        r'holes:\s*\[([^\]]+)\]',
        re.DOTALL
    )
    hole_re = re.compile(r'\{par:\s*(\d+)\s*,\s*si:\s*(\d+)\s*[,}]')
    out = {}
    for m in block_re.finditer(html):
        key, name, holes_text = m.group(1), m.group(2), m.group(3)
        holes = [(int(p), int(s)) for p, s in hole_re.findall(holes_text)]
        if not holes:
            out[key] = {'name': name, 'holes_count': 0, 'par_sum': 0, 'si_ok': False, 'placeholder': True}
            continue
        pars = [p for p, _ in holes]
        sis = [s for _, s in holes]
        out[key] = {
            'name': name,
            'holes_count': len(holes),
            'par_sum': sum(pars),
            'si_ok': len(holes) == 18 and sorted(sis) == list(range(1, 19)),
            'placeholder': False,
        }
    return out


# ── Check primitives ────────────────────────────────────────────────────────

class Report:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.passes = 0
        self.fails = 0

    def ok(self, msg, detail=''):
        self.passes += 1
        suffix = f' · {detail}' if (detail and self.verbose) else ''
        print(f'  [PASS] {msg}{suffix}')

    def fail(self, msg, detail='', fix=''):
        self.fails += 1
        print(f'  [FAIL] {msg}')
        if detail:
            print(f'         {detail}')
        if fix:
            print(f'         FIX: {fix}')


# ── Individual checks ──────────────────────────────────────────────────────


def check_bundle_exists(rep, event_id):
    bundle = fb_get(f'events/{event_id}/bundle')
    if bundle is None:
        rep.fail(
            f'No bundle found at /events/{event_id}/bundle',
            fix=f'Push the event from admin (chubbs-admin.netlify.app) targeting this event ID.'
        )
        return None
    rep.ok(f'Bundle exists at /events/{event_id}/bundle')
    return bundle


def check_published_metadata(rep, bundle):
    pa = bundle.get('_publishedAt')
    pb = bundle.get('_publishedBy')
    if not pa or not isinstance(pa, (int, float)):
        rep.fail(
            'Bundle has no _publishedAt timestamp',
            detail='Either the admin push never landed, OR a mobile sync overwrote it (pre-v6.3 .set() clobber regression).',
            fix='Re-push from admin. If this is v6.3+ mobile, the issue is admin-side --toggle the playoff section in admin and push again.'
        )
        return
    age_h = (datetime.now(timezone.utc).timestamp() - pa / 1000) / 3600
    iso = datetime.fromtimestamp(pa / 1000, tz=timezone.utc).isoformat(timespec='seconds')
    rep.ok(f'_publishedAt: {iso} ({age_h:.1f}h ago)')
    if pb != 'ChubbsAdmin':
        rep.fail(
            f'_publishedBy is "{pb}" (expected "ChubbsAdmin")',
            detail='Bundle may have been written by a mobile device sync, not an admin push.',
            fix='Re-push from chubbs-admin.netlify.app to overwrite with a proper admin payload.'
        )
        return
    rep.ok(f'_publishedBy: {pb}')


def check_event_block(rep, bundle, expected_event_id):
    ev = bundle.get('event') or {}
    eid = ev.get('eventId')
    if eid != expected_event_id:
        rep.fail(
            f'event.eventId mismatch --bundle says "{eid}", path says "{expected_event_id}"',
            fix='Re-push from admin; the eventId is derived from the form fields and may have drifted.'
        )
    else:
        rep.ok(f'event.eventId matches path: {eid}')
    name = ev.get('displayName') or ev.get('name') or ''
    if not name.strip():
        rep.fail('event has no displayName or name', fix='Set the Event Name / Display Name in admin and re-push.')
    else:
        rep.ok(f'event name: "{name}"')
    sat = ev.get('satDate') or ''
    sun = ev.get('sunDate') or ''
    if not sat and not sun:
        rep.fail('event has no satDate AND no sunDate', fix='Fill date fields in admin and re-push.')
    else:
        rep.ok(f'event dates: sat={sat or "—"}, sun={sun or "—"}')


def check_players(rep, bundle):
    players = bundle.get('players') or []
    if not isinstance(players, list) or len(players) == 0:
        rep.fail('bundle.players is empty', fix='Add players to the admin roster + mark their attendance for this event.')
        return players
    bad = []
    for p in players:
        if not isinstance(p, dict):
            bad.append('non-object entry')
            continue
        if not p.get('playerId'):
            bad.append(f'player missing playerId: {p}')
        if not (p.get('displayName') or p.get('fullName')):
            bad.append(f'player {p.get("playerId")} has no displayName/fullName')
    if bad:
        rep.fail(f'players list has {len(bad)} malformed entries', detail='; '.join(bad[:3]))
    else:
        rep.ok(f'players: {len(players)} (all have playerId + displayName)')
    return players


def check_groups(rep, bundle, players):
    teams = bundle.get('day1ScrambleTeams') or []
    groups = bundle.get('day2Groups') or []
    rep.ok(f'day1ScrambleTeams: {len(teams)} (Saturday)') if teams else rep.fail(
        'day1ScrambleTeams is empty', detail='OK if this is a Stableford-only event; otherwise re-check Section 3 in admin.')
    if not groups:
        rep.fail('day2Groups is empty --no Sunday/main-day groups defined', fix='Fill stableford groups in admin and re-push.')
        return teams, groups
    rep.ok(f'day2Groups: {len(groups)} (Sunday)')

    # All scorers and players must be in the bundle's player roster
    pid_set = {str(p.get('playerId', '')) for p in players if isinstance(p, dict)}
    issues = []
    for g in groups:
        gid = g.get('groupId', '?')
        scorer = str(g.get('scorerPlayerId', '') or '')
        ids = [str(x) for x in (g.get('playerIds') or [])]
        if scorer and scorer not in pid_set:
            issues.append(f'group {gid} scorer "{scorer}" not in players[]')
        if scorer and ids and scorer not in ids:
            issues.append(f'group {gid} scorer "{scorer}" not in its own playerIds[]')
        for pid in ids:
            if pid not in pid_set:
                issues.append(f'group {gid} references unknown playerId "{pid}"')
    for t in teams:
        tid = t.get('teamId', '?')
        scorer = str(t.get('scorerPlayerId', '') or '')
        ids = [str(x) for x in (t.get('playerIds') or [])]
        if scorer and scorer not in pid_set:
            issues.append(f'team {tid} scorer "{scorer}" not in players[]')
        for pid in ids:
            if pid not in pid_set:
                issues.append(f'team {tid} references unknown playerId "{pid}"')

    if issues:
        rep.fail(
            f'{len(issues)} group/team integrity issues',
            detail='; '.join(issues[:5]),
            fix='Inspect the affected groups in admin; usually a player was removed from the roster but left in a lineup.'
        )
    else:
        rep.ok(f'group integrity: all {len(teams)+len(groups)} lineups reference valid playerIds')
    return teams, groups


def check_playoffs(rep, bundle, players):
    po = bundle.get('playoffs')
    if not po or not isinstance(po, dict):
        rep.fail(
            'bundle.playoffs is null or missing',
            detail='Fresh devices loading this event will see Stableford only --no Match-Play banner, no .mp-me highlight.',
            fix='In admin: open Section 6 (Playoff Setup), confirm toggle is ON, verify the seed list shows 16 players, then re-push. The v6.0 hard-guard should block the wrong-state push.'
        )
        return None
    seeds = po.get('seeds') or []
    stage = po.get('stage') or 'r16'
    if not isinstance(seeds, list) or len(seeds) < 16:
        rep.fail(
            f'playoffs.seeds has {len(seeds) if isinstance(seeds, list) else 0} entries (expected 16)',
            fix='Re-push from admin with Section 6 toggle ON and the qualified-player roster fully populated.'
        )
        return po
    rep.ok(f'playoffs: stage={stage}, seeds={len(seeds)}')

    # Canonicalisation check --every seed must resolve to a roster player
    canon_failures = []
    pid_display = {str(p.get('playerId', '')): (p.get('displayName') or p.get('fullName') or '') for p in players}
    display_set = {norm(v) for v in pid_display.values() if v}
    for i, seed_name in enumerate(seeds, 1):
        resolved = canonicalise(seed_name, players)
        if norm(resolved) not in display_set:
            canon_failures.append(f'#{i} "{seed_name}" -> "{resolved}" (not in roster)')
    if canon_failures:
        rep.fail(
            f'{len(canon_failures)} seed(s) failed canonicalisation',
            detail='; '.join(canon_failures[:5]),
            fix='Add the raw seed name as an alias on the matching player in admin masterRoster, or fix season-4.json.'
        )
    else:
        rep.ok(f'canonicalisation: all {len(seeds)} seeds resolve to roster players')

    # Verify seededAt + stage + bookkeeping
    seeded_at = po.get('seededAt') or '—'
    rep.ok(f'playoffs.seededAt: {seeded_at}')

    return po


def check_courses(rep, bundle, courses):
    ev = bundle.get('event') or {}
    course_ids = []
    for k in ('day1CourseId', 'day2CourseId', 'courseId'):
        v = ev.get(k)
        if v and v not in course_ids:
            course_ids.append(v)
    if not course_ids:
        rep.fail('event has no day1CourseId / day2CourseId', fix='Set the course in admin Section 4 and re-push.')
        return
    for cid in course_ids:
        c = courses.get(cid)
        if not c:
            rep.fail(f'event references unknown course "{cid}"',
                     detail='Course must exist in ChubbsMobileApp_v5/index.html COURSE_LIBRARY.',
                     fix='Pick a course that exists in the library, or add the course definition first.')
            continue
        if c.get('placeholder'):
            rep.fail(f'course "{cid}" ({c.get("name")}) is a placeholder with no hole data',
                     fix='Add the hole-by-hole par + SI for this course in COURSE_LIBRARY.')
            continue
        if not c.get('si_ok'):
            rep.fail(f'course "{cid}" ({c.get("name")}) has SI integrity issues',
                     detail='Run python qa/course_data_qa.py for details.',
                     fix='Fix the SI duplicates / missing entries in COURSE_LIBRARY.')
            continue
        rep.ok(f'course "{cid}" ({c.get("name")}): par {c.get("par_sum")}, SI 1-18 OK')


def check_current_event_pointer(rep, event_id):
    ptr = fb_get('chubbs/currentEvent')
    if ptr is None:
        rep.fail(
            '/chubbs/currentEvent is not set',
            detail='Brain-trust phones loaded with the OLD event URL will NOT see the gold "switch event" banner --they stay on whatever event they last loaded.',
            fix='In admin: tick "Mark as current LIVE event" before pushing (v6.1+ feature). Or write {eventId, ts: now} directly to /chubbs/currentEvent.'
        )
        return
    ptr_eid = ptr.get('eventId') if isinstance(ptr, dict) else None
    if ptr_eid == event_id:
        ts = ptr.get('ts')
        age_h = (datetime.now(timezone.utc).timestamp() - ts / 1000) / 3600 if isinstance(ts, (int, float)) else 0
        rep.ok(f'currentEvent pointer matches this event (set {age_h:.1f}h ago)')
    else:
        rep.fail(
            f'currentEvent pointer is "{ptr_eid}", not this event ({event_id})',
            detail='Brain-trust phones will get a banner suggesting they switch to a DIFFERENT event.',
            fix='Re-push from admin with the "Mark as current LIVE event" checkbox ON.'
        )


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    verbose = '--verbose' in sys.argv or '-v' in sys.argv

    if '--list' in sys.argv:
        ids = list_events()
        print(f'Events in Firebase ({len(ids)}):')
        for eid in ids:
            ts = fb_get(f'events/{eid}/bundle/_publishedAt')
            ts_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(timespec='seconds') if isinstance(ts, (int, float)) else '(no publishedAt)'
            print(f'  {eid}    publishedAt={ts_str}')
        return 0

    event_id = args[0] if args else most_recent_event_id()
    if not event_id:
        print('FAIL: no event ID provided and no events found in Firebase.')
        return 1

    print(f'Chubbs pre-flight check -- {event_id}')
    print('=' * (28 + len(event_id)))
    print()

    rep = Report(verbose=verbose)
    courses = extract_courses()

    bundle = check_bundle_exists(rep, event_id)
    if not bundle:
        print()
        print(f'FAIL: {rep.fails} check(s) failed.')
        return 1

    check_published_metadata(rep, bundle)
    check_event_block(rep, bundle, event_id)
    players = check_players(rep, bundle)
    check_groups(rep, bundle, players)
    check_playoffs(rep, bundle, players)
    check_courses(rep, bundle, courses)
    check_current_event_pointer(rep, event_id)

    print()
    if rep.fails:
        print(f'FAIL: {rep.fails} check(s) failed, {rep.passes} passed.')
        print('Fix the items above and re-run before telling the brain trust to load the link.')
        return 1
    print(f'PASS: {rep.passes}/{rep.passes} checks ok. Bundle is ready for the brain trust.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
