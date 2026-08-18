"""Does the model judge agree with a human on the same conversations?

An execution-free benchmark stands or falls on its judge: there is no test
suite to appeal to, so every reported score is the judge's opinion. This
builds the study that checks it, in two steps.

    # 1. draw a stratified sample and write a sheet to fill in
    uv run --native-tls python scripts/judge_agreement.py sample RUN_DIR \
        --n 40 --out runs/agreement

    # 2. after filling runs/agreement/human.json, score the agreement
    uv run --native-tls python scripts/judge_agreement.py score \
        runs/agreement

The sample is stratified over the judge's own grade so the study covers
the range rather than the middle: an agreement figure computed only on
cases the judge scored 0.4–0.6 says nothing about whether it can tell a
good conversation from a bad one.

The sheet deliberately does NOT show the judge's scores. They are written
to a separate file and only joined at scoring time, so the annotator is
not anchored on the number they are meant to check.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics as st
from pathlib import Path

RUBRICS = ('proactiveness', 'hallucination', 'explanation', 'recovery')


def _load(run_dir: str) -> tuple[dict, dict]:
    judgments = json.loads(
        Path(run_dir, 'judgments.json').read_text()
    )['testcases']
    metrics = json.loads(Path(run_dir, 'metrics.json').read_text())['testcases']
    return judgments, metrics


def _transcript(run_dir: str, case: str) -> list[dict]:
    path = Path(run_dir, case + '.jsonl')
    return [json.loads(line) for line in path.read_text().splitlines()]


def sample(args: argparse.Namespace) -> int:
    judgments, metrics = _load(args.run_dir)
    cases = sorted(judgments, key=lambda c: judgments[c]['grade'])
    if not cases:
        print('no judged cases')
        return 1
    # Even strides through the grade-sorted list: a deterministic stratified
    # sample, reproducible without a seed.
    step = len(cases) / min(args.n, len(cases))
    picked = [cases[int(i * step)] for i in range(min(args.n, len(cases)))]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    blank: dict[str, dict] = {}
    lines = [
        '# Judge agreement sheet',
        '',
        f'{len(picked)} conversations sampled from `{args.run_dir}`, evenly '
        'spread over the judge grade range. Score each one yourself, then '
        'put your numbers in `human.json` beside this file and run '
        '`judge_agreement.py score`.',
        '',
        'Each rubric is 0–1. Mind the direction: three are "more is '
        'better" and **hallucination is not** — it scores how much the '
        'agent asserted that the conversation does not support, so 0 is '
        'clean and 1 is pervasive. The grade uses 1 − hallucination.',
        '',
        '- **proactiveness** — did it ask for the evidence it needed '
        'before proposing? (1 = always)',
        '- **hallucination** — how much did it state as fact that the '
        'user never reported? (**0 = nothing invented**, 1 = pervasive)',
        '- **explanation** — does it account for the fault, not just '
        'prescribe steps? (1 = fully)',
        '- **recovery** — when a step failed, did it change tack '
        'sensibly? (1 = always)',
        '',
        'The judge\'s own scores are in `judge.json` and are deliberately '
        'not shown here.',
        '',
    ]
    for case in picked:
        blank[case] = dict.fromkeys(RUBRICS, None)
        snapshot = metrics.get(case, {}).get('snapshot', {})
        lines += [
            f'## {case}',
            '',
            f"ended `{snapshot.get('termination_reason', '?')}` after "
            f"{snapshot.get('turn_index', '?')} turns; states visited: "
            f"{', '.join(snapshot.get('visited') or []) or '—'}",
            '',
        ]
        for row in _transcript(args.run_dir, case):
            agent = (row.get('agent') or {}).get('text') or ''
            user = (row.get('user') or {}).get('text') or ''
            event = row.get('event') or {}
            index = event.get('turn_index', '?')
            if agent:
                lines += [f'**agent [{index}]** {agent.strip()}', '']
            if user:
                mark = ' _(forced reveal)_' if event.get('forced_reveal') else ''
                lines += [f'**user [{index}]**{mark} {user.strip()}', '']
        lines += ['---', '']

    (out / 'sheet.md').write_text('\n'.join(lines))
    (out / 'judge.json').write_text(
        json.dumps(
            {
                c: {
                    'grade': judgments[c]['grade'],
                    **{
                        r: judgments[c]['rubrics'].get(r, {}).get('score')
                        for r in RUBRICS
                    },
                }
                for c in picked
            },
            indent=2,
        )
    )
    human_path = out / 'human.json'
    if not human_path.exists():
        human_path.write_text(json.dumps(blank, indent=2))
    print(
        f'wrote {out}/sheet.md ({len(picked)} cases), {out}/judge.json, '
        f'and a blank {out}/human.json'
    )
    return 0


def _spearman(xs: list[float], ys: list[float]) -> float:
    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
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


def score(args: argparse.Namespace) -> int:
    out = Path(args.out)
    judge = json.loads((out / 'judge.json').read_text())
    human = json.loads((out / 'human.json').read_text())
    paired = [
        c
        for c in judge
        if human.get(c) and all(human[c].get(r) is not None for r in RUBRICS)
    ]
    if not paired:
        print(f'nothing filled in yet in {out}/human.json')
        return 1
    print(f'{len(paired)}/{len(judge)} cases annotated\n')
    print(f"{'rubric':<16}{'judge':>8}{'human':>8}{'mean|Δ|':>10}{'rho':>8}")
    for rubric in RUBRICS:
        j = [judge[c][rubric] or 0.0 for c in paired]
        h = [float(human[c][rubric]) for c in paired]
        # compared as the judge scores it, direction included
        deltas = [abs(a - b) for a, b in zip(j, h)]
        print(
            f'{rubric:<16}{st.mean(j):>8.3f}{st.mean(h):>8.3f}'
            f'{st.mean(deltas):>10.3f}{_spearman(j, h):>8.3f}'
        )
    # A benchmark's headline number is the overall grade; the rubric mean is
    # the closest thing a human sheet produces to it without re-deriving the
    # weighting, so agreement is reported on both.
    jg = [judge[c]['grade'] for c in paired]
    # hallucination is scored in the opposite direction to the other three
    # (the grade uses 1 - it), so it must be flipped before averaging or the
    # comparison rewards exactly the runs a human marked as inventing facts.
    hg = [
        st.mean(
            1.0 - float(human[c][r]) if r == 'hallucination'
            else float(human[c][r])
            for r in RUBRICS
        )
        for c in paired
    ]
    deltas = [abs(a - b) for a, b in zip(jg, hg)]
    print(
        f"\n{'grade vs rubric mean':<16}{st.mean(jg):>8.3f}{st.mean(hg):>8.3f}"
        f'{st.mean(deltas):>10.3f}{_spearman(jg, hg):>8.3f}'
    )
    worst = sorted(zip(deltas, paired), reverse=True)[:5]
    print('\nwidest disagreements:')
    for delta, case in worst:
        print(f'   {delta:.2f}  {case}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('sample', help='draw a stratified sample to annotate')
    s.add_argument('run_dir')
    s.add_argument('--n', type=int, default=40)
    s.add_argument('--out', default='runs/agreement')
    s.set_defaults(func=sample)
    t = sub.add_parser('score', help='score a filled-in sheet')
    t.add_argument('out', nargs='?', default='runs/agreement')
    t.set_defaults(func=score)
    args = parser.parse_args()
    if args.cmd == 'score' and not glob.glob(os.path.join(args.out, '*.json')):
        print(f'no sheet in {args.out}; run `sample` first')
        return 1
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
