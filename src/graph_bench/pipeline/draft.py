"""LLM stages: issue-level filter, graph drafting, validate + repair loop."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from graph_bench.oncall_graph.models import Task
from graph_bench.pipeline.prompts import (
    DRAFT_SYSTEM,
    DRAFT_USER,
    FILTER_PROMPT,
    REPAIR_PROMPT,
)
from graph_bench.user_simulator.provider import extract_text

if TYPE_CHECKING:
    from collections.abc import Callable

_FENCE = re.compile(r'^```(?:json)?\s*|\s*```$', re.MULTILINE)

FILTER_GATES = (
    'resolved_with_confirmed_fix',
    'technically_specific',
    'multi_turn_diagnostic',
    'environment_bound',
    'reporter_engaged',
    'safe_content',
    'annotatable',
)

# The reporter's own posts are the evidence user_answers must quote from;
# truncating them while maintainer summaries fit whole makes the drafting
# model substitute the engineer's conclusion for the raw output — the
# dominant leak class. So reporter comments get a much higher cap.
_REPORTER_CAP = 4000


def render_thread(thread: dict, *, per_comment: int = 1400) -> str:
    lines = [
        f'TITLE: {thread["title"]}',
        f'URL: {thread["url"]}',
        f'LABELS: {", ".join(thread.get("labels", []))}',
        f'REPORTER: {thread["reporter"]}',
        '',
        'OPENING (reporter):',
        thread['body'][: max(3 * per_comment, _REPORTER_CAP)],
        '',
    ]
    for i, c in enumerate(thread['comments']):
        who = c['author']
        is_reporter = who == thread['reporter']
        tag = ' (reporter)' if is_reporter else ''
        cap = _REPORTER_CAP if is_reporter else per_comment
        body = c['body']
        if len(body) > cap:
            body = body[:cap] + f' …[+{len(body) - cap}ch]'
        lines.append(f'--- c{i} [{who}{tag}] {c["created_at"][:10]}')
        lines.append(body)
    return '\n'.join(lines)


def _parse_json(raw: str) -> dict:
    text = _FENCE.sub('', raw.strip()).strip()
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
        msg = f'no JSON object in reply: {text[:200]}'
        raise ValueError(msg)
    return json.loads(text[start : end + 1])


def filter_issue(llm, thread: dict) -> dict:  # noqa: ANN001
    prompt = FILTER_PROMPT.format(thread=render_thread(thread))
    verdict = _parse_json(extract_text(llm.invoke(prompt)))
    verdict['passed'] = all(bool(verdict.get(k)) for k in FILTER_GATES)
    return verdict


def lint_task(
    task: Task, image_dir: Path, thread: dict | None = None
) -> list[str]:
    """Semantic checks beyond pydantic validation."""
    problems: list[str] = []
    g = task.graph
    terminals = [nid for nid, n in g.nodes.items() if n.is_terminal]
    if not terminals:
        problems.append('no terminal node')
    reachable = {g.start_node}
    frontier = [g.start_node]
    while frontier:
        cur = frontier.pop()
        for e in g.edges:
            if e.from_node == cur and e.to_node not in reachable:
                reachable.add(e.to_node)
                frontier.append(e.to_node)
    if not any(t in reachable for t in terminals):
        problems.append('terminal unreachable from start_node')
    if not any(e.edge_type in ('clarification_only', 'mixed') for e in g.edges):
        problems.append('no clarification edge')
    # Every non-terminal node needs a way forward, and the start node
    # needs at least one canonical (non-blind) exit — otherwise every run
    # is forced through a scored dead end, or strands entirely.
    out_edges: dict[str, list] = {}
    for e in g.edges:
        out_edges.setdefault(e.from_node, []).append(e)
    blind_targets = {
        e.to_node
        for e in g.edges
        if e.solution is not None and e.solution.is_known_blind_path
    }
    for nid in reachable:
        node = g.nodes[nid]
        if node.is_terminal:
            continue
        outs = out_edges.get(nid, [])
        if not outs and nid not in blind_targets:
            # blind-edge targets get auto-generated rollback escapes at
            # load time; anything else stranded is a real defect
            problems.append(f'non-terminal node {nid} has no outgoing edge')
    # Verification-timing heuristic: a terminal solution must not hard-
    # require an id that smells like a verification result granted by an
    # upstream clarification (rule 4d) — fix-then-verify, never the inverse.
    import re as _re
    _verif = _re.compile(
        r'retest|_verified_fix|verified_fixed|verified_working'
        r'|fix_verified|verified_no_recurrence|verified.*resolv'
        r'|update_verified|verified_restores|works_again'
    )
    for e in g.edges:
        if e.solution is None or not g.nodes[e.to_node].is_terminal:
            continue
        upstream_ids = {
            c.info_id
            for ue in g.edges
            if ue.to_node == e.from_node
            for c in ue.clarifications
        }
        for rid in e.solution.required_info.flat():
            if 'try_build' in rid or 'test_build' in rid or '_rc' in rid:
                continue  # pre-landing candidate-build tests are rule 4d(i)
            if rid in upstream_ids and _verif.search(rid):
                problems.append(
                    f'terminal solution {e.edge_id} hard-requires '
                    f'verification-shaped id {rid!r} granted by the '
                    f'immediately upstream clarification — re-shape to '
                    f'fix-then-verify (rule 4d)'
                )
    # Level consistency: an id required at level X must be declared at the
    # same level on the clarification that grants it.
    declared = {
        c.info_id: c.level
        for e in g.edges
        for c in e.clarifications
        if c.level
    }
    lvl_map = {'L1': 'L1_basic', 'L2': 'L2_inferable', 'L3': 'L3_specific'}
    for e in g.edges:
        if e.solution is None:
            continue
        for bucket, lname in lvl_map.items():
            for rid in getattr(e.solution.required_info, bucket):
                if rid in declared and declared[rid] != lname:
                    problems.append(
                        f'{e.edge_id}: id {rid!r} required at {bucket} but '
                        f'declared {declared[rid]} on its clarification'
                    )
    start_outs = out_edges.get(g.start_node, [])
    if start_outs and all(
        e.solution is not None and e.solution.is_known_blind_path
        for e in start_outs
    ):
        problems.append(
            'start node has no canonical (non-blind) outgoing edge — '
            'an agent making the correct first move has nothing to match'
        )
    opening_refs = list(task.opening_images)
    other_refs: list[str] = []
    for n in g.nodes.values():
        other_refs += n.symptom_images
    for e in g.edges:
        for c in e.clarifications:
            other_refs += c.images
    refs = opening_refs + other_refs
    repo_root = image_dir.parents[2]
    for r in refs:
        if not (repo_root / r).exists() and not (
            image_dir / Path(r).name
        ).exists():
            problems.append(f'missing image: {r}')
    # Each attachment hooked at most once across all hooks.
    names = [Path(r).name for r in refs]
    for name in sorted({n for n in names if names.count(n) > 1}):
        problems.append(f'image referenced more than once: {name}')
    # Provenance: an attachment the harvester recorded as coming from the
    # opening post may only appear in opening_images.
    if thread is not None:
        opening_files = {
            img['file']
            for img in thread.get('images', [])
            if img.get('where') == 'opening'
        }
        for r in other_refs:
            if Path(r).name in opening_files:
                problems.append(
                    f'opening-post attachment hooked to a later '
                    f'node/edge: {Path(r).name}'
                )
    return problems


def draft_task(
    llm,  # noqa: ANN001
    thread: dict,
    *,
    task_id: str,
    image_prefix: str,
    image_dir: Path,
    max_repairs: int = 2,
    log: Callable[[str], None] = print,
) -> Task | None:
    attachments = '\n'.join(
        f'- {image_prefix}/{img["file"]}  (from {img["where"]})'
        for img in thread.get('images', [])
    ) or '(none)'
    created_from = (
        f'{thread["url"]} (LLM-draft via graph_bench pipeline; '
        f'pending human review)'
    )
    repo_root = Path(__file__).resolve().parents[3]
    fewshot_a = (repo_root / 'data/trial/graphs/bmo_1822845.json').read_text()
    fewshot_b = (repo_root / 'data/trial/graphs/bmo_1865928.json').read_text()
    system = DRAFT_SYSTEM.format(fewshot_a=fewshot_a, fewshot_b=fewshot_b)
    user = DRAFT_USER.format(
        repo=thread['repo'],
        number=thread['number'],
        task_id=task_id,
        created_from=created_from,
        attachments=attachments,
        thread=render_thread(thread),
    )
    # Repair rounds keep the FULL conversation (system rules + thread +
    # the model's previous JSON) so the model can fix faithfulness errors
    # against the source instead of blindly rewiring fields.
    messages: list[tuple[str, str]] = [('system', system), ('user', user)]
    raw = extract_text(llm.invoke(messages))
    for attempt in range(max_repairs + 1):
        try:
            data = _parse_json(raw)
            data.setdefault('metadata', {})
            data['metadata']['hitl_reviewed'] = False
            data['metadata'].setdefault('graph_version', 'v1')
            data['metadata']['created_from'] = created_from
            task = Task.model_validate(data)
        except Exception as exc:  # noqa: BLE001 - feed back to the model
            if attempt == max_repairs:
                log(f'  draft FAILED after {max_repairs} repairs: {exc}')
                return None
            log(f'  repair {attempt + 1}: {str(exc)[:160]}')
            messages = [
                *messages,
                ('assistant', raw),
                ('user', REPAIR_PROMPT.format(error=str(exc)[:2000])),
            ]
            raw = extract_text(llm.invoke(messages))
            continue
        problems = lint_task(task, image_dir, thread)
        if problems and attempt < max_repairs:
            log(f'  repair {attempt + 1} (lint): {problems}')
            messages = [
                *messages,
                ('assistant', raw),
                ('user', REPAIR_PROMPT.format(error='; '.join(problems))),
            ]
            raw = extract_text(llm.invoke(messages))
            continue
        if problems:
            log(f'  draft FAILED lint after repairs: {problems}')
            return None
        return task
    return None
