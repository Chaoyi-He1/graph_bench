#!/usr/bin/env python3
"""
Judge-vs-human agreement from the filled score sheets.

Reports what CAB reports so the two are comparable: inter-annotator
Cohen's kappa (quadratic-weighted, since the scale is ordinal), and the
judge's agreement with the human consensus expressed as a fraction of the
inter-human baseline. Also mean |judge - human| in grade units, so the
number can be read against the effects the paper rules on.

Usage:
    python scripts/human_validation_analyze.py --dir ~/graph_bench_human
"""
from __future__ import annotations
import argparse, csv, json, os, statistics as st
from pathlib import Path

RUBRICS = ('proactiveness', 'hallucination', 'explanation', 'recovery')
LEVELS = [0.0, 0.25, 0.5, 0.75, 1.0]


def snap(x: float) -> float:
    return min(LEVELS, key=lambda l: abs(l - x))


def weighted_kappa(a: list[float], b: list[float]) -> float:
    """Quadratic-weighted Cohen's kappa on the 5-level scale."""
    k = len(LEVELS); idx = {l: i for i, l in enumerate(LEVELS)}
    n = len(a)
    O = [[0] * k for _ in range(k)]
    for x, y in zip(a, b):
        O[idx[snap(x)]][idx[snap(y)]] += 1
    ra = [sum(O[i][j] for j in range(k)) for i in range(k)]
    rb = [sum(O[i][j] for i in range(k)) for j in range(k)]
    w = [[((i - j) ** 2) / ((k - 1) ** 2) for j in range(k)] for i in range(k)]
    num = sum(w[i][j] * O[i][j] for i in range(k) for j in range(k))
    den = sum(w[i][j] * ra[i] * rb[j] / n for i in range(k) for j in range(k))
    return 1 - num / den if den else 1.0


def read_scores(p: Path) -> dict[str, dict[str, float]]:
    out = {}
    with open(p) as f:
        for row in csv.DictReader(f):
            vals = {r: row[r].strip() for r in RUBRICS}
            if all(vals.values()):
                out[row['sheet']] = {r: float(vals[r]) for r in RUBRICS}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', required=True)
    d = Path(os.path.expanduser(ap.parse_args().dir))
    key = json.loads((d / 'KEY.json').read_text())
    A, B = read_scores(d / 'scores_A.csv'), read_scores(d / 'scores_B.csv')
    both = sorted(set(A) & set(B) & set(key))
    if len(both) < 10:
        raise SystemExit(f'only {len(both)} sheets scored by both annotators; need more')
    print(f'{len(both)} sheets scored by both annotators\n')
    print(f"{'rubric':15}{'human-human κ':>15}{'judge-human κ':>15}{'% of baseline':>15}{'mean |Δ|':>10}")
    agg = {'hh': [], 'jh': []}
    for r in RUBRICS:
        ha = [A[s][r] for s in both]; hb = [B[s][r] for s in both]
        consensus = [(x + y) / 2 for x, y in zip(ha, hb)]
        judge = [key[s]['judge'][r] for s in both]
        if any(v is None for v in judge):
            print(f'{r:15}  judge scores missing for some sheets'); continue
        k_hh = weighted_kappa(ha, hb)
        k_jh = weighted_kappa(judge, consensus)
        pct = 100 * k_jh / k_hh if k_hh > 0 else float('nan')
        mad = st.mean(abs(j - c) for j, c in zip(judge, consensus))
        agg['hh'].append(k_hh); agg['jh'].append(k_jh)
        print(f'{r:15}{k_hh:15.2f}{k_jh:15.2f}{pct:15.1f}%{mad:10.3f}')
    if agg['hh']:
        hh, jh = st.mean(agg['hh']), st.mean(agg['jh'])
        print(f"\n{'average':15}{hh:15.2f}{jh:15.2f}{100*jh/hh if hh else float('nan'):15.1f}%")
        print('\nCAB, for comparison: inter-human κ = 0.68; judge at 84.2% of the human baseline.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
