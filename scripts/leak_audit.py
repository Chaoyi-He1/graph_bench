"""Did the simulator ever say something the agent had not earned?

The benchmark's central claim is that the simulated user speaks only from
its current graph position: this node's visible symptoms, the answers to
clarifications actually asked, and — when the insurance fires — a reveal
that is recorded as such. If a user turn instead names the root cause or
the fix before the agent got there, every score downstream of that turn is
contaminated, and the leak is invisible in the aggregates.

This audits recorded runs for exactly that. For each user turn it takes
the case's answer-key vocabulary — the distinctive words of the terminal
solution's required elements and of the satisfaction conditions — and asks
whether the turn used them before any turn that legitimately could:

  * a forced reveal (recorded, `forced_reveal: true`), or
  * arrival at the node/edge whose authored text contains them.

Words the opening report already contains are excluded: the user is free
to repeat their own bug report. Terms are matched whole-word and
case-folded, and a turn must hit at least ``MIN_HITS`` distinct answer-key
terms to be reported, so incidental overlap ("update", "restart") does not
raise an alarm on its own.

    uv run --native-tls python scripts/leak_audit.py RUN_DIR [...]

Exit code 1 if any unexplained leak is found.
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))

# A leak has to be specific. Two or more distinct answer-key terms in one
# user turn is the bar; one shared word is coincidence.
MIN_HITS = 2

# ...and at least one of them must be a term this corpus barely uses. Pairs
# of common words ("configuration", "source") clear MIN_HITS on their own
# and were most of the first pass's false alarms; a term appearing in this
# few cases' answer keys is the kind that actually gives an answer away.
RARE_DF = 3

# Words that carry no case-specific meaning even when they appear in an
# answer key, so they can never evidence a leak on their own.
GENERIC = frozenset(
    """the and for with that this from into your you are was were has have
    had not but all any can could should would will when where which who
    why how what use used using set sets setting run runs running make
    makes made take takes taken get gets got give gives given see sees
    seen look looks looking need needs needed want wants try tries tried
    change changes changed update updates updated fix fixes fixed issue
    issues problem problems error errors fail fails failed failure user
    users file files data value values name names type types version
    versions build builds check checks checking start starts started stop
    stops stopped work works working same different first last next new
    old more most less least than then than also only just even still
    after before during while about above below between over under again
    once each other another some such very much many few both either
    neither none nothing something anything everything""".split()
)

_WORD = re.compile(r'[a-z][a-z0-9_.-]{3,}')


def _terms(text: str) -> set[str]:
    # Trailing punctuation must not survive: "result." would otherwise miss
    # every exclusion list that spells it "result".
    words = (w.strip('.-_') for w in _WORD.findall(text.lower()))
    return {w for w in words if len(w) > 3 and w not in GENERIC}


def _answer_key(task: dict) -> set[str]:
    """Distinctive vocabulary of the case's answer — cause and fix."""
    graph = task['graph']
    terms: set[str] = set()
    for cond in task.get('satisfaction_conditions') or []:
        terms |= _terms(cond)
    for edge in graph['edges']:
        sol = edge.get('solution') or {}
        if not sol:
            continue
        to_node = graph['nodes'].get(edge['to'], {})
        if not to_node.get('is_terminal'):
            continue
        for element in sol.get('required_elements_for_full_match') or []:
            terms |= _terms(element.replace('_', ' '))
        terms |= _terms(sol.get('intent') or '')
    return terms


def _opening_earned(task: dict) -> set[str]:
    """
    Vocabulary the user may use before answering anything: their own bug
    report, and the symptoms of every node — what a user can see happening
    is theirs to describe whenever they reach it.
    """
    graph = task['graph']
    terms = _terms(task.get('title', '') + ' ' + task.get('body', ''))
    for node in graph['nodes'].values():
        for symptom in node.get('symptoms_visible') or []:
            terms |= _terms(symptom)
    return terms


def _answer_vocab(task: dict) -> dict[str, set[str]]:
    """info_id -> vocabulary of its authored answer, earned once asked."""
    out: dict[str, set[str]] = {}
    for edge in task['graph']['edges']:
        for clar in edge.get('clarifications') or []:
            out[clar['info_id']] = _terms(
                clar.get('user_answer_in_this_oncall') or ''
            ) | _terms(clar['info_id'].replace('_', ' '))
    return out


