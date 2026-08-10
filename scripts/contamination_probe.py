"""Contamination probe: can a model produce the answer with NO dialogue?

Every case comes from a public thread that may sit in pretraining data.
The benchmark's claim is that it measures interactive diagnosis, not
recall — so a model that already knows the case should be able to skip
the conversation. This probe measures exactly that skip:

  turn-0 probe   the model sees ONLY the opening report and is asked for
                 the final root cause + fix, with no chance to ask
                 anything. A grader (model, thread in hand) decides
                 whether that answer matches the thread's accepted
                 diagnosis.

A high turn-0 hit rate on a case means the case is recall-solvable and
its multi-turn score is contaminated. The per-case verdicts are written
out so the paper can report the rate, split it by issue date, and (if
needed) publish a decontaminated subset.

Usage:
  uv run --native-tls python scripts/contamination_probe.py [N]
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())


_load_env(REPO / '.env')

from graph_bench.llm import build_chat_client  # noqa: E402
from graph_bench.user_simulator.provider import extract_text  # noqa: E402

OUT = REPO / 'runs' / 'contamination'
OUT.mkdir(parents=True, exist_ok=True)

ANSWER_PROMPT = """You are a senior engineer. Below is the opening report \
of a real software issue. State, as specifically as you can, the ROOT CAUSE \
and the FIX that the maintainers eventually landed. You cannot ask questions \
— answer from what you know.

If you do not know this specific issue, say so plainly instead of guessing.

OPENING REPORT ({repo} #{number}):
{body}

Answer in at most 120 words: root cause, then fix."""

GRADE_PROMPT = """Decide whether a candidate answer already identifies the \
resolution that a support thread eventually reached.

THREAD'S ACCEPTED OUTCOME (from the annotated answer key):
- root cause / final diagnosis: {root}
- required elements of the accepted fix: {elements}
- satisfaction conditions: {conditions}

CANDIDATE ANSWER (produced with NO access to the thread, from the opening \
report alone):
{answer}

Grade STRICTLY. "hit" means the candidate names the same mechanism AND the \
same class of fix — not merely the same subsystem, and not a generic \
suggestion that happens to overlap. "partial" means it names the mechanism \
but not the fix (or vice versa). "miss" means neither, or the candidate \
declines to answer.

Return ONLY JSON: {{"grade": "hit"|"partial"|"miss", "why": "<1 sentence>"}}"""

_FENCE = re.compile(r'^```(?:json)?\s*|\s*```$', re.MULTILINE)


def _terminal_solution(graph: dict) -> dict:
    nodes = graph['graph']['nodes']
    for e in graph['graph']['edges']:
        sol = e.get('solution')
        if sol and nodes.get(e['to'], {}).get('is_terminal'):
            return sol
    return {}


def run_one(answer_llm, grade_llm, path: Path) -> None:
    slug = path.stem
    out = OUT / f'{slug}.json'
    if out.exists():
        return
    g = json.loads(path.read_text())
    src = path.parents[1]
    raw = json.loads((src / 'raw' / f'{slug}.json').read_text())
    sol = _terminal_solution(g)
    try:
        answer = extract_text(
            answer_llm.invoke(
                ANSWER_PROMPT.format(
                    repo=raw.get('repo', '?'),
                    number=raw.get('number', '?'),
                    body=(g.get('body') or '')[:4000],
                )
            )
        ).strip()
        text = extract_text(
            grade_llm.invoke(
                GRADE_PROMPT.format(
                    root=sol.get('intent', ''),
                    elements='; '.join(
                        sol.get('required_elements_for_full_match', [])
                    ),
                    conditions='; '.join(g.get('satisfaction_conditions', [])),
                    answer=answer[:3000],
                )
            )
        ).strip()
        text = _FENCE.sub('', text).strip()
        verdict = json.loads(text[text.find('{') : text.rfind('}') + 1])
        verdict.update(
            slug=slug,
            created_at=raw.get('created_at'),
            answer=answer[:1500],
        )
        out.write_text(json.dumps(verdict, ensure_ascii=False, indent=1))
        print(f'{slug}: {verdict["grade"]}')
    except Exception as exc:  # noqa: BLE001
        print(f'{slug}: FAILED ({str(exc)[:100]})')


def main() -> None:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    cases = [
        p
        for p in sorted(REPO.glob('data/*/graphs/*.json'))
        if json.loads(p.read_text())['metadata'].get('hitl_reviewed')
    ]
    if limit:
        cases = cases[:limit]
    lock = threading.Lock()
    idx = {'i': 0}

    def worker() -> None:
        a = build_chat_client(effort='medium', max_tokens=1200)
        gr = build_chat_client(effort='medium', max_tokens=600)
        while True:
            with lock:
                if idx['i'] >= len(cases):
                    return
                p = cases[idx['i']]
                idx['i'] += 1
            run_one(a, gr, p)

    ts = [threading.Thread(target=worker) for _ in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(f'contamination probe complete: {len(list(OUT.glob("*.json")))}')


if __name__ == '__main__':
    main()
