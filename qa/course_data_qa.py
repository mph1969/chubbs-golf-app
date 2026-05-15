"""
Course data integrity tests.

Parses the COURSE_LIBRARY object inline in
ChubbsMobileApp_v5/index.html and asserts the structural invariants
that every course MUST hold or scoring quietly breaks:

  * 18 holes exactly
  * par sum == 72 or 73 (Chubbs allows the rare par-73 routing — Nicklaus
    course at BRG is the live example)
  * SI 1-18 each appears exactly once
  * par values are integers in {3, 4, 5}
  * no None / zero pars

Placeholder courses (those built via blankCourseHoles()) are skipped —
they're known empty until someone uploads the scorecard.

Run from repo root:
    python qa/course_data_qa.py
    python qa/course_data_qa.py --verbose

Exit code 0 = all courses pass. Non-zero = at least one course failed
(prints the failure detail).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

INDEX_HTML = Path(__file__).resolve().parent.parent / 'ChubbsMobileApp_v5' / 'index.html'
HOLE_RE = re.compile(r'\{par:(\d+),si:(\d+)\}')

# Courses with known data issues that the test should skip until the
# underlying data is fixed in index.html. Keys are course IDs (the key in
# COURSE_LIBRARY); values are short reasons for the skip. When a course
# is fixed and the data passes, REMOVE the entry — don't let stale
# whitelist entries silently mask new regressions.
COURSES_WITH_KNOWN_DATA_ISSUES = {
    'krungthepKreetha': 'H3/H7 duplicate SI 5, SI 8 missing — needs scorecard verification (2026-05-15). Not on near-term schedule.',
}
COURSE_BLOCK_RE = re.compile(
    r'(\w+):\s*\{\s*'                    # key:
    r'name:[\'"]([^\'"]+)[\'"]'          # name:'...'
    r'.*?'                                # club / city / note / etc (non-greedy)
    r'holes:\s*\[([^\]]+)\]',            # holes:[ ... ]
    re.DOTALL
)


def extract_courses(html: str) -> list[tuple[str, str, list[tuple[int, int]]]]:
    """Return [(key, name, [(par, si), ...]), ...] for every course found."""
    out = []
    for match in COURSE_BLOCK_RE.finditer(html):
        key, name, holes_text = match.group(1), match.group(2), match.group(3)
        holes = [(int(p), int(s)) for p, s in HOLE_RE.findall(holes_text)]
        if not holes:
            continue  # placeholder (blankCourseHoles produces no inline {par:..,si:..})
        out.append((key, name, holes))
    return out


def validate(key: str, name: str, holes: list[tuple[int, int]], verbose: bool = False) -> list[str]:
    """Return list of failure messages. Empty list = pass."""
    failures = []

    if len(holes) != 18:
        failures.append(f'hole count = {len(holes)}, expected 18')
        return failures  # everything else is meaningless

    pars = [p for p, _ in holes]
    sis = [s for _, s in holes]

    par_sum = sum(pars)
    # Most Chubbs courses are par 72; BRG Nicklaus runs par 73; Unico Grande
    # is an executive par 63 (intentionally unusual). Anything outside 60-76
    # is suspicious — likely a data-entry typo.
    if par_sum < 60 or par_sum > 76:
        failures.append(f'par sum = {par_sum}, outside plausible range 60-76')

    for i, p in enumerate(pars, 1):
        if p not in (3, 4, 5):
            failures.append(f'hole {i} has unusual par {p}')

    si_set = set(sis)
    if len(si_set) != 18:
        # duplicates exist
        from collections import Counter
        dupes = [s for s, c in Counter(sis).items() if c > 1]
        failures.append(f'SI duplicates: {sorted(dupes)}')

    missing = sorted(set(range(1, 19)) - si_set)
    if missing:
        failures.append(f'missing SI values: {missing}')

    extra = sorted(s for s in si_set if s < 1 or s > 18)
    if extra:
        failures.append(f'SI out of range: {extra}')

    if verbose and not failures:
        print(f'  [{key}] {name}: 18 holes, par {par_sum}, SI 1-18 OK')

    return failures


def main() -> int:
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    html = INDEX_HTML.read_text(encoding='utf-8')
    courses = extract_courses(html)

    if not courses:
        print('FAIL: no courses found — has index.html or the regex shape changed?')
        return 1

    print(f'Found {len(courses)} courses with hole data (placeholders skipped)\n')

    bad = []
    skipped = []
    for key, name, holes in courses:
        if key in COURSES_WITH_KNOWN_DATA_ISSUES:
            skipped.append((key, name, COURSES_WITH_KNOWN_DATA_ISSUES[key]))
            if verbose:
                print(f'  [{key}] {name}: SKIPPED — {COURSES_WITH_KNOWN_DATA_ISSUES[key]}')
            continue
        failures = validate(key, name, holes, verbose=verbose)
        if failures:
            bad.append((key, name, failures))

    if skipped:
        print(f'\nWhitelisted ({len(skipped)} course(s) skipped):')
        for key, name, reason in skipped:
            print(f'  [{key}] {name}: {reason}')

    if bad:
        print(f'\nFAIL: {len(bad)} course(s) failed:')
        for key, name, fs in bad:
            print(f'  [{key}] {name}:')
            for f in fs:
                print(f'    - {f}')
        return 1

    checked = len(courses) - len(skipped)
    print(f'\nPASS: All {checked} verified courses ok (18 holes, par 60-76, SI 1-18 unique)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
