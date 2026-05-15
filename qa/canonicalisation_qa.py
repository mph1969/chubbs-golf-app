"""
Seed-name canonicalisation regression tests.

Python port of canonicaliseSeedName() in ChubbsMobileApp_v5/index.html.
Mirrors the JS function exactly — when either side changes, mirror the
change here. Otherwise mobile and tests drift apart silently.

Why this matters: season-4.json uses bare names ("Jack", "John", "Matt D"),
but the admin canonical roster uses displayNames ("JACK S", "John B",
"MATT"). Every downstream match-play seed lookup in mobile relies on the
canonicalisation correctly resolving across that gap. Brain-trust testing
on 2026-05-15 surfaced this — three matches (M1, M6, M7) silently failed
to render banners until v5.110 added punctuation-stripping + Levenshtein
fallback. These tests guard that fix from regression.

Run from repo root:
    python qa/canonicalisation_qa.py
    python qa/canonicalisation_qa.py --verbose
"""
from __future__ import annotations

import re
import sys

# ── Python port of canonicaliseSeedName ─────────────────────────────────────


def _norm(s: str) -> str:
    """Mirror JS: trim → uppercase → strip punctuation → collapse whitespace."""
    if s is None:
        return ''
    out = str(s).strip().upper()
    out = re.sub(r"[.,'\"`]", '', out)
    out = re.sub(r'\s+', ' ', out)
    return out


