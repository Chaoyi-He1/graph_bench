#!/usr/bin/env python3
"""
Draw a stratified, blinded sample for a human judge-validation study and
emit one grading sheet per transcript.

The judge has never been checked against a human. This prepares the study
so the humans do only the reading and scoring:

  * 15 transcripts per model row, stratified across grade quartiles within
    the row, so easy and hard cases both appear.
  * Blinded: the sheet never names the model. The mapping lives in a
    separate key file the annotators must not open.
  * Humans see EXACTLY what the judge saw -- the same rendered transcript
    (reused from the recorder, not re-implemented), the agent's reasoning
    channel, the termination reason, the user's final satisfaction, and the
    verbatim rubric instructions -- so they grade the judge's construct and
    not a different one.
  * Scores on {0, 0.25, 0.5, 0.75, 1}, the judge's own range, so judge and
    human are directly comparable without rescaling.

Usage:
    python scripts/human_validation_sample.py --out ~/graph_bench_human --seed 7
Then hand each annotator `sheets/` and `scores_ANNOTATOR.csv`; keep
`KEY.json` away from them until scoring is done.
"""
from __future__ import annotations
import argparse, csv, json, os, random, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from graph_bench.recorder.reader import load_run, to_transcript  # noqa: E402
from graph_bench.judge.provider import rubric_instructions  # noqa: E402
from graph_bench.judge.rubrics import _agent_reasoning  # noqa: E402

WS = Path(os.path.expanduser('~/graph_bench_ws'))
M = WS / 'runs/matrix'
ROWS = [('gpt-5.6', 'm-gpt56'), ('gpt-5.5', 'm-gpt55'),
        ('GLM-5.1', 'm-glm51'), ('Kimi-2.5', 'm-kimi25')]
RUBRICS = ('proactiveness', 'hallucination', 'explanation', 'recovery')
SCALE = '0 / 0.25 / 0.5 / 0.75 / 1'


def stratified(grades: dict[str, float], k: int, rng: random.Random) -> list[str]:
    """k cases spread across grade quartiles, so the sample is not all
    middling cases where judge and human would trivially agree."""
    ordered = sorted(grades, key=grades.get)
    q = [ordered[i * len(ordered) // 4:(i + 1) * len(ordered) // 4] for i in range(4)]
    per = [k // 4 + (1 if i < k % 4 else 0) for i in range(4)]
    out = []
    for bucket, n in zip(q, per):
        out += rng.sample(bucket, min(n, len(bucket)))
    return out


def render(sheet_id: str, term, sat, turns, jt, instr) -> str:
    lines = [f'# Sheet {sheet_id}', '',
             'Score each rubric on the scale ' + SCALE + '. Read the whole',
             'transcript first. The definitions below are the exact ones the',
             'automated judge was given; grade the same construct, not your own.',
             '']
    for r in RUBRICS:
        lines += [f'## {r}', '', instr[r], '', f'**Your score ({SCALE}):** ____', '']
    lines += ['---', '', '## Context the judge also saw', '',
              f'- termination_reason: `{term}`',
              f'- final_user_satisfaction: `{sat}`', '']
    reasoning = _agent_reasoning(turns)
    if reasoning and reasoning.strip():
        lines += ['## Agent reasoning channel (if any)', '', '```', reasoning.strip()[:4000], '```', '']
    lines += ['## Transcript', '']
    for m in jt:
        who = 'USER' if m['role'] == 'user' else 'AGENT'
        lines += [f'**{who}:** {m["text"]}', '']
    return '\n'.join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--per-row', type=int, default=15)
    ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    out = Path(os.path.expanduser(a.out)); (out / 'sheets').mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    instr = rubric_instructions('default')

    key, rows_csv = {}, []
    for name, r in ROWS:
        run = M / r / r
        recorded = load_run(run)
        j = json.loads((run / 'judgments.json').read_text())['testcases']
        grades = {k: v['grade'] for k, v in j.items() if v.get('grade') is not None}
        for case in stratified(grades, a.per_row, rng):
            sid = f'{rng.randrange(10**6):06d}'
            while sid in key:
                sid = f'{rng.randrange(10**6):06d}'
            turns = recorded.traces[case]
            mm = recorded.metrics.testcases[case].metrics
            (out / 'sheets' / f'{sid}.md').write_text(
                render(sid, mm.termination_reason, mm.final_user_satisfaction,
                       turns, to_transcript(turns), instr))
            key[sid] = {'model': name, 'run': r, 'case': case,
                        'judge': {x: (j[case].get('rubrics') or {}).get(x, {}).get('score')
                                  for x in RUBRICS},
                        'judge_grade': grades[case]}
            rows_csv.append(sid)

    (out / 'KEY.json').write_text(json.dumps(key, indent=1))
    for ann in ('A', 'B'):
        with open(out / f'scores_{ann}.csv', 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['sheet'] + list(RUBRICS) + ['notes'])
            for sid in sorted(rows_csv):
                w.writerow([sid, '', '', '', '', ''])
    print(f'{len(key)} sheets -> {out}/sheets/   scores_A.csv scores_B.csv   KEY.json (keep from annotators)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
