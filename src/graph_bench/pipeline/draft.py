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
    'reporter_engaged',
    'safe_content',
    'annotatable',
)


def render_thread(thread: dict, *, per_comment: int = 1400) -> str:
    lines = [
        f'TITLE: {thread["title"]}',
        f'URL: {thread["url"]}',
        f'LABELS: {", ".join(thread.get("labels", []))}',
        f'REPORTER: {thread["reporter"]}',
        '',
        'OPENING (reporter):',
        thread['body'][: 3 * per_comment],
        '',
    ]
    for i, c in enumerate(thread['comments']):
        who = c['author']
        tag = ' (reporter)' if who == thread['reporter'] else ''
        body = c['body']
        if len(body) > per_comment:
            body = body[:per_comment] + f' …[+{len(body) - per_comment}ch]'
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


def lint_task(task: Task, image_dir: Path) -> list[str]:
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
    refs = list(task.opening_images)
    for n in g.nodes.values():
        refs += n.symptom_images
    for e in g.edges:
        for c in e.clarifications:
            refs += c.images
    for r in refs:
        if not (image_dir / Path(r).name).exists():
            problems.append(f'missing image: {r}')
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
    fewshot = (repo_root / 'data/trial/graphs/bmo_1822845.json').read_text()
    system = DRAFT_SYSTEM.format(fewshot=fewshot)
    user = DRAFT_USER.format(
        repo=thread['repo'],
        number=thread['number'],
        task_id=task_id,
        created_from=created_from,
        attachments=attachments,
        thread=render_thread(thread),
    )
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
            raw = extract_text(
                llm.invoke(
                    REPAIR_PROMPT.format(error=str(exc)[:2000], previous=raw)
                )
            )
            continue
        problems = lint_task(task, image_dir)
        if problems and attempt < max_repairs:
            log(f'  repair {attempt + 1} (lint): {problems}')
            raw = extract_text(
                llm.invoke(
                    REPAIR_PROMPT.format(
                        error='; '.join(problems), previous=raw
                    )
                )
            )
            continue
        if problems:
            log(f'  draft FAILED lint after repairs: {problems}')
            return None
        return task
    return None
