"""Is a recorded row actually complete, and is what is missing random?

A row loses cases three ways, and all three used to be silent:

* the backbone crashes mid-conversation — a truncated transcript with no
  metrics entry;
* the judge fails and the case is dropped — metrics but no grade;
* a case never starts at all.

None of this shows in the aggregates. The first 229-case row published
n=221 with no sign that two of the missing were `terminal_resolved` —
the agent's best outcomes, lost to one 502 from the gateway. A row that
drops its successes reports a lower grade than the model earned, and
nothing in the output says so.

    uv run --native-tls python scripts/run_integrity.py RUN_DIR [...]

Exit code 1 if any row is incomplete, so it can gate a table.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path


def _parse_errors(judged: dict) -> int:
    """Rubric verdicts that came from a failed parse rather than a judge."""
    return sum(
        1
        for v in judged.values()
        for rv in (v.get('rubrics') or {}).values()
        if rv.get('label') == 'parse_error'
    )


def audit(run_dir: str, expected: int | None) -> dict:
    transcripts = {
        os.path.basename(p)[:-6] for p in glob.glob(os.path.join(run_dir, '*.jsonl'))
    }
    metrics_path = Path(run_dir, 'metrics.json')
    judge_path = Path(run_dir, 'judgments.json')
    metrics = (
        json.loads(metrics_path.read_text())['testcases']
        if metrics_path.exists()
        else {}
    )
    judged = (
        json.loads(judge_path.read_text())['testcases']
        if judge_path.exists()
        else {}
    )
    truncated = sorted(transcripts - set(metrics))
    unjudged = sorted(set(metrics) - set(judged))
    # The question that matters is not how many were lost but whether the
    # loss was outcome-neutral. Cases that resolved are the ones a dropped
    # sample most distorts.
    lost_resolved = [
        c
        for c in unjudged
        if metrics[c]['snapshot']['termination_reason'] == 'terminal_resolved'
    ]
    return {
        'run': os.path.basename(run_dir.rstrip('/')),
        'parse_errors': _parse_errors(judged),
        'expected': expected,
        'transcripts': len(transcripts),
        'metrics': len(metrics),
        'judged': len(judged),
        'truncated': truncated,
        'unjudged': unjudged,
        'lost_resolved': lost_resolved,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    expected = next(
        (
            int(a.split('=')[1])
            for a in sys.argv[1:]
            if a.startswith('--expected=')
        ),
        None,
    )
    bad = 0
    for run_dir in args:
        r = audit(run_dir, expected)
        short = (
            (expected is not None and r['judged'] < expected)
            or r['truncated']
            or r['unjudged']
            # A row scored by the broken judge is not a shorter row, it is a
            # wrong one: a failed parse became score 0.0, which the grade
            # inverts on `hallucination` into free full marks. Mixing eras in
            # one comparison manufactures an effect the size of the fix.
            or r['parse_errors']
        )
        mark = 'INCOMPLETE' if short else 'ok'
        target = f"/{r['expected']}" if r['expected'] else ''
        print(
            f"{r['run']:<16} transcripts={r['transcripts']:<5} "
            f"metrics={r['metrics']:<5} judged={r['judged']}{target}  {mark}"
        )
        if r['truncated']:
            print(
                f"   {len(r['truncated'])} truncated (crashed mid-run, "
                f"no metrics): {', '.join(r['truncated'][:4])}"
                + (' …' if len(r['truncated']) > 4 else '')
            )
            print('      -> delete these transcripts and re-run the row; '
                  'the runner skips cases it already has')
        if r['unjudged']:
            print(
                f"   {len(r['unjudged'])} unjudged (metrics but no grade): "
                f"{', '.join(r['unjudged'][:4])}"
                + (' …' if len(r['unjudged']) > 4 else '')
            )
            print('      -> re-run `judge run` on the row; it skips cases '
                  'already judged')
        if r['parse_errors']:
            print(
                f"   !! {r['parse_errors']} rubric verdicts came from a failed "
                'parse, not a judge — this row predates the judge fix and '
                'CANNOT be compared against a row judged after it'
            )
            print('      -> `judge run <row> --force` to re-judge it')
        if r['lost_resolved']:
            print(
                f"   !! {len(r['lost_resolved'])} of the unjudged RESOLVED — "
                'the loss is biased toward successes, so the reported grade '
                'is below what the model earned'
            )
        if short:
            bad += 1
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
