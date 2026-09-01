#!/usr/bin/env python3
"""
How much of a rubric score is the judge, and how much is noise?

The paper has no human validation of its judge, which is its largest
stated weakness. This does not fix that -- a model agreeing with itself is
not correctness -- but it bounds the other side: if the same judge, given
the same transcript twice, does not reproduce its own score, then no
rubric-level reading is safe regardless of whether the judge is right.

Run after scripts/judge_consistency.sh.
"""
from __future__ import annotations
import json, os, statistics as st, sys
from pathlib import Path

WS = Path(os.path.expanduser('~/graph_bench_ws'))
M = WS / 'runs/matrix'
SLUG = 'lynx_bench_56'
RUBRICS = ('proactiveness', 'hallucination', 'explanation', 'recovery')


def load(path: Path) -> dict:
    d = json.loads(path.read_text())['testcases']
    out = {}
    for k, v in d.items():
        if v.get('grade') is None:
            continue
        rub = v.get('rubrics') or {}
        out[k] = {'grade': v['grade'],
                  **{r: (rub.get(r) or {}).get('score') for r in RUBRICS}}
    return out


def pearson(xs, ys):
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = (sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys)) ** .5
    return num / den if den else 0.0


def main() -> int:
    any_row = False
    for row in ('m-gpt56', 'm-kimi25'):
        a = M / row / row / 'judgments.json'
        b = M / row / f'{row}-judged-by-{SLUG}' / 'judgments.json'
        if not (a.exists() and b.exists()):
            print(f'{row}: second pass not finished')
            continue
        any_row = True
        A, B = load(a), load(b)
        common = sorted(set(A) & set(B))
        print(f'\n{row}  (n={len(common)} cases judged twice by the same judge)')
        print(f"  {'field':16}{'pass 1':>9}{'pass 2':>9}{'mean |diff|':>13}"
              f"{'r':>7}{'exact':>8}")
        for f in ('grade',) + RUBRICS:
            xs = [A[c][f] for c in common if A[c][f] is not None
                  and B[c][f] is not None]
            ys = [B[c][f] for c in common if A[c][f] is not None
                  and B[c][f] is not None]
            if not xs:
                continue
            d = [abs(x - y) for x, y in zip(xs, ys)]
            exact = sum(1 for x, y in zip(xs, ys) if x == y) / len(xs)
            print(f'  {f:16}{st.mean(xs):9.3f}{st.mean(ys):9.3f}'
                  f'{st.mean(d):13.3f}{pearson(xs, ys):7.2f}{exact:8.1%}')
    if not any_row:
        sys.exit('no completed second pass yet')
    print('\nRead carefully. mean |diff| is PER-CASE. The paper rules on')
    print('CORPUS MEANS, where per-case judge noise averages down by sqrt(n):')
    print('at n=229 a per-case sd of 0.033 contributes 0.0022 to a mean.')
    print('Comparing 0.026 against a 0.022 mean effect mixes the two levels')
    print('and would wrongly suggest the effect sits inside judge noise.')
    print('The per-case noise is also already inside the paired sd the')
    print('t-tests use, so it was never being ignored.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
