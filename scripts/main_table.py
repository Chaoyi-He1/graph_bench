"""Produce the paper's main table from the matrix rows.

Every number here is a claim someone will check, so the table carries the
things a bare mean hides: how many cases each row actually completed, how
a spread compares to the drift between two identical runs, and which
outcomes are saturated and therefore not agent metrics at all.

    uv run --native-tls python scripts/main_table.py RUN_DIR [RUN_DIR ...]

Rows are restricted to the cases every row completed, because a row that
lost three cases to API errors would otherwise be compared on an easier
set than its neighbours. A row still running has no judgments file yet;
it is reported on the outcomes the recorder already knows, so this
doubles as the monitor for a multi-day table.
"""

from __future__ import annotations

import collections
import json
import os
import statistics as st
import sys
from pathlib import Path

# E-variance, corrected: two identical rounds of the frozen configuration
# moved the aggregate grade by this much.
NOISE_GRADE = 0.021
# The same experiment's binary drift: 15% of resolved verdicts flipped
# between identical runs, so a smaller gap says nothing.
NOISE_RESOLVED_PTS = 15.0


def _row(run_dir: str) -> tuple[str, dict, dict]:
    name = os.path.basename(run_dir.rstrip('/'))
    metrics = json.loads(Path(run_dir, 'metrics.json').read_text())['testcases']
    path = Path(run_dir, 'judgments.json')
    judged = json.loads(path.read_text())['testcases'] if path.exists() else {}
    return name, metrics, judged


def _reveals(run_dir: str, cases: list[str]) -> list[int]:
    out = []
    for case in cases:
        path = os.path.join(run_dir, case + '.jsonl')
        if not os.path.exists(path):
            continue  # transcript reaped; a blank beats a wrong number
        out.append(
            sum(
                1
                for line in open(path)
                if (json.loads(line).get('event') or {}).get('forced_reveal')
            )
        )
    return out


def main() -> int:
    runs = sys.argv[1:]
    if not runs:
        print(__doc__)
        return 1
    rows = []
    for run in runs:
        try:
            rows.append((run, *_row(run)))
        except FileNotFoundError:
            print(f'{os.path.basename(run.rstrip("/")):<12} not started')
    if not rows:
        return 1

    common = None
    for _, _, metrics, _ in rows:
        s = set(metrics)
        common = s if common is None else common & s
    common = sorted(common)
    n = len(common)
    judged_all = all(judged for _, _, _, judged in rows)
    print(f'cases completed in every row: {n}')
    if not judged_all:
        print('(a row is still running — grades appear once it is judged)')
    print()
    print(
        f"{'row':<12}{'n':>5}{'grade':>9}{'resolved':>12}{'forced walk':>14}"
        f"{'ran out':>11}{'turns':>7}{'reveals':>9}"
    )
    summary: dict[str, tuple[float | None, float]] = {}
    for run, name, metrics, judged in rows:
        term = collections.Counter(
            metrics[c]['snapshot']['termination_reason'] for c in common
        )
        turns = [metrics[c]['snapshot']['turn_index'] for c in common]
        grades = [judged[c]['grade'] for c in common if c in judged]
        rev = _reveals(run, common)
        grade = st.mean(grades) if grades else None
        resolved_pct = 100 * term['terminal_resolved'] / n
        summary[name] = (grade, resolved_pct)
        print(
            f'{name:<12}{len(metrics):>5}'
            f"{(f'{grade:.4f}' if grade is not None else '—'):>9}"
            f"{term['terminal_resolved']:>7} ({resolved_pct:>3.0f}%)"
            f"{term['forced_walk_to_terminal']:>8} "
            f"({100 * term['forced_walk_to_terminal'] / n:>3.0f}%)"
            f"{term['none']:>6} ({100 * term['none'] / n:>3.0f}%)"
            f'{st.median(turns):>7.0f}'
            f"{(f'{st.mean(rev):.1f}' if rev else '—'):>9}"
        )

    if len(summary) < 2:
        return 0
    print('\nWhat separates the rows, against the noise floor:')
    grades = [g for g, _ in summary.values() if g is not None]
    if len(grades) >= 2:
        spread = max(grades) - min(grades)
        print(
            f'   grade    spread {spread:.4f} = {spread / NOISE_GRADE:.1f}x '
            f'the {NOISE_GRADE} drift between identical runs'
        )
    resolved = [r for _, r in summary.values()]
    rspread = max(resolved) - min(resolved)
    verdict = (
        'reportable' if rspread > NOISE_RESOLVED_PTS else 'INSIDE the noise'
    )
    print(
        f'   resolved spread {rspread:.0f} pts against {NOISE_RESOLVED_PTS:.0f} '
        f'pts of verdict flipping — {verdict}'
    )
    print(
        '\n   Forced reveals and reached-terminal saturate once cases live '
        'their full budget;\n   both are reported as harness health, not as '
        'agent metrics.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