def _simulator_vocab() -> set[str]:
    """
    Words the simulator says in its own fixed drafts and reply intents.
    A canned follow-up asking the agent to "verify the result" must not
    read as a leak just because an answer key also says "verify".
    """
    from graph_bench.user_simulator import responder, speaker  # noqa: PLC0415

    terms: set[str] = set()
    for module in (responder, speaker):
        for name, value in vars(module).items():
            if not name.startswith('_') or not isinstance(value, str):
                continue
            terms |= _terms(value)
        for value in getattr(module, '_PARTIAL_TEMPLATES', {}).values():
            terms |= _terms(value)
        for value in getattr(module, '_PARTIAL_BY_KIND', {}).values():
            terms |= _terms(value)
    return terms


def _graphs(corpus: str) -> list[str]:
    """Graph paths under ``corpus``, whether it is one directory of graphs
    or the repository's data/ with a graphs/ dir per source."""
    return sorted(
        glob.glob(os.path.join(corpus, '*.json'))
        + glob.glob(os.path.join(corpus, '*/graphs/*.json'))
    )


def _released(paths: list[str]) -> list[str]:
    out = []
    for path in paths:
        try:
            task = json.loads(Path(path).read_text())
        except (ValueError, OSError):
            continue
        # data/ also holds review reports and stats dumps; a task is a dict
        # with a graph, and the release is the reviewed subset of those.
        if not isinstance(task, dict) or 'graph' not in task:
            continue
        if (task.get('metadata') or {}).get('hitl_reviewed'):
            out.append(path)
    return out


def _document_frequency(corpus: str) -> dict[str, int]:
    df: dict[str, int] = {}
    for path in _released(_graphs(corpus)):
        try:
            task = json.loads(Path(path).read_text())
        except (ValueError, OSError):
            continue
        for term in _answer_key(task):
            df[term] = df.get(term, 0) + 1
    return df


def audit(run_dir: str, corpus: str) -> list[dict]:
    findings: list[dict] = []
    df = _document_frequency(corpus)
    for path in sorted(glob.glob(os.path.join(run_dir, '*.jsonl'))):
        case = os.path.basename(path)[:-6]
        graph_path = next(
            (p for p in _graphs(corpus) if os.path.basename(p)[:-5] == case),
            None,
        )
        if graph_path is None:
            continue
        task = json.loads(Path(graph_path).read_text())
        graph = task['graph']
        answers = _answer_vocab(task)
        earned = _opening_earned(task) | _simulator_vocab()
        key = _answer_key(task) - earned
        if not key:
            continue
        revealed = False
        for line in open(path):
            row = json.loads(line)
            event = row.get('event') or {}
            user = (row.get('user') or {}).get('text') or ''
            # A recorded reveal is the reveal turn itself, not just the
            # turns after it: check the latch BEFORE this turn is scored.
            if event.get('forced_reveal') or event.get('revealed_by_simulator'):
                revealed = True
            # This turn's own answers are earned BY this turn: the reply that
            # delivers a clarification answer is the legitimate way that
            # vocabulary enters the conversation.
            for info_id in event.get('info_gained') or []:
                key -= answers.get(
                    info_id, _terms(info_id.replace('_', ' '))
                )
            # Reaching a state earns the right to describe it. An agent that
            # proposes the fix and lands on the terminal is told the outcome
            # — including, legitimately, a shortcut that gets there at once.
            after = event.get('node_after')
            if after and after != event.get('node_before'):
                for symptom in (
                    graph['nodes'].get(after, {}).get('symptoms_visible') or []
                ):
                    key -= _terms(symptom)
            hits = sorted(_terms(user) & key)
            rare = [h for h in hits if df.get(h, 0) <= RARE_DF]
            if not revealed and len(hits) >= MIN_HITS and rare:
                findings.append({
                    'case': case,
                    'turn': event.get('turn_index'),
                    'terms': rare[:3] + [h for h in hits if h not in rare][:3],
                    'text': user[:220],
                })
    return findings