def _levenshtein(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 1:
        return 2  # we only care about <=1
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def canonicalise_seed_name(seed_name, roster):
    """Returns canonical displayName for seed_name if matched in roster,
    else returns seed_name unchanged. Roster entries are dicts with
    displayName / fullName / aliases keys (matching the mobile bundle shape).
    """
    target = _norm(seed_name)
    if not target or not roster:
        return seed_name

    # Pass 1 — exact match on normalised name/alias.
    for p in roster:
        if not p:
            continue
        if _norm(p.get('displayName')) == target:
            return p['displayName']
        if _norm(p.get('fullName')) == target:
            return p['displayName']
        for alias in (p.get('aliases') or []):
            if _norm(alias) == target:
                return p['displayName']

    # Pass 2 — Levenshtein <=1 fuzzy fallback. >=4 char gate to avoid
    # false positives on short names ("Tim" vs "Tom" shouldn't collapse).
    if len(target) >= 4:
        for p in roster:
            if not p:
                continue
            cands = [p.get('displayName'), p.get('fullName')] + (p.get('aliases') or [])
            for cand in cands:
                if cand and len(cand) >= 4 and _levenshtein(target, _norm(cand)) <= 1:
                    return p['displayName']

    return seed_name


# ── Fixture: minimal roster matching the May Chubbs config ─────────────────

ROSTER = [
    {'playerId': 'HANSON',  'displayName': 'HANSON',  'aliases': ['Handon', 'Mike H']},
    {'playerId': 'JACKS',   'displayName': 'JACK S',  'aliases': ['Jack', 'Jack S.']},
    {'playerId': 'JOHNB',   'displayName': 'John B',  'aliases': ['John', 'John B.']},
    {'playerId': 'MATT',    'displayName': 'MATT',    'aliases': ['Matt D.']},
    {'playerId': 'MATTHEW', 'displayName': 'MATTHEW', 'aliases': ['Other Matt', 'Mathew', 'Matthew SA']},
    {'playerId': 'RYANN',   'displayName': 'RYAN N',  'aliases': ['Ryan', 'Ryan N.']},
    {'playerId': 'LEIGH',   'displayName': 'Leigh',   'aliases': []},
    {'playerId': 'GRAEME',  'displayName': 'GRAEME',  'aliases': ['Greame']},
    {'playerId': 'STUART',  'displayName': 'STUART',  'aliases': ['Stuartom']},
    {'playerId': 'PENGLEI', 'displayName': 'PENGLEI', 'aliases': ['Peng Lei', 'PLZ']},
]

# ── Test cases ──────────────────────────────────────────────────────────────


CASES = [
    # (label, raw_input, expected_canonical)
    # --- Exact displayName match (case-insensitive) ---
    ('exact-displayName-uppercase',   'HANSON',  'HANSON'),
    ('exact-displayName-mixed-case',  'hanson',  'HANSON'),
    ('exact-displayName-titlecase',   'Leigh',   'Leigh'),
    ('exact-displayName-mixed',       'leigh',   'Leigh'),

    # --- Alias match (the v5.109 fix) ---
    ('alias-jack-shortform',          'Jack',    'JACK S'),
    ('alias-john-shortform',          'John',    'John B'),
    ('alias-handon-typo',             'Handon',  'HANSON'),
    ('alias-greame-typo',             'Greame',  'GRAEME'),
    ('alias-stuartom-variant',        'Stuartom', 'STUART'),
    ('alias-mike-h-legacy',           'Mike H',  'HANSON'),

    # --- Punctuation handling (the v5.110 fix) ---
    # season-4.json has "Matt D" (no period). Roster has alias "Matt D." (with).
    # Pre-v5.110 this failed equality. Now strips trailing punctuation.
    ('punctuation-matt-d-no-period',  'Matt D',  'MATT'),
    ('punctuation-matt-d-trailing',   'Matt D.', 'MATT'),
    ('punctuation-jack-s-period',     'Jack S.', 'JACK S'),
    ('punctuation-ryan-n-period',     'Ryan N.', 'RYAN N'),
    ('punctuation-peng-lei-space',    'Peng Lei', 'PENGLEI'),

    # --- Multi-alias entries (Matthew has 3) ---
    ('multi-alias-other-matt',        'Other Matt', 'MATTHEW'),
    ('multi-alias-mathew-misspell',   'Mathew',     'MATTHEW'),
    ('multi-alias-matthew-sa',        'Matthew SA', 'MATTHEW'),

    # --- Levenshtein fuzzy fallback (single-char typo, name >=4 chars) ---
    ('lev-hansson-typo',              'Hansson',  'HANSON'),    # 1 insertion -> match
    ('lev-hansen-typo',               'Hansen',   'HANSON'),    # 1 substitution -> match
    # KNOWN TRADEOFF: threshold-1 Levenshtein produces false positives for
    # any name 1 edit from a roster name. "Ranson" collapses to "HANSON"
    # (R->H substitution). Acceptable risk for Chubbs because seed names
    # come from the curated season-4.json, not arbitrary user input. If the
    # roster ever contains two real names within edit distance 1, the test
    # below will fail and we re-evaluate (raise threshold to 5+ chars, drop
    # Levenshtein entirely, or whitelist).
    ('lev-ranson-false-positive',     'Ranson',   'HANSON'),

    # --- Non-roster names pass through unchanged ---
    ('passthrough-totally-unknown',   'Beyonce',  'Beyonce'),
    ('passthrough-empty-string',      '',         ''),

    # --- Short names should NOT use Levenshtein (avoid false positives) ---
    # "Tim" and "Tom" both pass Levenshtein but neither is in roster.
    # Verify they pass through unchanged.
    ('short-name-no-fuzzy-tim',       'Tim',      'Tim'),
    ('short-name-no-fuzzy-tom',       'Tom',      'Tom'),
]


def run_tests(verbose: bool = False) -> tuple[int, int]:
    passed = 0
    failed = 0
    for label, raw, expected in CASES:
        actual = canonicalise_seed_name(raw, ROSTER)
        ok = actual == expected
        if ok:
            passed += 1
            if verbose:
                print(f'  PASS  {label:35s} {raw!r:25s} -> {actual!r}')
        else:
            failed += 1
            print(f'  FAIL  {label:35s} {raw!r:25s} -> got {actual!r}, expected {expected!r}')
    return passed, failed


def main() -> int:
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    print(f'Running {len(CASES)} canonicalisation cases\n')
    passed, failed = run_tests(verbose=verbose)
    print(f'\n{passed} passed, {failed} failed')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
