"""Does the agent's answer move when the evidence moves?

The corpus authors, for clarifications that mattered, alternative answers
the reporter could plausibly have given, each marked with whether the
right fix changes as a result: 1,635 variants over all 229 released
cases. That turns a static answer key into an intervention.

The question is not whether an agent scores well. It is whether it is
*conditioning on what the user said* at all. An agent that pattern-matches
the opening report will propose the same fix whichever answer it gets
back, and no aggregate score reveals that — both runs can look equally
competent.

Two steps, because the middle one costs gateway time:

    # 1. draw a balanced plan of interventions
    uv run --native-tls python scripts/counterfactual.py plan \
        --n 60 --out runs/cf/plan.jsonl

    # 2. after running baseline and each variant, score the pairs
    uv run --native-tls python scripts/counterfactual.py score \
        runs/cf/plan.jsonl --baseline RUN_DIR --variants runs/cf

Each plan row carries the `--sim-config` to run it with: the harness
already serves `answer_overrides` on every reveal path (clarification
reply, mixed edge, forced reveal), so an intervention is a config, not a
code change.

Scoring reports two rates, and they fail in opposite directions:

* **sensitivity** — of the variants where the fix *should* change, how
  often the agent's final proposal did. Low means it is not listening.
* **specificity** — of the variants where it should *not*, how often the
  agent held its answer. Low means it is blown around by irrelevant
  detail.

An agent can only score well on both by actually using the evidence.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))


def _released() -> list[dict]:
    out = []
    for path in sorted(REPO.glob('data/*/graphs/*.json')):
        task = json.loads(path.read_text())
        if (task.get('metadata') or {}).get('hitl_reviewed'):
            out.append(task)
    return out


def _self_earned(baseline: str) -> set[str]:
    """
    Cases where the baseline agent proposed a fix of its own.

    An intervention is only readable against such a case. Where the agent
    reached its terminal solely through a forced reveal, the proposal on
    record is the simulator's, and changing the user's answer cannot move
    something the agent never chose. The first run of this experiment did
    not filter on it and 55 of 60 interventions came back uncomparable.
    """
    import glob as _glob  # noqa: PLC0415

    out: set[str] = set()
    for path in _glob.glob(os.path.join(baseline, '*.jsonl')):
        case = os.path.basename(path)[:-6]
        with open(path) as fh:
            for line in fh:
                event = json.loads(line).get('event') or {}
                if event.get('solution_call') and not event.get('forced_reveal'):
                    out.add(case)
                    break
    return out


def plan(args: argparse.Namespace) -> int:
    usable = _self_earned(args.baseline) if args.baseline else None
    if usable is not None:
        print(f'{len(usable)} cases in the baseline have a self-earned proposal')
    rows: list[dict] = []
    for task in _released():
        if usable is not None and task['task_id'] not in usable:
            continue
        for edge in task['graph']['edges']:
            for clar in edge.get('clarifications') or []:
                for cf in clar.get('counterfactual_candidates') or []:
                    rows.append({
                        'task_id': task['task_id'],
                        'info_id': clar['info_id'],
                        'level': clar.get('level'),
                        'type': cf.get('type'),
                        'solution_should_change': bool(
                            cf.get('solution_should_change')
                        ),
                        'answer': cf.get('answer', ''),
                        'sim_config': json.dumps(
                            {'answer_overrides': {
                                clar['info_id']: cf.get('answer', '')
                            }},
                            ensure_ascii=False,
                        ),
                    })
    # Balance the two directions. An unbalanced plan reports a flattering
    # number: variants that should change outnumber the rest 954 to 681,
    # and sensitivity is the easier of the two rates to score well on.
    changing = [r for r in rows if r['solution_should_change']]
    holding = [r for r in rows if not r['solution_should_change']]
    half = args.n // 2
    picked: list[dict] = []
    for bucket in (changing, holding):
        # Even strides over a case-sorted bucket: deterministic, and
        # spreads the sample across cases instead of over-drawing the
        # cases that happen to carry many variants.
        bucket = sorted(bucket, key=lambda r: (r['task_id'], r['info_id']))
        take = min(half, len(bucket))
        step = len(bucket) / take
        picked += [bucket[int(i * step)] for i in range(take)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w') as fh:
        for row in picked:
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    cases = len({r['task_id'] for r in picked})
    print(
        f'{len(picked)} interventions over {cases} cases '
        f'({sum(r["solution_should_change"] for r in picked)} should change) '
        f'-> {out}'
    )
    print(f'   drawn from {len(rows)} authored variants')
    return 0


def _final_solution(run_dir: str, case: str) -> str | None:
    """The edge id of the last solution call the agent earned."""
    path = os.path.join(run_dir, case + '.jsonl')
    if not os.path.exists(path):
        return None
    last = None
    for line in open(path):
        event = json.loads(line).get('event') or {}
        call = event.get('solution_call')
        # A forced reveal is the simulator's move, not the agent's; it
        # would make every intervention look like it landed.
        if call and not event.get('forced_reveal'):
            last = call.get('edge_id')
    return last


def score(args: argparse.Namespace) -> int:
    rows = [json.loads(line) for line in Path(args.plan).read_text().splitlines()]
    sens_hit = sens_n = spec_hit = spec_n = missing = unearned = 0
    for row in rows:
        # The runner nests its output as <out>/<run_id>/, so a variant's
        # transcripts sit one level below the directory named for it.
        slug = f"cf-{row['task_id']}-{row['info_id']}"
        variant_dir = os.path.join(args.variants, slug, slug)
        base = _final_solution(args.baseline, row['task_id'])
        var = _final_solution(variant_dir, row['task_id'])
        if base is None or var is None:
            # Two different failures. Either the variant never ran, or one
            # side reached its terminal only through a forced reveal and so
            # has no proposal of the agent's own to compare. Lumping them
            # together hides a sampling error behind an ops problem.
            if not os.path.exists(os.path.join(variant_dir, row['task_id'] + '.jsonl')):
                missing += 1
            else:
                unearned += 1
            continue
        changed = base != var
        if row['solution_should_change']:
            sens_n += 1
            sens_hit += changed
        else:
            spec_n += 1
            spec_hit += not changed
    print(
        f'scored {sens_n + spec_n} of {len(rows)} interventions '
        f'({missing} never ran, {unearned} had no self-earned proposal on '
        f'one side)'
    )
    if sens_n:
        print(
            f'   sensitivity  {sens_hit}/{sens_n} '
            f'({100 * sens_hit / sens_n:.0f}%) — answer moved when it should'
        )
    if spec_n:
        print(
            f'   specificity  {spec_hit}/{spec_n} '
            f'({100 * spec_hit / spec_n:.0f}%) — answer held when it should'
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--n', type=int, default=60)
    p.add_argument('--out', default='runs/cf/plan.jsonl')
    p.add_argument(
        '--baseline',
        help='baseline run dir; restricts the sample to cases where the '
             'agent proposed a fix of its own, the only ones an '
             'intervention can be read against',
    )
    p.set_defaults(func=plan)
    s = sub.add_parser('score')
    s.add_argument('plan')
    s.add_argument('--baseline', required=True)
    s.add_argument('--variants', default='runs/cf')
    s.set_defaults(func=score)
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
