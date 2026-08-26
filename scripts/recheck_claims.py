"""Re-derive the run-to-run drift, then re-test every claim that leaned on it.

Every "reportable / not reportable" ruling in docs/experiments.md was a
comparison measured in noise floors. Two things were wrong with that.

The floor came from two identical runs judged *before* the judge's
truncation defect was found, so a corrupt denominator was silently
re-deciding which findings a paper may state. And one pair is not a floor:
three arms the agent cannot tell apart drift by 0.0091, 0.0184 and 0.0260
against each other — a factor of three — so any single estimate carries
error the comparison then inherits.

For paired per-case data a test is available, costs nothing, and does not
inherit that error. The ruling now comes from the test; the drift is
reported as context.

    uv run --native-tls python scripts/recheck_claims.py

Exit 1 if any ruling changed against the record, 2 if the inputs are not
clean enough to rule on.
"""

from __future__ import annotations

import itertools
import json
import statistics as st
from math import comb
from pathlib import Path

M = '/tmp/gb-v6/runs/matrix'
ALPHA = 0.01
T_CRIT = 2.6

# Arms identical from the agent's side: the reference, one that passed a
# simulator flag as an agent key (the adapter ignores unknown keys), and one
# that switched off images a non-multimodal agent never read.
IDENTICAL = {
    'fix6': f'{M}/gpt56-fix6/gpt56-fix6',
    'vision': f'{M}/gpt56-vision/gpt56-vision',
    'noimg': f'{M}/gpt56-noimg/gpt56-noimg',
}

CLAIMS = [
    ('E5   gpt-5.6 vs Kimi-2.5', f'{M}/m-kimi25/m-kimi25', f'{M}/m-gpt56/m-gpt56', 'reportable'),
    ('E5   gpt-5.6 vs GLM-5.1', f'{M}/m-glm51/m-glm51', f'{M}/m-gpt56/m-gpt56', 'reportable'),
    ('E5   gpt-5.6 vs gpt-5.5 (within tier)', f'{M}/m-gpt55/m-gpt55', f'{M}/m-gpt56/m-gpt56', 'reportable'),
    ('E5   GLM-5.1 vs Kimi-2.5 (within tier)', f'{M}/m-kimi25/m-kimi25', f'{M}/m-glm51/m-glm51', 'NOT reportable'),
    ('E1   leakage inflation, profile A vs C', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-leakA/gpt56-leakA', 'NOT reportable'),
    ('E7   no-images ablation', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-noimg/gpt56-noimg', 'NOT reportable'),
    ('E-tb turn budget 20 vs 30', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/gpt56-t30/gpt56-t30', 'NOT reportable'),
    ('E8   simulator swap', f'{M}/gpt56-fix6/gpt56-fix6', f'{M}/e8-simswap/e8-simswap', 'NOT reportable'),
    ('E-f  fairness, 50-case arms', f'{M}/kimi25-fix6/kimi25-fix6', f'{M}/gpt56-fix6/gpt56-fix6', 'reportable'),
]


def _grades(run: str) -> dict[str, float]:
    path = Path(run, 'judgments.json')
    if not path.exists():
        return {}
    data = json.loads(path.read_text())['testcases']
    return {c: v['grade'] for c, v in data.items() if v.get('grade') is not None}


def _parse_errors(run: str) -> int:
    path = Path(run, 'judgments.json')
    if not path.exists():
        return -1
    data = json.loads(path.read_text())['testcases']
    return sum(
        1
        for v in data.values()
        for rv in (v.get('rubrics') or {}).values()
        if rv.get('label') == 'parse_error'
    )


def _paired(a: str, b: str) -> list[float]:
    ga, gb = _grades(a), _grades(b)
    return [gb[c] - ga[c] for c in sorted(set(ga) & set(gb))]


def _t(deltas: list[float]) -> float:
    if len(deltas) < 2:
        return 0.0
    sd = st.stdev(deltas)
    return st.mean(deltas) / (sd / len(deltas) ** 0.5) if sd else float('inf')


def _sign_p(deltas: list[float]) -> float:
    """
    Two-sided sign test. Grades are bounded and lumpy, so a test counting
    direction rather than assuming normality is the safer of the two; where
    it disagrees with t, the disagreement is itself the finding.
    """
    up = sum(1 for d in deltas if d > 0)
    down = sum(1 for d in deltas if d < 0)
    n = up + down
    if n == 0:
        return 1.0
    k = min(up, down)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def main() -> int:
    dirty = {r: _parse_errors(r) for r in IDENTICAL.values()}
    if any(v > 0 for v in dirty.values()):
        for run, n in dirty.items():
            if n > 0:
                print(f'REFUSING: {Path(run).name} still has {n} parse errors')
        return 2

    drifts = []
    for x, y in itertools.combinations(IDENTICAL, 2):
        d = _paired(IDENTICAL[x], IDENTICAL[y])
        if d:
            drifts.append(abs(st.mean(d)))
    floor = max(drifts) if drifts else 0.0
    print(
        f'identical-run drift over {len(drifts)} pairs: '
        + ', '.join(f'{d:.4f}' for d in sorted(drifts))
        + f'   (widest {floor:.4f})'
    )
    print(f'ruling = paired t > {T_CRIT} AND sign test p < {ALPHA}\n')

    head = f"{'claim':<40}{'n':>4}{'delta':>9}{'drifts':>8}{'t':>8}{'sign p':>9}  verdict"
    print(head)
    changed = []
    for label, lo, hi, recorded in CLAIMS:
        deltas = _paired(lo, hi)
        if not deltas:
            print(f'{label:<40}{"—":>4}{"—":>9}{"—":>8}{"—":>8}{"—":>9}  not run yet')
            continue
        mean = st.mean(deltas)
        mult = abs(mean) / floor if floor else float('inf')
        t = _t(deltas)
        p = _sign_p(deltas)
        verdict = (
            'reportable' if abs(t) > T_CRIT and p < ALPHA else 'NOT reportable'
        )
        mark = '' if verdict == recorded else '   <-- CHANGED'
        if mark:
            changed.append((label, recorded, verdict))
        print(
            f'{label:<40}{len(deltas):>4}{mean:>+9.4f}{mult:>7.1f}x'
            f'{t:>8.1f}{p:>9.4f}  {verdict}{mark}'
        )

    print()
    if changed:
        print(f'{len(changed)} ruling(s) changed against the record:')
        for label, was, now in changed:
            print(f'   {label}: was {was}, now {now}')
        return 1
    print('every recorded ruling survives.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
