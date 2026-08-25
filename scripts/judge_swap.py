"""Does the ranking survive a judge from a different family?

The main table is scored by a gpt-5.6-family judge, and gpt-5.6 is one of
the models it ranks. Self-preference is the first thing a reader will
ask about, and the answer cannot be "we used a good prompt".

This re-judges an already-recorded row with a different judge model and
compares. It needs no new conversations — the transcripts exist — so a
swap costs judging alone, not a re-run.

    # re-judge row 1 with a different family
    uv run --native-tls python scripts/judge_swap.py judge \
        RUN_DIR --model lynx_ai_glm_5.1

    # compare the two verdicts on the same transcripts
    uv run --native-tls python scripts/judge_swap.py compare \
        RUN_DIR --model lynx_ai_glm_5.1

The swap writes into a sibling directory rather than over the original
judgments, so the primary result is never clobbered by a check on it.

What to read: if the two judges disagree on *level* but agree on
*ordering*, the table's comparisons stand and only the absolute numbers
are judge-specific. If they disagree on ordering, the ranking is a
property of the judge and must be reported that way.
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics as st
import subprocess
import sys
from pathlib import Path


def _swap_dir(run_dir: str, model: str) -> Path:
    slug = model.replace('/', '_').replace('.', '')
    return Path(str(run_dir.rstrip('/')) + f'-judged-by-{slug}')


def judge(args: argparse.Namespace) -> int:
    src = Path(args.run_dir)
    dst = _swap_dir(args.run_dir, args.model)
    dst.mkdir(parents=True, exist_ok=True)
    # Transcripts and metrics are the judge's input; copying them keeps the
    # original judgments.json untouched by this check.
    # run.json too: the recorder's loader needs the run header, and
    # leaving it out made every swap die on the first read.
    for path in list(src.glob('*.jsonl')) + [
        src / 'metrics.json',
        src / 'run.json',
    ]:
        target = dst / path.name
        if path.exists() and not target.exists():
            shutil.copy2(path, target)
    print(f'judging {len(list(dst.glob("*.jsonl")))} transcripts with {args.model}')
    return subprocess.call([
        'uv', 'run', '--native-tls', 'python', '-m', 'graph_bench',
        'judge', 'run', str(dst), '--model', args.model, '--online',
        '--concurrency', str(args.concurrency),
    ])


def _grades(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text())['testcases']
    return {c: v['grade'] for c, v in data.items() if v.get('grade') is not None}


def compare(args: argparse.Namespace) -> int:
    primary = _grades(Path(args.run_dir, 'judgments.json'))
    other = _grades(_swap_dir(args.run_dir, args.model) / 'judgments.json')
    common = sorted(set(primary) & set(other))
    if not common:
        print('no overlap — has the swap been judged yet?')
        return 1
    a = [primary[c] for c in common]
    b = [other[c] for c in common]
    deltas = [y - x for x, y in zip(a, b)]
    print(f'{len(common)} cases judged by both')
    print(f'   primary judge   mean={st.mean(a):.4f}')
    print(f'   {args.model:<15} mean={st.mean(b):.4f}   '
          f'delta={st.mean(deltas):+.4f}')
    print(f'   per-case |delta| mean={st.mean(abs(d) for d in deltas):.3f} '
          f'median={st.median(abs(d) for d in deltas):.3f}')
    # Ordering is what the table actually claims; levels are allowed to move.
    ranked_a = sorted(common, key=lambda c: primary[c])
    ranked_b = sorted(common, key=lambda c: other[c])
    pos_b = {c: i for i, c in enumerate(ranked_b)}
    n = len(common)
    concordant = sum(
        1
        for i, c in enumerate(ranked_a)
        for d in ranked_a[i + 1:]
        if (pos_b[d] > pos_b[c])
    )
    total = n * (n - 1) / 2
    tau = (2 * concordant / total) - 1 if total else 0.0
    print(f'   rank agreement (Kendall tau) = {tau:.3f}')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    j = sub.add_parser('judge')
    j.add_argument('run_dir')
    j.add_argument('--model', required=True)
    j.add_argument('--concurrency', type=int, default=4)
    j.set_defaults(func=judge)
    c = sub.add_parser('compare')
    c.add_argument('run_dir')
    c.add_argument('--model', required=True)
    c.set_defaults(func=compare)
    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
