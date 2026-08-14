"""Validity gate for a recorded run: is this row scoreable at all?

A matrix row can look like a weak model when it is really a broken
configuration. The failure that motivated this check: an output budget
left unset makes the gateway cap output at 1000 tokens, a reasoning
model spends the whole budget on reasoning, and the agent returns an
EMPTY message every turn. Empty turns match no edge, so the row scores
terrible — indistinguishable from genuine incapability unless you look
at the transcripts.

Usage:  uv run --native-tls python scripts/run_validity.py RUN_DIR [...]
Exit code 1 if any run exceeds the empty-reply threshold.
"""

from __future__ import annotations

import glob
import json
import os
import statistics as st
import sys

# An occasional empty turn is normal (a model may return only a tool-less
# refusal); a quarter of them is not.
EMPTY_RATE_FAIL = 0.05


def audit(run_dir: str) -> dict:
    turns = empty = 0
    lens: list[int] = []
    for path in glob.glob(os.path.join(run_dir, '*.jsonl')):
        with open(path) as fh:
            for line in fh:
                text = (json.loads(line).get('agent') or {}).get('text')
                if text is None:
                    continue
                turns += 1
                lens.append(len(text))
                if not text.strip():
                    empty += 1
    rate = empty / turns if turns else 0.0
    return {
        'run': os.path.basename(run_dir.rstrip('/')),
        'agent_turns': turns,
        'empty': empty,
        'empty_rate': round(rate, 4),
        'len_median': st.median(lens) if lens else 0,
        'verdict': 'INVALID' if rate > EMPTY_RATE_FAIL else 'ok',
    }


def main() -> int:
    bad = 0
    for run_dir in sys.argv[1:]:
        r = audit(run_dir)
        print(
            f"{r['run']:<14} turns={r['agent_turns']:<5} "
            f"empty={r['empty']:<5} ({100 * r['empty_rate']:.1f}%) "
            f"len_med={r['len_median']:<6.0f} {r['verdict']}"
        )
        if r['verdict'] == 'INVALID':
            bad += 1
            print(
                '   -> empty replies dominate: check the output budget '
                '(max_tokens) against this model\'s reasoning usage before '
                'reporting any score from this row.'
            )
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
