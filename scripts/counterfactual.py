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


def _variant_dir(root: str, row: dict) -> str | None:
    """The run directory for one intervention, whatever it was named."""
    hits = [
        d for d in glob.glob(
            os.path.join(root, f"cf-{row['task_id']}-{row['info_id']}*", '')
        )
        if os.path.isdir(d)
    ]
    if not hits:
        return None
    inner = glob.glob(os.path.join(hits[0], '*', ''))
    return inner[0] if inner else hits[0]


def score(args: argparse.Namespace) -> int:
    """
    Three outcomes per intervention, not two.

    The first version asked only whether the proposal changed, and could
    not score a case where the agent never reached a proposal of its own.
    That turned out to be most of them — 43 of 60 — and not because the
    sample was drawn badly: every baseline in the plan closes its case
    unaided, by construction. Changing one answer is what stops the agent
    closing. An intervention that derails the conversation is a result,
    and collapsing it into "unscoreable" hides the largest thing this
    experiment found.
    """
    rows = [json.loads(line) for line in Path(args.plan).read_text().splitlines()]
    tally = {
        (True, 'adapted'): 0, (True, 'held'): 0, (True, 'derailed'): 0,
        (False, 'adapted'): 0, (False, 'held'): 0, (False, 'derailed'): 0,
    }
    missing = 0
    for row in rows:
        variant_dir = _variant_dir(args.variants, row)
        if variant_dir is None:
            missing += 1
            continue
        base = _final_solution(args.baseline, row['task_id'])
        var = _final_solution(variant_dir, row['task_id'])
        if base is None:
            missing += 1
            continue
        if var is None:
            outcome = 'derailed'
        elif base != var:
            outcome = 'adapted'
        else:
            outcome = 'held'
        tally[(row['solution_should_change'], outcome)] += 1

    print(f'{sum(tally.values())} interventions scored ({missing} unusable)\n')
    for should, label in ((True, 'the fix SHOULD change'),
                          (False, 'the fix should NOT change')):
        n = sum(v for (s, _), v in tally.items() if s == should)
        if not n:
            continue
        print(f'{label} (n={n})')
        for outcome, gloss in (
            ('adapted', 'proposed something different'),
            ('held', 'proposed the same thing'),
            ('derailed', 'never reached a proposal of its own'),
        ):
            c = tally[(should, outcome)]
            mark = ''
            if should and outcome == 'adapted':
                mark = '  <- correct'
            if not should and outcome == 'held':
                mark = '  <- correct'
            print(f'   {gloss:<38} {c:>3}  ({100 * c / n:>3.0f}%){mark}')
        print()
    derailed = sum(v for (_, o), v in tally.items() if o == 'derailed')
    total = sum(tally.values())
    if total:
        print(
            f'derailed on either direction: {derailed}/{total} '
            f'({100 * derailed / total:.0f}%) — the agents mostly do not '
            'switch to a different fix when the evidence changes; they '
            'stop being able to close the case at all.'
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
