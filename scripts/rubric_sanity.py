"""Does a rubric agree with a measurement that does not involve a judge?

A rubric can drift without anyone noticing, because there is nothing to
check it against — except where the harness already counts something
related. This compares each LLM rubric with a behavioural count taken
straight from the transcripts, so a rubric that stops describing the
behaviour it is named after shows up as a disagreement rather than as a
number nobody questions.

    uv run --native-tls python scripts/rubric_sanity.py

The pairing that motivated it: `proactiveness` against how often an agent
proposes a fix from a state whose graph offers no solution edge — that
is, before the evidence chain is complete. Under the first rubric wording
every model scored 0.92–0.97 while their premature-proposal rates
differed by 1.7x, and the summary "asking is solved" came from the rubric
rather than from the conversations. The corrected wording tracks the
count.

A rubric is not automatically wrong when it disagrees. But the
disagreement has to be explained before either number is quoted.
"""

from __future__ import annotations

import glob
import json
import os
import statistics as st
from pathlib import Path

M = '/tmp/gb-v6/runs/matrix'
CORPUS = '/tmp/gb-v6/data/released/graphs'
ROWS = ['m-gpt56', 'm-gpt55', 'm-glm51', 'm-kimi25']


def _graphs() -> dict:
    return {
        os.path.basename(p)[:-5]: json.loads(Path(p).read_text())['graph']
        for p in glob.glob(os.path.join(CORPUS, '*.json'))
    }


def premature_rate(run: str, graphs: dict) -> float | None:
    """Proposals per case made from a state offering no solution edge."""
    total = cases = 0
    for path in glob.glob(os.path.join(run, '*.jsonl')):
        case = os.path.basename(path)[:-6]
        graph = graphs.get(case)
        if graph is None:
            continue
        cases += 1
        offers = {
            e['from']
            for e in graph['edges']
            if e['edge_type'] in ('solution_only', 'mixed')
        }
        for line in open(path):
            event = json.loads(line).get('event') or {}
            match = event.get('match') or {}
            if (
                match.get('type') == 'none'
                and match.get('edge_type') == 'solution_only'
                and event.get('node_before') not in offers
            ):
                total += 1
    return total / cases if cases else None


def rubric_mean(run: str, rubric: str) -> float | None:
    path = Path(run, 'judgments.json')
    if not path.exists():
        return None
    data = json.loads(path.read_text())['testcases']
    vals = [
        (v.get('rubrics') or {}).get(rubric, {}).get('score')
        for v in data.values()
    ]
    vals = [v for v in vals if v is not None]
    return st.mean(vals) if vals else None


def _spearman(xs: list[float], ys: list[float]) -> float:
    def rank(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        for pos, i in enumerate(order):
            out[i] = pos + 1
        return out

    rx, ry = rank(xs), rank(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (
        sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)
    ) ** 0.5
    return num / den if den else 0.0


def main() -> int:
    graphs = _graphs()
    rows, prem, proa = [], [], []
    for row in ROWS:
        run = f'{M}/{row}/{row}'
        p = premature_rate(run, graphs)
        q = rubric_mean(run, 'proactiveness')
        if p is None or q is None:
            continue
        rows.append(row)
        prem.append(p)
        proa.append(q)

    print('proactiveness against premature proposals per case')
    print(f"{'row':<12}{'premature/case':>16}{'proactiveness':>15}")
    for row, p, q in zip(rows, prem, proa):
        print(f'{row:<12}{p:>16.2f}{q:>15.3f}')
    if len(rows) >= 3:
        rho = _spearman(prem, proa)
        print(f'\nSpearman rho = {rho:+.2f} over {len(rows)} rows')
        # The rubric says the agent established evidence before proposing;
        # the count says how often it did the opposite. They should run
        # against each other.
        if rho > -0.5:
            print(
                '   the rubric does NOT track the behaviour it names — '
                'expected a strong negative. Explain before quoting '
                'either number.'
            )
        else:
            print('   the rubric tracks the behaviour it names.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
