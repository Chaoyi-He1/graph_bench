"""E4: noise floor between two identical runs over the frozen corpus.

Reports, for the cases present in both rounds: aggregate drift, per-case
grade drift, and how often the binary outcomes (resolved / reached
terminal) flip. Any cross-model claim in the paper has to clear these
numbers.

Usage: uv run --native-tls python scripts/variance_report.py RUN_A RUN_B
"""

from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path


def load(run_dir: Path) -> tuple[dict, dict]:
    metrics = json.loads((run_dir / 'metrics.json').read_text())['testcases']
    jpath = run_dir / 'judgments.json'
    judged = (
        json.loads(jpath.read_text())['testcases'] if jpath.exists() else {}
    )
    return metrics, judged


def main() -> None:
    a_dir, b_dir = Path(sys.argv[1]), Path(sys.argv[2])
    ma, ja = load(a_dir)
    mb, jb = load(b_dir)
    common = sorted(set(ma) & set(mb))
    print(f'cases in both rounds: {len(common)}  (A={len(ma)} B={len(mb)})')

    def agg(m: dict, j: dict, keys: list[str]) -> dict:
        res = sum(
            1
            for k in keys
            if m[k]['metrics']['final_user_satisfaction'] == 'resolved'
        )
        term = sum(1 for k in keys if m[k]['metrics']['reached_terminal'])
        grades = [j[k]['grade'] for k in keys if k in j]
        return {
            'resolved': res,
            'terminal': term,
            'mean_grade': st.mean(grades) if grades else None,
            'n_graded': len(grades),
        }

    A, B = agg(ma, ja, common), agg(mb, jb, common)
    print(f'\n{"metric":22s} {"round A":>10s} {"round B":>10s} {"drift":>10s}')
    for k in ('resolved', 'terminal'):
        d = B[k] - A[k]
        print(
            f'{k:22s} {A[k]:>10d} {B[k]:>10d} {d:>+10d}'
            f'  ({100 * A[k] / len(common):.1f}% -> {100 * B[k] / len(common):.1f}%)'
        )
    if A['mean_grade'] and B['mean_grade']:
        print(
            f'{"mean grade":22s} {A["mean_grade"]:>10.4f} '
            f'{B["mean_grade"]:>10.4f} {B["mean_grade"] - A["mean_grade"]:>+10.4f}'
        )

    # per-case instability
    flip_res = [
        k
        for k in common
        if (ma[k]['metrics']['final_user_satisfaction'] == 'resolved')
        != (mb[k]['metrics']['final_user_satisfaction'] == 'resolved')
    ]
    flip_term = [
        k
        for k in common
        if ma[k]['metrics']['reached_terminal']
        != mb[k]['metrics']['reached_terminal']
    ]
    both = [k for k in common if k in ja and k in jb]
    deltas = [abs(jb[k]['grade'] - ja[k]['grade']) for k in both]
    print(
        f'\nper-case outcome flips: resolved {len(flip_res)}/{len(common)} '
        f'({100 * len(flip_res) / len(common):.1f}%), '
        f'terminal {len(flip_term)}/{len(common)} '
        f'({100 * len(flip_term) / len(common):.1f}%)'
    )
    if deltas:
        print(
            f'per-case |grade delta|: mean {st.mean(deltas):.3f} '
            f'median {st.median(deltas):.3f} p90 '
            f'{sorted(deltas)[int(0.9 * len(deltas))]:.3f} max {max(deltas):.3f}'
        )
        stable = sum(1 for d in deltas if d <= 0.05)
        print(
            f'cases with |delta| <= 0.05: {stable}/{len(deltas)} '
            f'({100 * stable / len(deltas):.0f}%)'
        )
    json.dump(
        {
            'n_common': len(common),
            'A': A,
            'B': B,
            'flip_resolved': len(flip_res),
            'flip_terminal': len(flip_term),
            'grade_delta_mean': st.mean(deltas) if deltas else None,
            'grade_delta_p90': sorted(deltas)[int(0.9 * len(deltas))]
            if deltas
            else None,
        },
        open('runs/variance_summary.json', 'w'),
        indent=1,
    )
    print('\nwrote runs/variance_summary.json')


if __name__ == '__main__':
    main()
