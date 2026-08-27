#!/usr/bin/env python3
"""
The full-corpus leak ablation, ready to run the moment e-leak-full judges.

The n=48 version of this comparison gave +0.037 against a 99% detection
bound of 0.054 -- the paper's weakest row, and the one a reviewer will
press hardest, since the benchmark's stated motivation is that
transcript-conditioned simulation contaminates the dialogue. At n=229 the
bound falls to about 0.025, so the same effect would clear. This prints
the answer either way, including the case where it does not clear, which
is a real outcome and not a failure to report.
"""
from __future__ import annotations
import json, statistics as st, sys
from math import comb, sqrt
from pathlib import Path

BASE = Path('/tmp/gb-v6/runs/matrix/m-gpt56/m-gpt56')          # leak_profile C
LEAK = Path('/tmp/gb-v6/runs/matrix/e-leak-full/e-leak-full')  # leak_profile A

def grades(d: Path) -> dict[str, float]:
    p = d / 'judgments.json'
    if not p.exists():
        sys.exit(f'not judged yet: {p}')
    b = json.loads(p.read_text())
    prof = b.get('rubric_profile', 'default')
    return {k: v['grade'] for k, v in b['testcases'].items()
            if v.get('grade') is not None}, prof

def sign_p(d: list[float]) -> float:
    pos = sum(1 for x in d if x > 0); neg = sum(1 for x in d if x < 0)
    n = pos + neg
    if n == 0: return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

def main() -> int:
    (gb, pb), (gl, pl) = grades(BASE), grades(LEAK)
    if pb != pl:
        sys.exit(f'rubric profiles differ ({pb} vs {pl}) — not comparable')
    common = sorted(set(gb) & set(gl))
    d = [gl[c] - gb[c] for c in common]          # leaked minus clean
    n = len(d)
    m, sd = st.mean(d), st.stdev(d)
    t = m / (sd / sqrt(n))
    bound = 2.6 * sd / sqrt(n)
    p = sign_p(d)
    real = abs(t) > 2.6 and p < 0.01
    print(f'profile          {pb}')
    print(f'paired cases     {n}  (clean n={len(gb)}, leaked n={len(gl)})')
    print(f'clean mean       {st.mean([gb[c] for c in common]):.4f}')
    print(f'leaked mean      {st.mean([gl[c] for c in common]):.4f}')
    print(f'difference       {m:+.4f}   t={t:.2f}   sign p={p:.3g}')
    print(f'99% bound        {bound:.4f}')
    print(f'RULING           {"REAL — leak inflates the grade" if real else f"not called (|effect| < {bound:.3f})"}')
    if not real:
        print('  Report as a bound, not an absence. Leak-safety still rests')
        print('  on leaked turns being directly detected by the screen.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
