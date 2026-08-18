"""What does grounding the judge in the graph actually buy?

The structured grade averages five components: four LLM rubrics and
`info_grounded_rate`, the one term the graph supplies — the share of an
agent's solution calls that were made with the required information
actually in hand. Drop it and you have the *plain* judge: a transcript
read by a model with no answer key, which is what an execution-free
benchmark looks like without the annotation layer.

Both are recoverable from any judged run, because every component is
stored in `grade_components`. So this ablation needs no new runs — it
re-scores what is already on disk.

    uv run --native-tls python scripts/judge_ablation.py RUN_DIR [...]

Reported per run: the two grades, their rank correlation, and — the
question that matters — how far each separates the models it is meant to
separate, in units of the noise floor. A judge that cannot tell two
models apart by more than one identical rerun moves them is not
measuring anything.
"""

from __future__ import annotations

import json
import os
import statistics as st
import sys
from pathlib import Path

# E-variance, corrected: two identical rounds of the frozen configuration
# moved the aggregate grade by this much.
NOISE_FLOOR = 0.021

RUBRIC_KEYS = ('proactiveness', 'non_hallucination', 'explanation', 'recovery')


def _spearman(xs: list[float], ys: list[float]) -> float:
    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while (
                j + 1 < len(order)
                and values[order[j + 1]] == values[order[i]]
            ):
                j += 1
            shared = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = shared
            i = j + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    ) ** 0.5
    return num / den if den else 0.0


def grades(run_dir: str) -> dict[str, tuple[float, float]]:
    """case -> (structured grade, plain grade)."""
    data = json.loads(Path(run_dir, 'judgments.json').read_text())['testcases']
    out: dict[str, tuple[float, float]] = {}
    for case, judgment in data.items():
        comp = judgment.get('grade_components') or {}
        if not all(k in comp for k in RUBRIC_KEYS):
            continue  # abstained case: no rubric scores to average
        plain = st.mean(float(comp[k]) for k in RUBRIC_KEYS)
        out[case] = (float(judgment['grade']), plain)
    return out


def main() -> int:
    runs = sys.argv[1:]
    if not runs:
        print(__doc__)
        return 1
    table = []
    for run in runs:
        g = grades(run)
        if not g:
            continue
        name = os.path.basename(run.rstrip('/'))
        s = [v[0] for v in g.values()]
        p = [v[1] for v in g.values()]
        table.append((name, st.mean(s), st.mean(p), _spearman(s, p), len(g)))
    print(
        f"{'run':<18}{'n':>5}{'structured':>12}{'plain':>10}{'rho':>8}"
    )
    for name, s, p, rho, n in table:
        print(f'{name:<18}{n:>5}{s:>12.4f}{p:>10.4f}{rho:>8.3f}')
    if len(table) < 2:
        return 0
    # Separation is the point. A judge is useful here only if the gap it
    # reports between models is large next to the drift between two
    # identical runs of one model.
    print(f'\nseparation between the extreme runs (noise floor {NOISE_FLOOR}):')
    for label, idx in (('structured', 1), ('plain', 2)):
        values = [row[idx] for row in table]
        spread = max(values) - min(values)
        print(
            f'   {label:<11} spread={spread:.4f}  '
            f'= {spread / NOISE_FLOOR:.1f}x the noise floor'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