# A non-terminal state whose visible symptoms presuppose the fix. The
# vocabulary screen cannot find these — a symptom legitimately shares words
# with the answer because it describes the same system — but the phrasing
# is distinctive: the reporter speaks from AFTER the resolution.
_RESOLVED_VOICE = re.compile(
    r'\b(?:with|on|using|after)\s+(?:a|the)\s+'
    r'(?:\w+\s+){0,3}(?:build|version|release|patch|commit)\s+'
    r'(?:that\s+)?(?:contain\w*|includ\w*|with)\s+(?:the\s+)?[\w-]*\s*fix'
    r'|\bafter\s+(?:applying|installing)\s+the\s+fix'
    r'|\b(?:the\s+)?fix(?:ed)?\s+build\b'
    r'|\bonce\s+the\s+fix\b'
    r'|\bwith\s+the\s+patch(?:ed)?\b',
    re.IGNORECASE,
)


def audit_corpus(corpus: str) -> list[dict]:
    """
    Static screen for states that speak from after the resolution.

    A run only exercises the nodes it reaches; a non-terminal node whose
    authored symptoms already presuppose the fix hands the answer to any
    agent that gets there, whether or not this run did.
    """
    findings: list[dict] = []
    for path in _released(_graphs(corpus)):
        task = json.loads(Path(path).read_text())
        case = os.path.basename(path)[:-5]
        graph = task['graph']
        # A state entered by proposing a fix may describe that fix's outcome
        # — that is the aftermath the agent earned. The defect is a state
        # reachable WITHOUT proposing anything whose symptoms already speak
        # from after the resolution.
        earned_by_fix = {
            e['to'] for e in graph['edges'] if e['edge_type'] != 'clarification_only'
        }
        for node_id, node in graph['nodes'].items():
            if node.get('is_terminal') or node_id in earned_by_fix:
                continue
            for symptom in node.get('symptoms_visible') or []:
                hit = _RESOLVED_VOICE.search(symptom)
                if hit:
                    findings.append({
                        'case': case,
                        'where': f'{node_id}.symptoms_visible',
                        'terms': [hit.group(0)],
                        'text': symptom[:200],
                    })
            for clar in (
                c
                for e in graph['edges']
                if e['from'] == node_id
                for c in (e.get('clarifications') or [])
            ):
                answer = clar.get('user_answer_in_this_oncall') or ''
                hit = _RESOLVED_VOICE.search(answer)
                if hit:
                    findings.append({
                        'case': case,
                        'where': f'{node_id} answer to {clar["info_id"]}',
                        'terms': [hit.group(0)],
                        'text': answer[:200],
                    })
    return findings


def main() -> int:
    corpus = os.environ.get(
        'LEAK_AUDIT_CORPUS', str(REPO / 'data/released/graphs')
    )
    if not os.path.isdir(corpus):
        corpus = str(REPO / 'data')
    if not _graphs(corpus):
        print(f'no graphs under {corpus}', file=sys.stderr)
        return 2
    if sys.argv[1:2] == ['--corpus']:
        findings = audit_corpus(corpus)
        n = len(_released(_graphs(corpus)))
        cases = {f['case'] for f in findings}
        print(
            f'corpus screen: {len(findings)} suspect fields in '
            f'{len(cases)}/{n} cases'
        )
        for f in findings:
            print(f"   {f['case']} {f['where']}: {', '.join(f['terms'])}")
            print(f"      {f['text']}")
        return 1 if findings else 0
    total = 0
    for run_dir in sys.argv[1:]:
        findings = audit(run_dir, corpus)
        turns = sum(
            1
            for p in glob.glob(os.path.join(run_dir, '*.jsonl'))
            for _ in open(p)
        )
        name = os.path.basename(run_dir.rstrip('/'))
        rate = 100 * len(findings) / turns if turns else 0.0
        print(f'{name:<16} user turns={turns:<6} leaks={len(findings)} ({rate:.2f}%)')
        for f in findings[:5]:
            print(f"   {f['case']} turn {f['turn']}: {', '.join(f['terms'])}")
            print(f"      {f['text']}")
        total += len(findings)
    return 1 if total else 0


if __name__ == '__main__':
    raise SystemExit(main())
