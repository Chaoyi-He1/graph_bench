"""Generate per-case human-review documents under data/*/review/.

Each drafted (or hand-annotated) task graph gets one Markdown page with the
rendered graph (mermaid — GitHub renders it natively), an edge-by-edge audit
table, source links, and the review checklist distilled from the pilot's
defect catalog. Reviewers work through the checklist, edit the graph JSON if
needed, re-validate, and flip ``metadata.hitl_reviewed`` to true.

Usage:  uv run scripts/make_review_docs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / 'src'))

from graph_bench.oncall_graph.models import Task  # noqa: E402
from graph_bench.oncall_graph.visualize import task_to_mermaid  # noqa: E402

CHECKLIST = """\
## Review checklist

> The graph is the case's ANSWER KEY, not a transcript: edge order need
> not mirror thread chronology. Do not file chronology mismatch as a
> defect; what must be faithful is who knew what, when.

Structural (machine-checked by `scripts/validate.py`, re-verify after edits):

- [ ] validates: schema + info-containment + terminal reachability

Semantic (the defect catalog — check each against the source thread):

- [ ] **Faithful blind paths** — every `is_known_blind_path` edge corresponds
  to an attempt actually falsified in the thread (or a brush-off the
  reporter rejected). No invented failures; no ACCEPTED fix mislabeled as
  a blind path (the most common LLM defect class).
- [ ] **Gettable required info** — every id in any `solution.required_info`
  is obtainable: a clarification on some edge, or in the start node's
  info_state, or volunteered (with matching `volunteered_info` text).
  Engineer-only inference belongs in `info_inferred_by_engineer` /
  `inference_hint`, not in hard required_info.
- [ ] **Measurement-class rule** — handler-initiated measurements the user
  executed (bisections, test builds, config probes, version checks) are
  clarification edges, not solutions; their answers state what the
  measurement showed.
- [ ] **No logistics gates** — `required_elements_for_full_match` encode the
  technical diagnostic→fix chain, not release/packaging/scheduling
  remarks the engineer merely mentioned.
- [ ] **Coherent reveals** — each `user_answer_in_this_oncall` is consistent
  with the thread, delivers what it promises, and stays in the user's
  voice (no future knowledge, no diagnosis the user never made).
- [ ] **Symptoms are observations** — `symptoms_visible` contains only what
  the user can see; no causes or advice.
- [ ] **Terminal semantics** — satisfaction_conditions demand root cause +
  evidence grounding + prohibition of falsified moves + user verification;
  the terminal node is the verified-resolved state.
- [ ] **Image assignment** — referenced attachments exist and sit on the
  right hook (opening / node symptom / clarification evidence).
- [ ] **Persona** — matches the reporter's actual expertise and style.

## How to sign off

1. Edit the graph JSON if needed (authored fields only; keep
   `concrete_example` as the factual record).
2. `uv run scripts/validate.py '<graph path>'`
3. Set `metadata.hitl_reviewed: true` in the graph JSON.
4. Re-run `uv run scripts/make_review_docs.py` to refresh this page.
"""


FINDINGS_PATH = REPO / 'data' / 'REVIEW_FINDINGS.json'
_SEV_MARK = {'high': '🔴', 'medium': '🟠', 'low': '🟡'}
_FINDINGS: dict = {}


def _findings_section(slug: str) -> list[str]:
    """Render the machine-review findings for one case, if any exist."""
    if not FINDINGS_PATH.exists():
        return []
    data = json.loads(FINDINGS_PATH.read_text()).get(slug)
    if not data:
        return []
    lines = [
        '',
        '## Machine review (audit pass, adversarially verified)',
        '',
        f'Auditor verdict: **{data.get("reviewer_verdict", "n/a")}** · '
        f'{data.get("n_confirmed", 0)} of {data.get("n_raised", 0)} findings '
        f'survived independent refutation.',
        '',
        f'_{data.get("summary", "")}_',
        '',
    ]
    if data.get('confirmed_findings') or []:
        lines += ['### Confirmed findings', '']
        order = {'high': 0, 'medium': 1, 'low': 2}
        for f in sorted(
            data.get('confirmed_findings') or [],
            key=lambda x: order.get(x.get('severity'), 3),
        ):
            sev = f.get('severity', '?')
            lines += [
                f'- [ ] {_SEV_MARK.get(sev, "⚪")} **{f.get("defect_class")}** '
                f'({sev}) — `{f.get("location", "n/a")}`',
                f'  - claim: {f.get("claim")}',
                f'  - thread evidence: {f.get("thread_evidence")}',
                f'  - suggested fix: {f.get("suggested_fix")}',
                f'  - verifier: {f.get("verifier_reasoning", "")[:400]}',
            ]
        lines.append('')
    if data.get('refuted_claims') or []:
        lines += [
            '### Refuted claims (auditor was wrong — do not act on these)',
            '',
        ]
        for r in data.get('refuted_claims') or []:
            lines += [
                f'- ~~{r.get("defect_class")}~~: {r.get("claim", "")[:220]}',
                f'  - why refuted: {r.get("why_refuted", "")[:320]}',
            ]
        lines.append('')
    return lines


def render_case(graph_path: Path, out_dir: Path) -> tuple[str, bool]:
    task = Task.model_validate(json.loads(graph_path.read_text()))
    g = task.graph
    src = task.metadata.created_from or ''
    url = src.split(' ')[0] if src.startswith('http') else ''
    kind = (
        'LLM draft (needs review)'
        if 'LLM-draft' in src
        else 'hand-annotated pilot'
    )
    lines = [
        f'# Review: {task.task_id}',
        '',
        f'**{task.title}**',
        '',
        f'- source: {url or src}',
        f'- kind: {kind}',
        f'- reviewed: `{task.metadata.hitl_reviewed}`',
        f'- graph: `{graph_path.relative_to(REPO)}` · raw thread: '
        f'`{graph_path.relative_to(REPO).as_posix().replace("/graphs/", "/raw/")}`',
        '',
        '```mermaid',
        task_to_mermaid(task),
        '```',
        '',
        '## Opening (body)',
        '',
        '> ' + (task.body or '').replace('\n', '\n> '),
        '',
        '## Satisfaction conditions',
        '',
    ]
    lines += [f'{i + 1}. {c}' for i, c in enumerate(task.satisfaction_conditions)]
    lines += ['', '## Edges', '']
    lines += [
        '| edge | type | gates / info | payload |',
        '|---|---|---|---|',
    ]
    for e in g.edges:
        if e.solution is not None:
            blind = ' **BLIND**' if e.solution.is_known_blind_path else ''
            req = ', '.join(
                e.solution.required_info.L1
                + e.solution.required_info.L2
                + e.solution.required_info.L3
            )
            elems = ', '.join(e.solution.required_elements_for_full_match)
            payload = e.solution.intent.replace('|', '\\|')
            gates = f'req_info: {req}<br>elements: {elems}'
            kind_cell = f'{e.edge_type}{blind}'
        else:
            infos = ', '.join(c.info_id for c in e.clarifications)
            answers = ' / '.join(
                c.user_answer_in_this_oncall[:110].replace('|', '\\|')
                for c in e.clarifications
            )
            payload = answers
            gates = f'asks: {infos}'
            kind_cell = e.edge_type
        lines.append(
            f'| `{e.edge_id}` | {kind_cell} | {gates} | {payload} |'
        )
    lines += ['', '## Nodes', '']
    lines += ['| node | terminal | volunteered | images | symptoms |', '|---|---|---|---|---|']
    for nid, n in g.nodes.items():
        sym = ' '.join(n.symptoms_visible)[:140].replace('|', '\\|')
        lines.append(
            f'| `{nid}` | {"✓" if n.is_terminal else ""} '
            f'| {len(n.volunteered_info)} | {len(n.symptom_images)} | {sym} |'
        )
    lines += _findings_section(task.task_id)
    lines += ['', CHECKLIST]
    out = out_dir / f'{graph_path.stem}.md'
    out.write_text('\n'.join(lines))
    return graph_path.stem, task.metadata.hitl_reviewed


def main() -> None:
    global _FINDINGS  # noqa: PLW0603
    _FINDINGS = (
        json.loads(FINDINGS_PATH.read_text())
        if FINDINGS_PATH.exists()
        else {}
    )
    index: list[str] = [
        '# Human review queue',
        '',
        'One page per task graph: rendered graph, edge audit table, source',
        'links, and the review checklist (defect catalog from the pilot).',
        '',
        '| case | kind | audit verdict | confirmed findings | reviewed |',
        '|---|---|---|---|---|',
    ]
    for graphs_dir in sorted(REPO.glob('data/*/graphs')):
        out_dir = graphs_dir.parent / 'review'
        out_dir.mkdir(exist_ok=True)
        for gp in sorted(graphs_dir.glob('*.json')):
            stem, reviewed = render_case(gp, out_dir)
            created = json.loads(gp.read_text()).get('metadata', {}).get(
                'created_from', ''
            )
            rel = (out_dir / f'{stem}.md').relative_to(REPO)
            kind = 'LLM draft' if 'LLM-draft' in created else 'hand'
            link = rel.as_posix().removeprefix('data/')
            fd = _FINDINGS.get(stem, {})
            sevs = [
                f.get('severity') for f in fd.get('confirmed_findings', [])
            ]
            badge = ' '.join(
                f'{_SEV_MARK[s]}{sevs.count(s)}'
                for s in ('high', 'medium', 'low')
                if sevs.count(s)
            ) or '—'
            index.append(
                f'| [{stem}]({link}) | {kind} '
                f'| {fd.get("reviewer_verdict", "—")} | {badge} '
                f'| {"✅" if reviewed else "⬜"} |'
            )
            print('wrote', rel)
    # one index at data/REVIEW.md linking both datasets
    (REPO / 'data' / 'REVIEW.md').write_text('\n'.join(index) + '\n')
    print('index: data/REVIEW.md')


if __name__ == '__main__':
    main()
